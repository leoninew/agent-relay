"""T01 protocol evidence probe, independent of the Relay runtime and housekeeper.

Use a native codex executable. ``metadata`` only reads the running daemon's
version and thread metadata. ``isolated`` creates labelled threads in a temporary
workspace in its own app-server process. Add --run-model to exercise dynamic
tools and queue submission in those test threads. Queue submission itself can
start inference, so it is also gated by --run-model. No existing work thread is
resumed or submitted to.
Raw configuration, credentials, and unrelated conversation contents aren't saved.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import socket
import subprocess
import tempfile
import threading
import time
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


class RpcError(RuntimeError):
    def __init__(self, error: dict[str, Any]) -> None:
        self.error = error
        super().__init__(f"RPC error {error.get('code')}: {error.get('message')}")


class Client:
    def __init__(self, command: list[str], *, proxy: bool = False) -> None:
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        self.counter = 0
        self.inbox: queue.Queue[dict[str, Any] | None] = queue.Queue()
        self.notifications: list[dict[str, Any]] = []
        self.requests: list[dict[str, Any]] = []
        self.ws: Any = None
        self.bridges: list[socket.socket] = []
        if proxy:
            # The public proxy carries WebSocket bytes, not JSONL. A socketpair
            # lets the existing WebSocket library perform framing and handshake.
            from websockets.sync.client import connect

            local, bridge = socket.socketpair()
            self.bridges = [local, bridge]

            def to_proxy() -> None:
                assert self.process.stdin is not None
                try:
                    while data := bridge.recv(65536):
                        self.process.stdin.write(data)
                        self.process.stdin.flush()
                except OSError:
                    pass

            def from_proxy() -> None:
                assert self.process.stdout is not None
                try:
                    while data := os.read(self.process.stdout.fileno(), 65536):
                        bridge.sendall(data)
                except OSError:
                    pass
                finally:
                    with suppress(OSError):
                        bridge.shutdown(socket.SHUT_WR)

            threading.Thread(target=to_proxy, daemon=True).start()
            threading.Thread(target=from_proxy, daemon=True).start()
            self.ws = connect(
                "ws://localhost/", sock=local, proxy=None, open_timeout=15, close_timeout=2
            )
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self) -> None:
        try:
            if self.ws is not None:
                for message in self.ws:
                    self.inbox.put(json.loads(message))
            else:
                assert self.process.stdout is not None
                for line in self.process.stdout:
                    self.inbox.put(json.loads(line))
        except Exception:
            pass
        finally:
            self.inbox.put(None)

    def send(self, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, ensure_ascii=False)
        if self.ws is not None:
            self.ws.send(encoded)
        else:
            assert self.process.stdin is not None
            self.process.stdin.write((encoded + "\n").encode())
            self.process.stdin.flush()

    def receive(self, timeout: float = 20) -> dict[str, Any]:
        message = self.inbox.get(timeout=timeout)
        if message is None:
            raise EOFError("app-server transport closed")
        if "method" in message:
            (self.requests if "id" in message else self.notifications).append(message)
        return message

    def call(self, method: str, params: dict[str, Any], timeout: float = 30) -> Any:
        self.counter += 1
        request_id = self.counter
        self.send({"id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + timeout
        while (remaining := deadline - time.monotonic()) > 0:
            message = self.receive(remaining)
            if "method" not in message and message.get("id") == request_id:
                if "error" in message:
                    raise RpcError(message["error"])
                return message["result"]
        raise TimeoutError(method)

    def initialize(self) -> dict[str, Any]:
        result = self.call(
            "initialize",
            {
                "clientInfo": {"name": "agent_relay_t01_probe", "version": "0.1.0"},
                "capabilities": {"experimentalApi": True},
            },
        )
        self.send({"method": "initialized", "params": {}})
        return {key: result.get(key) for key in ("platformFamily", "platformOs")}

    def close(self) -> None:
        if self.ws is not None:
            self.ws.close()
        if self.process.stdin is not None:
            self.process.stdin.close()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)
        for stream in self.bridges:
            stream.close()


def disabled_integrations() -> list[str]:
    # CLI table overrides replace that table. Setting only a per-server enabled
    # key discards its transport, so clear the table for this child process.
    overrides: list[str] = ["-c", "mcp_servers={}"]
    for feature in ("apps", "plugins", "multi_agent", "shell_tool", "unified_exec", "hooks"):
        overrides.extend(["--disable", feature])
    return overrides


def tool_spec() -> dict[str, Any]:
    return {
        "type": "function",
        "name": "room_publish_probe",
        "description": "Protocol probe only. Return the requested synthetic message once.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "topicIds": {"type": "array", "items": {"type": "string"}},
                "mentionedMemberIds": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["content", "topicIds", "mentionedMemberIds"],
            "additionalProperties": False,
        },
    }


def run_metadata(codex: str, cwd: str) -> dict[str, Any]:
    client = Client([codex, "app-server", "proxy"], proxy=True)
    try:
        initialized = client.initialize()
        result = client.call("thread/list", {"cwd": cwd, "limit": 20, "useStateDbOnly": True})
        return {
            "initialize": initialized,
            "threads": [
                {key: row.get(key) for key in ("id", "cwd", "modelProvider", "status")}
                for row in result["data"]
            ],
            "hasMore": result.get("nextCursor") is not None,
        }
    finally:
        client.close()


def run_isolated(
    codex: str, output: Path, run_model: bool, resume_evidence: Path | None = None
) -> dict[str, Any]:
    previous = json.loads(resume_evidence.read_text(encoding="utf-8")) if resume_evidence else None
    workspace = (
        Path(previous["workspace"])
        if previous
        else Path(tempfile.mkdtemp(prefix="agent-relay-t01-workspace-"))
    )
    command = [codex, "app-server", *disabled_integrations()]
    client = Client(command)
    result: dict[str, Any] = {"workspace": str(workspace), "runModel": run_model}
    owned_threads: list[str] = []
    try:
        result["initialize"] = client.initialize()
        if previous:
            thread_id = previous["thread"]["id"]
            if (
                thread_id not in previous["ownedThreads"]
                or workspace.parent.resolve() != Path(tempfile.gettempdir()).resolve()
                or not workspace.name.startswith("agent-relay-t01-workspace-")
            ):
                raise ValueError("Resume is limited to this probe's own temporary test threads")
            metadata = client.call("thread/read", {"threadId": thread_id, "includeTurns": False})
            if Path(metadata["thread"]["cwd"]).resolve() != workspace.resolve():
                raise ValueError("Test thread workspace mismatch")
            client.call("thread/unarchive", {"threadId": thread_id})
            started = client.call(
                "thread/resume",
                {
                    "threadId": thread_id,
                    "excludeTurns": True,
                    "approvalPolicy": "never",
                    "sandbox": "read-only",
                },
            )
            result["resumedFrom"] = str(resume_evidence)
        else:
            started = client.call(
                "thread/start",
                {
                    "cwd": str(workspace),
                    "approvalPolicy": "never",
                    "sandbox": "read-only",
                    "historyMode": "paginated",
                    "serviceName": "agent-relay-t01-probe",
                    "baseInstructions": (
                        "You are an isolated protocol test fixture. Do not read or change files. "
                        "Do not execute commands, access networks, or spawn agents. Only call "
                        "room_publish_probe when explicitly requested. Use synthetic values only."
                    ),
                    "dynamicTools": [tool_spec()],
                },
            )
        thread_id = started["thread"]["id"]
        owned_threads.append(thread_id)
        result["thread"] = {
            key: started["thread"].get(key) for key in ("id", "cwd", "modelProvider", "status")
        }
        result["model"] = started.get("model")
        client.call("thread/name/set", {"threadId": thread_id, "name": "[T01 isolated probe]"})
        result["emptyQueue"] = client.call("thread/queue/list", {"threadId": thread_id})
        result["emptyHistory"] = client.call(
            "thread/items/list", {"threadId": thread_id, "limit": 2, "sortDirection": "desc"}
        )
        try:
            client.call("thread/queue/add", {"threadId": thread_id, "input": []})
        except RpcError as exc:
            result["invalidRequestRejection"] = exc.error
        if run_model:
            client_id = f"t01-tool-{uuid4()}"
            receipt = client.call(
                "thread/queue/add",
                {
                    "threadId": thread_id,
                    "clientUserMessageId": client_id,
                    "input": [
                        {
                            "type": "text",
                            "text": (
                                "Call room_publish_probe exactly once with "
                                "content='T01 tool probe', "
                                "topicIds=['probe-topic'], mentionedMemberIds=[]. After the result "
                                "reply exactly 'T01 final probe'. Do not use other tools."
                            ),
                        }
                    ],
                },
            )
            assert receipt["queuedSubmission"]["clientUserMessageId"] == client_id
            assert receipt["queuedSubmission"]["id"]
            result["modelReceipt"] = receipt
            deadline = time.monotonic() + 150
            callbacks = []
            while time.monotonic() < deadline:
                try:
                    message = client.receive(timeout=min(20, deadline - time.monotonic()))
                except queue.Empty:
                    continue
                if message.get("method") == "item/tool/call":
                    params = message["params"]
                    if params["threadId"] != thread_id or params["tool"] != "room_publish_probe":
                        raise RuntimeError("Unexpected tool context")
                    callbacks.append(params)
                    # Hold this callback while submitting two more messages.
                    # Their model turns must not run: remove this probe's own
                    # pending follow-ups before releasing the tool callback.
                    if len(callbacks) == 1 and not previous:
                        result["whileToolPending"] = client.call(
                            "thread/read", {"threadId": thread_id, "includeTurns": False}
                        )["thread"]["status"]
                        submissions = []
                        for index in range(2):
                            pending = client.call(
                                "thread/queue/add",
                                {
                                    "threadId": thread_id,
                                    "clientUserMessageId": f"t01-pending-{uuid4()}",
                                    "input": [
                                        {
                                            "type": "text",
                                            "text": (
                                                f"Synthetic pending probe {index}; do not execute."
                                            ),
                                        }
                                    ],
                                },
                            )
                            submissions.append(pending["queuedSubmission"])
                        result["busyReceipts"] = submissions
                        result["duplicateClientId"] = client.call(
                            "thread/queue/add",
                            {
                                "threadId": thread_id,
                                "clientUserMessageId": submissions[0]["clientUserMessageId"],
                                "input": submissions[0]["input"],
                            },
                        )
                        result["busyQueue"] = client.call(
                            "thread/queue/list", {"threadId": thread_id, "limit": 1}
                        )
                        pending_entries = list(result["busyQueue"]["data"])
                        cursor = result["busyQueue"].get("nextCursor")
                        pages = []
                        while cursor:
                            page = client.call(
                                "thread/queue/list",
                                {"threadId": thread_id, "limit": 1, "cursor": cursor},
                            )
                            pages.append(page)
                            pending_entries.extend(page["data"])
                            cursor = page.get("nextCursor")
                        result["busyQueueMorePages"] = pages
                        result["historyWhileToolPending"] = client.call(
                            "thread/items/list", {"threadId": thread_id, "limit": 20}
                        )
                        for entry in pending_entries:
                            client.call(
                                "thread/queue/delete",
                                {"threadId": thread_id, "queuedSubmissionId": entry["id"]},
                            )
                    client.send(
                        {
                            "id": message["id"],
                            "result": {
                                "success": True,
                                "contentItems": [
                                    {"type": "inputText", "text": "T01 synthetic saved"}
                                ],
                            },
                        }
                    )
                elif "id" in message and "method" in message:
                    client.send(
                        {
                            "id": message["id"],
                            "error": {"code": -32601, "message": "Probe forbids this request"},
                        }
                    )
                if message.get("method") == "turn/completed":
                    result["turnCompleted"] = message["params"]
                    break
            result["toolCallbacks"] = callbacks
            if not callbacks or "turnCompleted" not in result:
                raise TimeoutError("A dynamic tool callback and completed turn were required")
            if result["turnCompleted"]["turn"]["status"] != "completed":
                raise RuntimeError("The synthetic turn did not complete successfully")
            result["historyAfterModel"] = client.call(
                "thread/items/list", {"threadId": thread_id, "limit": 2, "sortDirection": "asc"}
            )
            cursor = result["historyAfterModel"].get("nextCursor")
            pages = []
            while cursor:
                page = client.call(
                    "thread/items/list",
                    {"threadId": thread_id, "limit": 2, "sortDirection": "asc", "cursor": cursor},
                )
                pages.append(page)
                cursor = page.get("nextCursor")
            result["historyMorePages"] = pages
            result["queueAfterTurn"] = client.call("thread/queue/list", {"threadId": thread_id})
        return result
    except Exception as exc:
        result["error"] = {"type": type(exc).__name__, "message": str(exc)}
        return result
    finally:
        archived = []
        for thread_id in owned_threads:
            try:
                client.call("thread/archive", {"threadId": thread_id}, timeout=10)
                archived.append(thread_id)
            except (RpcError, EOFError, TimeoutError, queue.Empty):
                pass
        result["archivedThreads"] = archived
        result["notifications"] = client.notifications
        result["serverRequests"] = client.requests
        result["ownedThreads"] = owned_threads
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex", required=True, help="Native codex executable, not a shell shim")
    parser.add_argument("--mode", choices=("metadata", "isolated"), required=True)
    parser.add_argument("--cwd", default=str(Path.cwd()), help="Exact project metadata filter")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--resume-evidence", type=Path, help="Resume only the owned thread in prior probe evidence"
    )
    parser.add_argument(
        "--run-model", action="store_true", help="Run a synthetic tool turn in an owned test thread"
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result = (
        run_metadata(args.codex, args.cwd)
        if args.mode == "metadata"
        else run_isolated(args.codex, args.output, args.run_model, args.resume_evidence)
    )
    result["observedAt"] = datetime.now(UTC).isoformat()
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "mode": args.mode,
                "output": str(args.output),
                "error": result.get("error"),
                "ownedThreads": result.get("ownedThreads", []),
                "threadCount": len(result.get("threads", [])),
            },
            ensure_ascii=False,
        )
    )
    if result.get("error"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
