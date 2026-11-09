"""Verify production Relay delivery against an owned shared-daemon session.

Uses a temporary Relay database, real HTTP handlers via TestClient, and synthetic
messages. A prior interrupted turn makes a fresh submission exercise FIFO queue
activation. User work sessions and development servers are never changed.
"""

from __future__ import annotations

import argparse
import json
import logging
import queue
import tempfile
import time
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from codex_capabilities import Client, tool_spec
from fastapi.testclient import TestClient

from agent_relay.bootstrap.config import load_settings
from agent_relay.bootstrap.http import create_app
from agent_relay.infrastructure.codex.driver import _launch_command
from agent_relay.infrastructure.persistence.migrations import run_migrations
from agent_relay.infrastructure.persistence.store import SQLiteRoomStore


def run(output: Path) -> dict[str, Any]:
    workspace = Path(tempfile.mkdtemp(prefix="agent-relay-n5-http-"))
    settings = load_settings()
    client = Client(_launch_command(settings.codex.command), proxy=True)
    thread_id: str | None = None
    evidence: dict[str, Any] = {
        "observedAt": datetime.now(UTC).isoformat(),
        "scope": "Temporary Relay database, production HTTP handlers, owned Codex session",
        "workspace": str(workspace),
    }
    try:
        client.initialize()
        started = client.call(
            "thread/start",
            {
                "cwd": str(workspace),
                "historyMode": "paginated",
                "serviceName": "agent-relay-n5-http",
                "baseInstructions": (
                    "Synthetic message delivery verification. Do not read files, run commands, "
                    "call HTTP, or publish any messages. Only use room_publish_probe if the "
                    "current input explicitly requests the synthetic gate. For each later incoming "
                    "JSON chatroom message, reply briefly with its content token, without tools."
                ),
                "dynamicTools": [tool_spec()],
            },
        )
        thread_id = started["thread"]["id"]
        evidence["threadId"] = thread_id
        client.call("thread/name/set", {"threadId": thread_id, "name": "[Relay N5 HTTP probe]"})
        client.call(
            "thread/queue/add",
            {
                "threadId": thread_id,
                "clientUserMessageId": "gate-" + uuid4().hex,
                "input": [
                    {
                        "type": "text",
                        "text": "Call room_publish_probe once with "
                        "content='synthetic gate', topicIds=['probe'], mentionedMemberIds=[].",
                    }
                ],
            },
        )
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            try:
                event = client.receive(timeout=min(10, deadline - time.monotonic()))
            except queue.Empty:
                continue
            if event.get("method") == "item/tool/call":
                params = event["params"]
                assert params["threadId"] == thread_id
                client.call("turn/interrupt", {"threadId": thread_id, "turnId": params["turnId"]})
                break
        else:
            raise TimeoutError("Synthetic gate not reached")
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            state = client.call("thread/read", {"threadId": thread_id, "includeTurns": False})
            if state["thread"]["status"]["type"] == "idle":
                break
            time.sleep(0.2)
        evidence["beforePublication"] = state["thread"]["status"]
        database = workspace / "relay.sqlite3"
        run_migrations(database)
        isolated = settings.model_copy(
            update={"database": settings.database.model_copy(update={"path": database})}
        )
        app = create_app(logging.getLogger("relay.n5.smoke"), settings=isolated)
        with TestClient(app) as http:
            room_response = http.post(
                "/api/room", json={"name": "N5 isolated", "projectPath": str(workspace)}
            )
            assert room_response.status_code == 201
            room_id = room_response.json()["id"]
            route = f"/api/room/{room_id}"
            topic = http.post(route + "/topic", json={"name": "Probe"}).json()
            candidates = http.get(route + "/session").json()
            candidate = next(row for row in candidates if row["id"] == thread_id)
            evidence["candidate"] = candidate
            assert candidate["usable"]
            joined = http.post(
                route + "/member",
                json={"sessionId": thread_id, "name": "Target", "topicIds": [topic["id"]]},
            )
            assert joined.status_code == 201
            member = joined.json()
            publications: list[str] = []
            for mode in ("topic", "mention", "both"):
                publication_id = uuid4().hex
                request = {
                    "publicationId": publication_id,
                    "content": "N5_" + mode.upper() + "_" + uuid4().hex[:8],
                    "topicIds": [topic["id"]] if mode != "mention" else [],
                    "mentionedMemberIds": [member["id"]] if mode != "topic" else [],
                }
                response = http.post(route + "/message", json=request)
                assert response.status_code == 201
                message = response.json()
                assert message["senderId"] is None and message["recipientIds"] == [member["id"]]
                assert len(message["deliveries"]) == 1
                replay = http.post(route + "/message", json=request)
                assert replay.json()["id"] == message["id"]
                publications.append(publication_id)
            deadline = time.monotonic() + 300
            results = []
            while time.monotonic() < deadline:
                results = [
                    http.get(route + "/publication/" + publication).json()
                    for publication in publications
                ]
                if all(row["deliveries"][0]["status"] == "received" for row in results):
                    break
                time.sleep(1)
            evidence["messages"] = results
            assert all(row["deliveries"][0]["status"] == "received" for row in results)
            assert any(row["deliveries"][0]["activationAttemptedAt"] for row in results)
            metadata = http.get(route + "/metadata").json()
            assert metadata["summary"]["totalMessages"] == metadata["summary"]["receivedCount"] == 3
            evidence["summary"] = metadata["summary"]
            evidence["allOriginalInputsConfirmed"] = True
        # A new Store validates that the input evidence is durable.
        reopened = SQLiteRoomStore(database)
        evidence["unconfirmedAfterReopen"] = reopened.unconfirmed_inputs()
        assert not evidence["unconfirmedAfterReopen"]
    except Exception as exc:
        evidence["error"] = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        if thread_id is not None:
            with suppress(Exception):
                client.call("thread/archive", {"threadId": thread_id})
                evidence["archivedOwnedSession"] = True
        client.close()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return evidence


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-model", action="store_true", required=True)
    args = parser.parse_args()
    result = run(args.output)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "error": result.get("error"),
                "received": result.get("allOriginalInputsConfirmed"),
            },
            ensure_ascii=False,
        )
    )
    if result.get("error"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
