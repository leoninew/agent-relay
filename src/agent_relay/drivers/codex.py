from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
from contextlib import ExitStack, suppress
from dataclasses import dataclass
from pathlib import Path
from threading import Thread
from time import monotonic
from typing import Any, Literal, cast

from websockets.sync.client import ClientConnection, connect

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
ThreadStatus = Literal["notLoaded", "idle", "active", "systemError"]


class RpcRejected(RuntimeError):
    """The server returned an explicit JSON-RPC error response."""


class RpcDisconnected(RuntimeError):
    pass


@dataclass(frozen=True)
class SessionInfo:
    id: str
    cwd: str
    provider: str
    name: str
    status: ThreadStatus
    archived: bool = False

    @property
    def presence(self) -> Literal["available", "busy", "offline"]:
        if self.status == "idle":
            return "available"
        return "busy" if self.status == "active" else "offline"


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
        return SessionInfo(
            id=cast(str, values[0]),
            cwd=cast(str, values[1]),
            provider=cast(str, values[2]),
            name=name or cast(str, values[0]),
            status=status,
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
        return list(result.values())

    def inspect(self, thread_id: str) -> SessionInfo:
        with ProxyRpc(self.command, self.timeout) as rpc:
            result = rpc.call("thread/read", {"threadId": thread_id, "includeTurns": False})
            return self._session(result.get("thread"))
