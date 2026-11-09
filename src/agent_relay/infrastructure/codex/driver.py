from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
from contextlib import ExitStack, suppress
from dataclasses import replace
from pathlib import Path
from threading import Thread
from time import monotonic
from typing import Any, cast

from websockets.sync.client import ClientConnection, connect

from agent_relay.application.delivery.ports import (
    ActivationRejected,
    InputPage,
    QueueHead,
    QueueReceipt,
    QueueRejected,
    ReceivedInput,
)
from agent_relay.application.members.sessions import SessionInfo, SessionStatus

SOURCE_KINDS = [
    "cli",
    "vscode",
    "exec",
    "appServer",
    "subAgent",
    "subAgentReview",
    "subAgentCompact",
    "subAgentThreadSpawn",
    "subAgentOther",
    "unknown",
]


class RpcRejected(RuntimeError):
    """The server returned an explicit JSON-RPC error response."""


class RpcDisconnected(RuntimeError):
    pass


def _launch_command(command: list[str]) -> list[str]:
    executable = shutil.which(command[0]) or command[0]
    path = Path(executable)
    if path.suffix.lower() not in {".cmd", ".bat", ".ps1"}:
        return [executable, *command[1:]]

    # npm's Windows shims aren't executable by CreateProcess. Start the official
    # package entry with Node, preserving argv without interpreting a shell script.
    if path.stem.lower() != "codex" or path.suffix.lower() == ".bat":
        raise OSError("Expected a native Codex executable, Node entry or official npm Codex shim")
    entry = path.parent / "node_modules" / "@openai" / "codex" / "bin" / "codex.js"
    if not entry.is_file():
        raise FileNotFoundError(f"Codex npm entry point not found: {entry}")
    node = path.parent / "node.exe"
    if not node.is_file():
        found = shutil.which("node")
        if found is None or Path(found).suffix.lower() in {".cmd", ".bat", ".ps1"}:
            raise FileNotFoundError("Node executable not found for the Codex npm entry point")
        node = Path(found)
    return [str(node), str(entry), *command[1:]]


class ProxyRpc:
    """A short-lived connection to the shared daemon, never its execution host."""

    def __init__(self, command: list[str], timeout: float) -> None:
        self.command = command
        self.timeout = timeout
        self.process: subprocess.Popen[bytes] | None = None
        self.ws: ClientConnection | None = None
        self.sockets: list[socket.socket] = []
        self.bridges: list[Thread] = []
        self._counter = 0
        self._connections = ExitStack()

    def __enter__(self) -> ProxyRpc:
        try:
            process = subprocess.Popen(
                _launch_command(self.command),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            self.process = process
            local, bridge = socket.socketpair()
            self.sockets = [local, bridge]

            def to_proxy() -> None:
                assert process.stdin is not None
                try:
                    while data := bridge.recv(65536):
                        process.stdin.write(data)
                        process.stdin.flush()
                except OSError:
                    pass
                finally:
                    with suppress(OSError):
                        process.stdin.close()

            def from_proxy() -> None:
                assert process.stdout is not None
                try:
                    while data := os.read(process.stdout.fileno(), 65536):
                        bridge.sendall(data)
                except OSError:
                    pass
                finally:
                    with suppress(OSError):
                        bridge.shutdown(socket.SHUT_WR)

            self.bridges = [
                Thread(target=to_proxy, name="relay-proxy-write", daemon=True),
                Thread(target=from_proxy, name="relay-proxy-read", daemon=True),
            ]
            for thread in self.bridges:
                thread.start()
            # The public proxy carries WebSocket frames over stdin/stdout, not JSONL.
            self.ws = self._connections.enter_context(
                connect(
                    "ws://localhost/",
                    sock=local,
                    proxy=None,
                    open_timeout=self.timeout,
                    close_timeout=1,
                    max_size=None,
                )
            )
            self.call(
                "initialize",
                {
                    "clientInfo": {"name": "agent_relay", "version": "0.1.0"},
                    "capabilities": {"experimentalApi": True},
                },
            )
            self.ws.send(json.dumps({"method": "initialized", "params": {}}))
            return self
        except BaseException:
            self.close()
            raise

    def call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if self.ws is None:
            raise RpcDisconnected("Codex proxy is not connected")
        self._counter += 1
        request_id = self._counter
        self.ws.send(json.dumps({"id": request_id, "method": method, "params": params}))
        deadline = monotonic() + self.timeout
        while (remaining := deadline - monotonic()) > 0:
            message = json.loads(self.ws.recv(timeout=remaining))
            if not isinstance(message, dict):
                raise RpcDisconnected("Invalid Codex RPC response")
            if "method" in message:
                if "id" in message:
                    self.ws.send(
                        json.dumps(
                            {
                                "id": message["id"],
                                "error": {
                                    "code": -32601,
                                    "message": "This metadata client has no request handler.",
                                },
                            }
                        )
                    )
                continue
            if message.get("id") != request_id:
                raise RpcDisconnected("Unexpected Codex RPC response ID")
            if "error" in message:
                raise RpcRejected(str(message["error"]))
            if not isinstance(message.get("result"), dict):
                raise RpcDisconnected("Invalid Codex RPC result")
            return cast(dict[str, Any], message["result"])
        raise TimeoutError(method)

    def close(self) -> None:
        with suppress(Exception):
            self._connections.close()
        for stream in self.sockets:
            with suppress(OSError):
                stream.shutdown(socket.SHUT_RDWR)
            stream.close()
        if self.process is not None:
            # Let the proxy and its Node launcher exit after WebSocket close.
            # Never terminate the shared daemon or user execution hosts.
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                try:
                    self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=3)
            for thread in self.bridges:
                thread.join(timeout=3)
            for pipe in (self.process.stdin, self.process.stdout):
                if pipe is not None:
                    pipe.close()

    def __exit__(self, *args: object) -> None:
        self.close()


