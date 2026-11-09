"""Exercise Relay HTTP -> shared Codex queue using only a newly owned thread."""

from __future__ import annotations

import argparse
import json
import logging
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic, sleep
from uuid import uuid4

from fastapi.testclient import TestClient

from agent_relay.application.rooms.service import RoomService
from agent_relay.bootstrap.config import load_settings
from agent_relay.bootstrap.http import create_app
from agent_relay.infrastructure.codex.driver import ProxyRpc
from agent_relay.infrastructure.persistence.migrations import run_migrations
from agent_relay.infrastructure.persistence.store import SQLiteRoomStore


def run(output: Path) -> None:
    workspace = Path(tempfile.mkdtemp(prefix="agent-relay-n1-"))
    settings = load_settings()
    database = settings.database.model_copy(update={"path": workspace / "relay.sqlite3"})
    settings = settings.model_copy(update={"database": database})
    run_migrations(database.path)
    with ProxyRpc(settings.codex.command, settings.codex.rpc_timeout) as rpc:
        started = rpc.call(
            "thread/start",
            {
                "cwd": str(workspace),
                "approvalPolicy": "never",
                "sandbox": "read-only",
                "historyMode": "paginated",
                "serviceName": "agent-relay-n1-probe",
                "baseInstructions": (
                    "This is an isolated Relay queue verification. Do not use tools, execute "
                    "commands, access files/networks, or spawn agents. For each chat message "
                    "reply only: Relay N1 received."
                ),
            },
        )
        thread_id = started["thread"]["id"]
        rpc.call("thread/name/set", {"threadId": thread_id, "name": "[Relay N1 owned probe]"})
    evidence: dict[str, object] = {
        "observedAt": datetime.now(UTC).isoformat(),
        "workspace": str(workspace),
        "threadId": thread_id,
        "scope": "Newly owned thread only; no existing work sessions",
    }
    with TestClient(create_app(logging.getLogger("relay.n1.probe"), settings=settings)) as client:
        room_response = client.post(
            "/api/room", json={"name": "N1 probe", "projectPath": str(workspace)}
        )
        room_response.raise_for_status()
        room_id = room_response.json()["id"]
        route = f"/api/room/{room_id}"
        topic_response = client.post(route + "/topic", json={"name": "Probe"})
        topic_response.raise_for_status()
        topic_id = topic_response.json()["id"]
        member_response = client.post(
            route + "/member",
            json={"sessionId": thread_id, "name": "Probe member", "topicIds": [topic_id]},
        )
        member_response.raise_for_status()
        member_id = member_response.json()["id"]
        publications = []
        for topics, mentions in [([topic_id], []), ([], [member_id]), ([topic_id], [member_id])]:
            request = {
                "publicationId": str(uuid4()),
                "content": "仅验证入队，请只回复 Relay N1 received。",
                "topicIds": topics,
                "mentionedMemberIds": mentions,
            }
            response = client.post(route + "/message", json=request)
            response.raise_for_status()
            message = response.json()
            assert len(message["deliveries"]) == 1
            publications.append(message)
            replay = client.post(route + "/message", json=request)
            replay.raise_for_status()
            assert replay.json()["id"] == message["id"]
        deadline = monotonic() + 100
        results = []
        while monotonic() < deadline:
            results = [
                client.get(route + "/publication/" + m["publicationId"]).json()
                for m in publications
            ]
            states = [d["status"] for m in results for d in m["deliveries"]]
            if all(state == "queued" for state in states) or any(
                state in {"unknown", "rejected"} for state in states
            ):
                break
            sleep(0.1)
        evidence["publications"] = results
        evidence["allQueued"] = all(
            d["status"] == "queued" for m in results for d in m["deliveries"]
        )
        evidence["summary"] = client.get(route).json()["summary"]
    restored = RoomService(SQLiteRoomStore(database.path))
    evidence["persistentLookupMatches"] = all(
        restored.publication(room_id, m["publicationId"]).model_dump(mode="json", by_alias=True)
        == m
        for m in results
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                key: evidence[key]
                for key in ("threadId", "allQueued", "persistentLookupMatches", "summary")
            },
            ensure_ascii=False,
        )
    )
    assert evidence["allQueued"] is True, f"See queue results in {output}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-model", action="store_true", required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    run(arguments.output)
