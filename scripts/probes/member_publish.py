"""Verify member HTTP publication using only newly owned Codex sessions."""

from __future__ import annotations

import argparse
import json
import logging
import tempfile
from contextlib import suppress
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from time import monotonic, sleep
from uuid import uuid4

from fastapi.testclient import TestClient

from agent_relay.api import create_app
from agent_relay.config import ServerSettings, load_settings
from agent_relay.drivers.codex import ProxyRpc
from agent_relay.migrations import run_migrations
from agent_relay.room_service import RoomService
from agent_relay.room_store import SQLiteRoomStore


def run(output: Path) -> None:
    workspace = Path(tempfile.mkdtemp(prefix="agent-relay-n2-"))
    settings = load_settings()
    database = settings.database.model_copy(update={"path": workspace / "relay.sqlite3"})
    run_migrations(database.path)
    owned: list[str] = []
    with ProxyRpc(settings.codex.command, settings.codex.rpc_timeout) as rpc:
        try:
            for name, instructions in [
                (
                    "Sender",
                    "You are an isolated Relay integration test sender. On receiving a chat "
                    "message, follow its content: use your normal shell/exec tool and Python "
                    "standard-library HTTP to publish exactly once to the provided local "
                    "publish.url using JSON Content-Type from publish.headers. "
                    "Use the requested publicationId, "
                    "content and topicIds, and set replyToMessageId to the envelope messageId. "
                    "Do not access other files or networks, use MCP, or spawn agents. "
                    "After successful HTTP publication, reply only 'N2 published'.",
                ),
                (
                    "Receiver",
                    "You are an isolated Relay test receiver. Do not call any tools or publish "
                    "a chat message. Reply only 'N2 received'.",
                ),
            ]:
                started = rpc.call(
                    "thread/start",
                    {
                        "cwd": str(workspace),
                        "approvalPolicy": "never",
                        "sandbox": "danger-full-access",
                        "historyMode": "paginated",
                        "serviceName": "agent-relay-n2-probe",
                        "baseInstructions": instructions,
                    },
                )
                thread_id = started["thread"]["id"]
                owned.append(thread_id)
                rpc.call(
                    "thread/name/set",
                    {"threadId": thread_id, "name": f"[Relay N2 owned probe] {name}"},
                )

            # A temporary HTTP bridge lets the model call the ASGI test app from its shell.
            class Handler(BaseHTTPRequestHandler):
                def do_GET(self) -> None:
                    self.forward()

                def do_POST(self) -> None:
                    self.forward()

                def forward(self) -> None:
                    body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                    response = client.request(
                        self.command, self.path, content=body, headers=dict(self.headers)
                    )
                    self.send_response(response.status_code)
                    for name in ("Content-Type", "X-Request-Id"):
                        if name in response.headers:
                            self.send_header(name, response.headers[name])
                    self.send_header("Content-Length", str(len(response.content)))
                    self.end_headers()
                    self.wfile.write(response.content)

                def log_message(self, format: str, *args: object) -> None:
                    pass

            with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as http:
                public_url = f"http://127.0.0.1:{http.server_port}"
                server = ServerSettings.model_validate(
                    {**settings.server.model_dump(), "public_url": public_url, "reload": False}
                )
                settings = settings.model_copy(update={"database": database, "server": server})
                with TestClient(
                    create_app(logging.getLogger("relay.n2.probe"), settings=settings)
                ) as client:
                    thread = Thread(target=http.serve_forever, daemon=True)
                    thread.start()
                    try:
                        room = client.post(
                            "/api/room", json={"name": "N2 probe", "projectPath": str(workspace)}
                        )
                        room.raise_for_status()
                        room_id = room.json()["id"]
                        route = f"/api/room/{room_id}"
                        topic = client.post(route + "/topic", json={"name": "Probe"})
                        topic.raise_for_status()
                        topic_id = topic.json()["id"]
                        member_ids = []
                        for name, session_id in zip(("Sender", "Receiver"), owned, strict=True):
                            member = client.post(
                                route + "/member",
                                json={
                                    "sessionId": session_id,
                                    "name": name,
                                    "topicIds": [topic_id],
                                },
                            )
                            member.raise_for_status()
                            member_ids.append(member.json()["id"])
                        publication_id = str(uuid4())
                        expected = {
                            "publicationId": publication_id,
                            "content": "N2 real member publication",
                            "topicIds": [topic_id],
                        }
                        posted = client.post(
                            route + "/message",
                            json={
                                "publicationId": str(uuid4()),
                                "content": "Publish exactly this JSON via publish.url, adding "
                                "replyToMessageId from the envelope messageId: "
                                + json.dumps(expected),
                                "mentionedMemberIds": [member_ids[0]],
                            },
                        )
                        posted.raise_for_status()
                        deadline = monotonic() + 150
                        member_message = None
                        while monotonic() < deadline:
                            snapshot = client.get(route).json()
                            member_message = next(
                                (
                                    message
                                    for message in snapshot["messages"]
                                    if message["publicationId"] == publication_id
                                ),
                                None,
                            )
                            if member_message is not None and all(
                                d["status"] in {"queued", "rejected", "unknown"}
                                for d in member_message["deliveries"]
                            ):
                                break
                            sleep(0.2)
                        evidence = {
                            "observedAt": datetime.now(UTC).isoformat(),
                            "scope": "Only two newly owned threads; no dynamicTools registered",
                            "threadIds": owned,
                            "workspace": str(workspace),
                            "consoleMessage": client.get(
                                route + "/publication/" + posted.json()["publicationId"]
                            ).json(),
                            "memberMessage": member_message,
                            "summary": client.get(route).json()["summary"],
                        }
                        output.parent.mkdir(parents=True, exist_ok=True)
                        output.write_text(
                            json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8",
                        )
                        assert member_message is not None, f"No member callback; see {output}"
                        assert member_message["senderId"] == member_ids[0]
                        assert member_message["recipientIds"] == [member_ids[1]]
                        assert member_message["replyToMessageId"] == posted.json()["id"]
                        assert member_message["content"] == expected["content"]
                        assert all(d["status"] == "queued" for d in member_message["deliveries"])
                        restored = RoomService(SQLiteRoomStore(database.path)).snapshot(room_id)
                        assert restored.messages[-1].id == member_message["id"]
                        print(
                            json.dumps(
                                {"memberPublished": True, "queued": True, "output": str(output)}
                            )
                        )
                    finally:
                        http.shutdown()
                        thread.join(timeout=5)
        finally:
            for thread_id in owned:
                with suppress(Exception):
                    rpc.call("thread/archive", {"threadId": thread_id})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-model", action="store_true", required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    run(arguments.output)
