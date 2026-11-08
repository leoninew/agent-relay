import json
import logging
import os
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from room_fixtures import DemoRoomService, create_room_store
from session_fixtures import FakeSessionDriver

from agent_relay.api import create_app
from agent_relay.config import load_settings
from agent_relay.migrations import run_migrations
from agent_relay.room_errors import RoomConflictError
from agent_relay.room_models import CreateMessage, CreateRoom, CreateTopic, UpdateMember
from agent_relay.room_queries import RoomQueries
from agent_relay.room_service import RoomService
from agent_relay.room_store import SQLiteRoomStore

pytestmark = pytest.mark.usefixtures("migrated_database")


def test_production_starts_empty_and_does_not_invent_sessions() -> None:
    app = create_app(logging.getLogger("tests.room.production"), session_driver=FakeSessionDriver())
    with TestClient(app) as client:
        assert client.get("/api/room").json() == []
        created = client.post("/api/room", json={"name": "Project", "projectPath": "D:/project"})
        room_id = created.json()["id"]
        assert created.status_code == 201
        assert client.get(f"/api/room/{room_id}/session").json() == []

    with TestClient(create_app(logging.getLogger("tests.room.restarted"))) as client:
        assert client.get("/api/room").json() == [created.json()]
        snapshot = client.get(f"/api/room/{room_id}").json()
        assert snapshot["members"] == snapshot["messages"] == snapshot["topics"] == []


def test_resources_and_historical_routing_survive_a_new_process(tmp_path: Path) -> None:
    path = tmp_path / "rooms.sqlite3"
    service = DemoRoomService(create_room_store(path))
    message = service.post_message(
        "agent-relay",
        CreateMessage(
            publication_id=str(uuid4()),
            content="持久化消息",
            topic_ids=["backend"],
            mentioned_member_ids=["frontend-worker"],
        ),
    )
    service.update_member(
        "agent-relay",
        "backend-worker",
        UpdateMember(name="后端成员", topic_ids=["frontend"]),
    )
    expected = service.snapshot("agent-relay").model_dump(mode="json")
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from pathlib import Path; "
            "from agent_relay.room_store import SQLiteRoomStore; "
            "from agent_relay.room_service import RoomService; "
            "print(RoomService(SQLiteRoomStore(Path(sys.argv[1])))"
            ".snapshot('agent-relay').model_dump_json())",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert json.loads(result.stdout) == expected
    assert expected["messages"][-1] == message.model_dump(mode="json")
    assert all(delivery.status == "pending" for delivery in message.deliveries)


def test_existing_app_instances_read_each_others_commits() -> None:
    first_app = create_app(logging.getLogger("tests.room.first"))
    second_app = create_app(logging.getLogger("tests.room.second"))
    with TestClient(first_app) as first, TestClient(second_app) as second:
        room = first.post("/api/room", json={"name": "Shared", "projectPath": "D:/shared"}).json()
        route = f"/api/room/{room['id']}"
        assert second.get("/api/room").json() == [room]
        one = first.post(f"{route}/topic", json={"name": "One"}).json()
        two = second.post(f"{route}/topic", json={"name": "Two"}).json()
        assert first.get(route).json()["topics"] == two["metadata"]["topics"]
        assert [topic["id"] for topic in two["metadata"]["topics"]] == [one["id"], two["id"]]
        assert second.get(route).json() == first.get(route).json()


def test_concurrent_publications_have_unique_sequences_and_no_lost_writes(tmp_path: Path) -> None:
    path = tmp_path / "rooms.sqlite3"
    DemoRoomService(create_room_store(path))

    def publish(index: int) -> int:
        service = RoomService(SQLiteRoomStore(path))
        return service.post_message(
            "agent-relay",
            CreateMessage(
                publication_id=str(uuid4()), content=f"message {index}", topic_ids=["frontend"]
            ),
        ).seq

    with ThreadPoolExecutor(max_workers=4) as pool:
        sequences = list(pool.map(publish, range(12)))
    assert sorted(sequences) == list(range(7, 19))
    snapshot = RoomService(SQLiteRoomStore(path)).snapshot("agent-relay")
    assert len(snapshot.messages) == 18
    assert len({message.id for message in snapshot.messages}) == 18
    assert all(
        len({d.target_member_id for d in m.deliveries}) == len(m.deliveries)
        for m in snapshot.messages
    )


def test_concurrent_normalized_project_creation_reports_conflict(tmp_path: Path) -> None:
    path = tmp_path / "rooms.sqlite3"
    run_migrations(path)

    def create(project_path: str) -> str:
        service = RoomService(SQLiteRoomStore(path))
        try:
            service.create_room(CreateRoom(name="Project", project_path=project_path))
        except RoomConflictError:
            return "conflict"
        return "created"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(create, ["D:/WORK/project/", "d:\\work\\PROJECT"]))
    assert sorted(results) == ["conflict", "created"]
    assert len(RoomService(SQLiteRoomStore(path)).list_rooms()) == 1


def test_delivery_write_failure_rolls_back_message_and_resource_changes(tmp_path: Path) -> None:
    path = tmp_path / "rooms.sqlite3"
    store = create_room_store(path)
    service = DemoRoomService(store)
    before = service.snapshot("agent-relay")
    with (
        pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"),
        store.write() as connection,
    ):
        state = RoomQueries(store).resources_in(connection, "agent-relay")
        original = deepcopy(state)
        state.room.name = "must roll back"
        state.members[0].topic_ids = ["backend"]
        message = service._build_message(
            state,
            seq=RoomQueries.next_message_seq_in(connection, state.room.id),
            content="must roll back",
            topic_ids=["backend"],
            mentioned_member_ids=[],
            sender_id=None,
            sender_name="控制台",
            created_at=datetime.now(UTC),
        )
        # This fails after the room, subscriptions, and message have been written.
        message.deliveries[-1].target_member_id = "missing"
        store.save_resources(connection, state, original)
        store.insert_message(connection, state.room.id, message)
    reopened = RoomService(SQLiteRoomStore(path))
    assert reopened.snapshot("agent-relay") == before
    message = reopened.post_message(
        "agent-relay",
        CreateMessage(publication_id=str(uuid4()), content="after rollback", topic_ids=["backend"]),
    )
    assert message.seq == before.messages[-1].seq + 1


def test_cross_room_subscription_is_rejected_by_database(tmp_path: Path) -> None:
    store = create_room_store(tmp_path / "rooms.sqlite3")
    service = DemoRoomService(store)
    foreign_topic = service.add_topic("housekeeper", CreateTopic(name="Other"))
    before = service.snapshot("agent-relay")
    with (
        pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"),
        store.write() as connection,
    ):
        state = RoomQueries(store).resources_in(connection, "agent-relay")
        original = deepcopy(state)
        state.members[0].topic_ids = [foreign_topic.id]
        store.save_resources(connection, state, original)
    assert service.snapshot("agent-relay") == before


def test_database_path_uses_central_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "configured" / "rooms.sqlite3"
    monkeypatch.setenv("AGENT_RELAY_DATABASE__PATH", str(path))
    settings = load_settings()
    assert settings.database.path == path
    run_migrations(settings.database.path)
    create_app(logging.getLogger("tests.room.configured"), settings=settings)
    assert path.is_file()
