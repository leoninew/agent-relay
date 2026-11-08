"""WebSocket-over-stdio fixture for metadata and queue submission."""

import json
import os
import socket
import sys
from contextlib import suppress
from threading import Event, Thread
from types import SimpleNamespace
from typing import Any, cast

from websockets.exceptions import ConnectionClosed
from websockets.server import ServerProtocol
from websockets.sync.server import ServerConnection

mode = sys.argv[1]
server_socket, bridge = socket.socketpair()


def read_input() -> None:
    try:
        while data := os.read(sys.stdin.fileno(), 65536):
            bridge.sendall(data)
    except OSError:
        pass
    finally:
        with suppress(OSError):
            bridge.shutdown(socket.SHUT_WR)


def write_output() -> None:
    try:
        while data := bridge.recv(65536):
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()
    except OSError:
        pass


Thread(target=read_input, daemon=True).start()
Thread(target=write_output, daemon=True).start()
ws = ServerConnection(
    server_socket,
    ServerProtocol(),
    cast(Any, SimpleNamespace(socket_closed=Event())),
    close_timeout=0.1,
)
ws.handshake(timeout=5)


def row(thread_id: str) -> dict[str, Any]:
    return {
        "id": thread_id,
        "cwd": "D:/project",
        "modelProvider": "test-provider",
        "name": "Worker " + thread_id,
        "status": {
            "type": "idle"
            if mode == "delivery"
            else "active"
            if thread_id == "one"
            else "notLoaded"
        },
    }


try:
    for raw in ws:
        message = json.loads(raw)
        method = message.get("method")
        params = message.get("params", {})
        if method == "initialized":
            continue
        if mode == "timeout" and method != "initialize":
            continue
        if method == "initialize":
            result: dict[str, Any] = {"platformFamily": "windows"}
        elif method == "thread/list":
            assert params["modelProviders"] == []
            assert set(params["sourceKinds"]) == {
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
            }
            assert params["useStateDbOnly"] is True
            assert "cwd" not in params
            if params["archived"]:
                result = {"data": [row("archived")], "nextCursor": None}
            elif not params["cursor"]:
                result = {"data": [row("one")], "nextCursor": "page-two"}
            else:
                result = {"data": [row("two"), row("one")], "nextCursor": None}
            if mode == "cursor":
                result["nextCursor"] = "same-cursor"
            if mode == "malformed":
                result = {"data": "invalid"}
        elif method == "thread/loaded/list":
            result = {"data": ["one"], "nextCursor": None}
        elif method == "thread/read":
            assert params["includeTurns"] is False
            result = {"thread": row(params["threadId"])}
        elif method == "thread/queue/list":
            result = {
                "data": [{"id": "queued-original", "clientUserMessageId": "stable-client-id"}],
                "nextCursor": None,
            }
        elif method == "thread/queue/start":
            assert params["queuedSubmissionId"] == "queued-original"
            result = {"turn": {"id": "turn-original", "status": "inProgress"}}
        elif method == "thread/items/list":
            assert params["sortDirection"] == "desc"
            result = {
                "data": [
                    {
                        "turnId": "turn-original",
                        "item": {"type": "agentMessage", "text": "ignored"},
                    },
                    {
                        "turnId": "turn-original",
                        "item": {
                            "type": "userMessage",
                            "id": "input-original",
                            "clientId": "stable-client-id",
                        },
                    },
                ],
                "nextCursor": None,
            }
        elif method == "thread/queue/add":
            assert params["threadId"] == "original-id"
            assert params["input"] == [{"type": "text", "text": "hello from Relay"}]
            result = {
                "queuedSubmission": {
                    "id": "queued-original",
                    "clientUserMessageId": params["clientUserMessageId"],
                }
            }
        else:
            raise AssertionError("Unexpected operation: " + str(method))
        if mode == "reject" and method != "initialize":
            ws.send(json.dumps({"id": message["id"], "error": {"code": -1, "message": "secret"}}))
        else:
            ws.send(json.dumps({"method": "notification", "params": {}}))
            ws.send(json.dumps({"id": message["id"], "result": result}))
except ConnectionClosed:
    pass
finally:
    ws.close()
