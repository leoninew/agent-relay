"""Read-only Codex discovery plus member binding in a temporary Relay database."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

from fastapi.testclient import TestClient

from agent_relay.bootstrap.config import load_settings
from agent_relay.bootstrap.http import create_app
from agent_relay.infrastructure.codex.driver import CodexDriver, ProxyRpc
from agent_relay.infrastructure.persistence.migrations import run_migrations
from agent_relay.infrastructure.persistence.store import SQLiteRoomStore


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex", type=Path, help="Override the configured Codex executable")
    parser.add_argument("--cwd", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    workspace = Path(tempfile.mkdtemp(prefix="relay-member-binding-"))
    database_path = workspace / "rooms.sqlite3"
    run_migrations(database_path)
    store = SQLiteRoomStore(database_path)
    settings = load_settings(root)
    command = [str(args.codex), "app-server", "proxy"] if args.codex else settings.codex.command
    driver = CodexDriver(command, settings.codex.rpc_timeout)
    requests: Counter[str] = Counter()
    original = ProxyRpc.call

    def metadata_only(rpc: ProxyRpc, method: str, params: dict[str, Any]) -> dict[str, Any]:
        assert method in {"initialize", "thread/list", "thread/read"}, method
        requests[method] += 1
        return original(rpc, method, params)

    with (
        patch.object(ProxyRpc, "call", metadata_only),
        TestClient(
            create_app(logging.getLogger("member-smoke"), store=store, session_driver=driver)
        ) as client,
    ):
        room = client.post(
            "/api/room", json={"name": "Metadata smoke", "projectPath": str(args.cwd)}
        )
        assert room.status_code == 201
        room_id = room.json()["id"]
        route = f"/api/room/{room_id}"
        candidates = client.get(route + "/session")
        assert candidates.status_code == 200
        rows = candidates.json()
        assert rows, "Smoke requires an existing session in the specified directory"
        selected = next((row for row in rows if not row["archived"]), rows[0])
        topic = client.post(route + "/topic", json={"name": "Test"}).json()
        request = {
            "sessionId": selected["id"],
            "name": "Bound test member",
            "topicIds": [topic["id"]],
        }
        response = client.post(route + "/member", json=request)
        assert response.status_code == 201, response.text
        member = response.json()
        assert member["sessionId"] == selected["id"]
        refreshed = client.get(route + "/session").json()
        assert (
            next(row for row in refreshed if row["id"] == selected["id"])["memberId"]
            == member["id"]
        )

    code = (
        "from pathlib import Path; "
        "from agent_relay.infrastructure.persistence.store import SQLiteRoomStore; "
        "from agent_relay.application.rooms.service import RoomService; import sys; "
        "print(RoomService(SQLiteRoomStore(Path(sys.argv[1]))).snapshot(sys.argv[2])."
        "members[0].session_id)"
    )
    reloaded = subprocess.run(
        [sys.executable, "-c", code, str(store.path), room_id],
        check=True,
        capture_output=True,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    assert reloaded.stdout.strip() == selected["id"]
    files = [
        "src/agent_relay/infrastructure/codex/driver.py",
        "src/agent_relay/application/members/service.py",
        "src/agent_relay/infrastructure/persistence/store.py",
        "src/agent_relay/domain/rooms/models.py",
        "src/agent_relay/infrastructure/persistence/migrations.py",
        "migrations/sqlite/sql/0001_baseline/01_schema.up.sql",
        "migrations/sqlite/versions/0001_baseline.py",
        "scripts/probes/member_session_smoke.py",
    ]
    evidence = {
        "recordedAt": datetime.now(UTC).isoformat(),
        "scope": "Existing-session metadata only; all Relay writes use a temporary database",
        "configuredCommandUsed": args.codex is None,
        "defaultCodexCommandUsed": command == ["codex", "app-server", "proxy"],
        "matchingSessionCount": len(rows),
        "selectedThreadHash": hashlib.sha256(selected["id"].encode()).hexdigest(),
        "sameThreadBound": True,
        "joinedCandidateMarked": True,
        "sameThreadAfterNewProcess": True,
        "codexRpcMethods": dict(requests),
        "createdThreads": 0,
        "resumedThreads": 0,
        "submittedMessages": 0,
        "sourceSha256": {
            name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in files
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "matchingSessionCount": len(rows),
                "sameThreadBound": True,
                "sameThreadAfterNewProcess": True,
                "codexRpcMethods": dict(requests),
            }
        )
    )


if __name__ == "__main__":
    main()