class CodexDriver:
    def __init__(self, command: list[str], timeout: float) -> None:
        self.command = command
        self.timeout = timeout

    @staticmethod
    def _session(thread: Any, *, archived: bool = False) -> SessionInfo:
        if not isinstance(thread, dict):
            raise RpcDisconnected("Missing Codex thread metadata")
        values = [thread.get(key) for key in ("id", "cwd", "modelProvider")]
        if any(not isinstance(value, str) or not value for value in values):
            raise RpcDisconnected("Incomplete Codex session identity")
        status = thread.get("status", {}).get("type")
        if status not in {"notLoaded", "idle", "active", "systemError"}:
            raise RpcDisconnected("Invalid Codex thread status")
        name = thread.get("name")
        if name is not None and not isinstance(name, str):
            raise RpcDisconnected("Invalid Codex thread name")
        name = (name or "").strip()
        preview = thread.get("preview")
        if not name and isinstance(preview, str):
            name = " ".join(preview.split())
        return SessionInfo(
            id=cast(str, values[0]),
            cwd=cast(str, values[1]),
            provider=cast(str, values[2]),
            name=name or "未命名会话",
            status=cast(
                SessionStatus,
                {
                    "notLoaded": "unavailable",
                    "idle": "idle",
                    "active": "active",
                    "systemError": "error",
                }[status],
            ),
            archived=archived,
        )

    def list_sessions(self) -> list[SessionInfo]:
        result: dict[str, SessionInfo] = {}
        with ProxyRpc(self.command, self.timeout) as rpc:
            for archived in (False, True):
                cursor: str | None = None
                seen: set[str] = set()
                while True:
                    page = rpc.call(
                        "thread/list",
                        {
                            "cursor": cursor,
                            "limit": 100,
                            "modelProviders": [],
                            "sourceKinds": SOURCE_KINDS,
                            "archived": archived,
                            "useStateDbOnly": True,
                        },
                    )
                    data = page.get("data")
                    if not isinstance(data, list):
                        raise RpcDisconnected("Missing Codex session list")
                    for row in data:
                        info = self._session(row, archived=archived)
                        result.setdefault(info.id, info)
                    cursor = page.get("nextCursor")
                    if cursor is None:
                        break
                    if not isinstance(cursor, str) or not cursor or cursor in seen:
                        raise RpcDisconnected("Invalid Codex pagination cursor")
                    seen.add(cursor)
            loaded: set[str] = set()
            cursor = None
            seen = set()
            while True:
                page = rpc.call("thread/loaded/list", {"cursor": cursor, "limit": 100})
                ids = page.get("data")
                if not isinstance(ids, list) or any(not isinstance(sid, str) for sid in ids):
                    raise RpcDisconnected("Invalid loaded Codex session list")
                loaded.update(ids)
                cursor = page.get("nextCursor")
                if cursor is None:
                    break
                if not isinstance(cursor, str) or not cursor or cursor in seen:
                    raise RpcDisconnected("Invalid loaded Codex pagination cursor")
                seen.add(cursor)
            for sid, info in tuple(result.items()):
                if sid not in loaded:
                    result[sid] = replace(info, status="unavailable")
            for sid in sorted(loaded):
                row = rpc.call("thread/read", {"threadId": sid, "includeTurns": False})
                info = self._session(row.get("thread"))
                if info.id != sid:
                    raise RpcDisconnected("Loaded Codex session identity mismatch")
                result[sid] = (
                    replace(info, archived=result[sid].archived) if sid in result else info
                )
        return list(result.values())

    def inspect(self, thread_id: str) -> SessionInfo:
        with ProxyRpc(self.command, self.timeout) as rpc:
            result = rpc.call("thread/read", {"threadId": thread_id, "includeTurns": False})
            return self._session(result.get("thread"))

    def enqueue(self, thread_id: str, client_message_id: str, text: str) -> QueueReceipt:
        with ProxyRpc(self.command, self.timeout) as rpc:
            metadata = rpc.call("thread/read", {"threadId": thread_id, "includeTurns": False})
            session = self._session(metadata.get("thread"))
            catalog = rpc.call("skills/list", {"cwds": [session.cwd], "forceReload": True})
            skills = [
                skill
                for entry in catalog["data"]
                if entry["cwd"] == session.cwd
                for skill in entry["skills"]
                if skill.get("name") == "agent-relay:agent-relay"
                and skill.get("pluginId") == "agent-relay@agent-relay-local"
                and skill.get("enabled") is True
            ]
            if len(skills) != 1:
                raise RpcDisconnected("Agent Relay skill unavailable; run make install for Codex")
            skill = skills[0]
            try:
                result = rpc.call(
                    "thread/queue/add",
                    {
                        "threadId": thread_id,
                        "clientUserMessageId": client_message_id,
                        "input": [
                            {"type": "text", "text": text},
                            {"type": "skill", "name": skill["name"], "path": skill["path"]},
                        ],
                    },
                )
            except RpcRejected as exc:
                raise QueueRejected(str(exc)) from exc
            receipt = result.get("queuedSubmission")
            if (
                not isinstance(receipt, dict)
                or not isinstance(receipt.get("id"), str)
                or not receipt["id"]
                or receipt.get("clientUserMessageId") != client_message_id
            ):
                raise RpcDisconnected("Queue receipt does not match this submission")
            return QueueReceipt(
                receipt["id"], {key: value for key, value in receipt.items() if key != "input"}
            )

    def activation_candidate(self, thread_id: str) -> QueueHead | None:
        with ProxyRpc(self.command, self.timeout) as rpc:
            metadata = rpc.call("thread/read", {"threadId": thread_id, "includeTurns": False})
            info = self._session(metadata.get("thread"))
            if info.id != thread_id:
                raise RpcDisconnected("Codex session identity mismatch")
            if info.status != "idle":
                return None
            page = rpc.call("thread/queue/list", {"threadId": thread_id, "limit": 1})
            data = page.get("data")
            if not isinstance(data, list):
                raise RpcDisconnected("Missing Codex queue list")
            if not data:
                return None
            head = data[0]
            if not isinstance(head, dict) or not isinstance(head.get("id"), str) or not head["id"]:
                raise RpcDisconnected("Invalid Codex queue head")
            client_id = head.get("clientUserMessageId")
            return QueueHead(head["id"], client_id if isinstance(client_id, str) else None)

    def activate(self, thread_id: str, queued_submission_id: str) -> str:
        with ProxyRpc(self.command, self.timeout) as rpc:
            try:
                result = rpc.call(
                    "thread/queue/start",
                    {"threadId": thread_id, "queuedSubmissionId": queued_submission_id},
                )
            except RpcRejected as exc:
                raise ActivationRejected(str(exc)) from exc
            turn = result.get("turn")
            if not isinstance(turn, dict) or not isinstance(turn.get("id"), str) or not turn["id"]:
                raise RpcDisconnected("Missing started Codex turn identity")
            return cast(str, turn["id"])

    def read_input_page(self, thread_id: str, cursor: str | None = None) -> InputPage:
        with ProxyRpc(self.command, self.timeout) as rpc:
            page = rpc.call(
                "thread/items/list",
                {"threadId": thread_id, "cursor": cursor, "limit": 100, "sortDirection": "desc"},
            )
            data = page.get("data")
            if not isinstance(data, list):
                raise RpcDisconnected("Missing Codex input history page")
            inputs = []
            for row in data:
                if not isinstance(row, dict) or not isinstance(row.get("item"), dict):
                    raise RpcDisconnected("Invalid Codex history item")
                item = row["item"]
                if item.get("type") != "userMessage" or not item.get("clientId"):
                    continue
                values = (item["clientId"], item.get("id"), row.get("turnId"))
                if any(not isinstance(value, str) or not value for value in values):
                    raise RpcDisconnected("Incomplete Codex input identity")
                inputs.append(ReceivedInput(*(cast(str, value) for value in values)))
            next_cursor = page.get("nextCursor")
            if next_cursor is not None and (not isinstance(next_cursor, str) or not next_cursor):
                raise RpcDisconnected("Invalid Codex input history cursor")
            return InputPage(tuple(inputs), next_cursor)
