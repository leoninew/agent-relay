import json
import logging
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from room_fixtures import DemoRoomService, create_room_store, open_room_store
from session_fixtures import FakeSessionDriver
from sqlalchemy.exc import IntegrityError

from agent_relay.application.rooms.contracts import (
    CreateMessage,
    CreateRoom,
    CreateTopic,
    UpdateMember,
)
from agent_relay.application.rooms.service import RoomService
from agent_relay.bootstrap.config import load_settings
from agent_relay.bootstrap.http import create_app
from agent_relay.domain.rooms.errors import RoomConflictError
from agent_relay.domain.rooms.rules import build_message
from agent_relay.infrastructure.persistence.migrations import run_migrations

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
        assert snapshot["messages"] == []
        assert [topic["name"] for topic in snapshot["topics"]] == ["产品", "架构", "开发", "测试"]
        assert len(snapshot["members"]) == 1
        assert snapshot["members"][0]["kind"] == "human"
        assert snapshot["members"][0]["name"] == "你"
        assert snapshot["members"][0]["sessionId"] is None


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
            "from agent_relay.infrastructure.persistence.database import Database; "
            "from agent_relay.infrastructure.persistence.room_store import SQLAlchemyRoomStore; "
            "from agent_relay.application.rooms.service import RoomService; "
            "database = Database(Path(sys.argv[1])); "
            "print(RoomService(SQLAlchemyRoomStore(database))"
            ".snapshot('agent-relay').model_dump_json()); database.close()",
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
        assert [topic["name"] for topic in two["metadata"]["topics"]] == [
            "产品",
            "架构",
            "开发",
            "测试",
            "One",
            "Two",
        ]
        assert [topic["id"] for topic in two["metadata"]["topics"]][-2:] == [one["id"], two["id"]]
        assert second.get(route).json() == first.get(route).json()


def test_concurrent_publications_have_unique_sequences_and_no_lost_writes(tmp_path: Path) -> None:
    path = tmp_path / "rooms.sqlite3"
    DemoRoomService(create_room_store(path))

    def publish(index: int) -> int:
        service = RoomService(open_room_store(path))
        return service.post_message(
            "agent-relay",
            CreateMessage(
                publication_id=str(uuid4()), content=f"message {index}", topic_ids=["frontend"]
            ),
        ).seq

    with ThreadPoolExecutor(max_workers=4) as pool:
        sequences = list(pool.map(publish, range(12)))
    assert sorted(sequences) == list(range(7, 19))
    snapshot = RoomService(open_room_store(path)).snapshot("agent-relay")
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
        service = RoomService(open_room_store(path))
        try:
            service.create_room(CreateRoom(name="Project", project_path=project_path))
        except RoomConflictError:
            return "conflict"
        return "created"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(create, ["D:/WORK/project/", "d:\\work\\PROJECT"]))
    assert sorted(results) == ["conflict", "created"]
    assert len(RoomService(open_room_store(path)).list_rooms()) == 1


def test_delivery_write_failure_rolls_back_message_and_resource_changes(tmp_path: Path) -> None:
    path = tmp_path / "rooms.sqlite3"
    store = create_room_store(path)
    service = DemoRoomService(store)
    before = service.snapshot("agent-relay")
    with (
        pytest.raises(IntegrityError, match="FOREIGN KEY"),
        store.write_rooms() as repository,
    ):
        state = repository.resources("agent-relay")
        original = deepcopy(state)
        state.room.name = "must roll back"
        state.members[0].topic_ids = ["backend"]
        message = build_message(
            state,
            seq=repository.next_message_seq(state.room.id),
            content="must roll back",
            topic_ids=["backend"],
            mentioned_member_ids=[],
            sender_id="user",
            sender_name="你",
            created_at=datetime.now(UTC),
        )
        # This fails after the room, subscriptions, and message have been written.
        message.deliveries[-1].target_member_id = "missing"
        repository.save_resources(state, original)
        repository.insert_message(state.room.id, message)
    reopened = RoomService(open_room_store(path))
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
        pytest.raises(IntegrityError, match="FOREIGN KEY"),
        store.write_rooms() as repository,
    ):
        state = repository.resources("agent-relay")
        original = deepcopy(state)
        state.members[0].topic_ids = [foreign_topic.id]
        repository.save_resources(state, original)
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
