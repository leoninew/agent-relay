import logging
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from room_fixtures import create_room_store
from session_fixtures import FakeQueueDriver, FakeSessionDriver

from agent_relay.api import create_app
from agent_relay.drivers.codex import SessionInfo
from agent_relay.member_sessions import MemberSessions, SessionUnavailableError
from agent_relay.room_errors import RoomConflictError, RoomInputError
from agent_relay.room_models import CreateMember, CreateRoom, CreateTopic
from agent_relay.room_queries import RoomQueries
from agent_relay.room_service import RoomService
from agent_relay.room_state import RoomState
from agent_relay.room_store import SQLiteRoomStore


def setup(tmp_path: Path) -> tuple[MemberSessions, RoomService, FakeSessionDriver, str, str]:
    store = create_room_store(tmp_path / "rooms.sqlite3")
    rooms = RoomService(store)
    room = rooms.create_room(CreateRoom(name="Project", project_path="D:/project"))
    topic = rooms.add_topic(room.id, CreateTopic(name="Work"))
    driver = FakeSessionDriver(
        [
            SessionInfo("one", "D:\\PROJECT\\", "provider-a", "Existing", "active"),
            SessionInfo("two", "d:/project", "provider-b", "History", "notLoaded", True),
            SessionInfo("child", "d:/project/subdir", "provider-a", "Child", "idle"),
            SessionInfo("other", "d:/other", "provider-a", "Other", "idle"),
        ]
    )
    return MemberSessions(store, driver), rooms, driver, room.id, topic.id


def request(topic_id: str, **fields: str) -> CreateMember:
    return CreateMember(
        name="Worker",
        topic_ids=[topic_id, topic_id],
        session_id=fields.get("session_id", "one"),
    )


def test_directory_discovery_and_join_bind_the_original_session(tmp_path: Path) -> None:
    members, rooms, driver, room_id, topic_id = setup(tmp_path)
    candidates = members.candidates(room_id)
    assert [info.id for info in candidates] == ["one", "two"]
    assert candidates[1].archived and candidates[1].presence == "unknown"
    assert [member.id for member in rooms.snapshot(room_id).members] == ["user"]
    member = members.add(room_id, request(topic_id))
    assert member.session_id == "one"
    assert member.topic_ids == [topic_id]
    assert member.name == "Worker" and driver.sessions["one"].name == "Existing"
    assert member.presence == "busy" and member.activity_source == "codex"
    assert members.candidates(room_id)[0].member_id == member.id
    current = rooms.snapshot(room_id).members[0]
    assert current.model_dump(exclude={"observed_at"}) == member.model_dump(
        exclude={"session", "metadata", "observed_at"}
    )
    assert current.observed_at is not None and member.observed_at is not None
    assert current.observed_at >= member.observed_at
    assert member.session.name == "Existing"
    with pytest.raises(RoomConflictError):
        members.add(room_id, request(topic_id))
    with pytest.raises(RoomConflictError, match="会话已加入"):
        members.add(room_id, request(topic_id).model_copy(update={"name": "Another"}))


def test_empty_list_and_failure_do_not_create_candidates_or_members(tmp_path: Path) -> None:
    members, rooms, driver, room_id, topic_id = setup(tmp_path)
    driver.sessions.clear()
    assert members.candidates(room_id) == []
    driver.error = TimeoutError("secret upstream detail")
    with pytest.raises(SessionUnavailableError):
        members.candidates(room_id)
    with pytest.raises(SessionUnavailableError):
        members.add(room_id, request(topic_id))
    assert [member.id for member in rooms.snapshot(room_id).members] == ["user"]


def test_posix_paths_remain_case_sensitive(tmp_path: Path) -> None:
    members, rooms, driver, _, _ = setup(tmp_path)
    room = rooms.create_room(CreateRoom(name="Linux", project_path="/Work/project"))
    driver.sessions = {
        info.id: info
        for info in [
            SessionInfo("exact", "/Work/project/", "a", "Exact", "idle"),
            SessionInfo("wrong-case", "/work/project", "a", "Wrong", "idle"),
        ]
    }
    assert [info.id for info in members.candidates(room.id)] == ["exact"]


def test_running_member_observations_refresh_when_the_original_session_changes_state(
    tmp_path: Path,
) -> None:
    members, rooms, driver, room_id, topic_id = setup(tmp_path)
    member = members.add(room_id, request(topic_id))
    assert member.presence == "busy"
    driver.sessions["one"] = SessionInfo("one", "D:/project", "provider-a", "Existing", "notLoaded")
    candidate = members.candidates(room_id)[0]
    assert candidate.presence == "unknown" and not candidate.usable
    assert candidate.unavailable_reason and "独立实例" in candidate.unavailable_reason
    current = RoomQueries(rooms.store).metadata(room_id).members[0]
    assert current.presence == "unknown"
    assert current.activity == candidate.unavailable_reason
    driver.sessions["one"] = SessionInfo("one", "D:/project", "provider-a", "Existing", "idle")
    assert members.candidates(room_id)[0].usable
    assert RoomQueries(rooms.store).metadata(room_id).members[0].presence == "available"


def test_join_revalidates_directory_id_topics_and_does_not_write_on_failure(tmp_path: Path) -> None:
    members, rooms, driver, room_id, topic_id = setup(tmp_path)
    with pytest.raises(RoomInputError, match="不属于"):
        members.add(room_id, request(topic_id, session_id="other"))
    with pytest.raises(RoomInputError, match="不属于"):
        members.add(room_id, request(topic_id, session_id="child"))
    driver.sessions["one"] = driver.sessions["two"]
    with pytest.raises(SessionUnavailableError, match="身份不匹配"):
        members.add(room_id, request(topic_id))
    with pytest.raises(RoomInputError, match="话题不存在"):
        members.add(room_id, request("missing"))
    assert [member.id for member in rooms.snapshot(room_id).members] == ["user"]


def test_concurrent_join_has_one_persistent_binding(tmp_path: Path) -> None:
    members, rooms, driver, room_id, topic_id = setup(tmp_path)
    second = MemberSessions(SQLiteRoomStore(members.store.path), driver)

    def join(index: int) -> str:
        try:
            [members, second][index % 2].add(room_id, request(topic_id))
            return "joined"
        except RoomConflictError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(join, range(8)))
    assert results.count("joined") == 1 and results.count("conflict") == 7
    assert len(rooms.snapshot(room_id).members) == 2


def test_failed_local_commit_rolls_back_session_and_member(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    members, rooms, _, room_id, topic_id = setup(tmp_path)
    original = members.store.save_resources

    def fail(connection: sqlite3.Connection, current: RoomState, before: RoomState) -> None:
        original(connection, current, before)
        raise sqlite3.OperationalError("injected failure")

    monkeypatch.setattr(members.store, "save_resources", fail)
    with pytest.raises(sqlite3.OperationalError):
        members.add(room_id, request(topic_id))
    assert [member.id for member in rooms.snapshot(room_id).members] == ["user"]
    assert RoomQueries(rooms.store).metadata(room_id).sessions == []


def test_api_preserves_bindings_on_restart_and_hides_upstream_errors(tmp_path: Path) -> None:
    members, rooms, driver, room_id, topic_id = setup(tmp_path)
    route = f"/api/room/{room_id}"
    logger = logging.getLogger("tests.member-sessions")
    with TestClient(
        create_app(
            logger, room_service=rooms, queue_driver=FakeQueueDriver(), session_driver=driver
        )
    ) as client:
        assert driver.listed == 0 and driver.inspected == []
        response = client.post(route + "/member", json=request(topic_id).model_dump(by_alias=True))
        assert response.status_code == 201
        member = response.json()
        session = member.pop("session")
        assert session["name"] == "Existing"
        assert client.get(route + "/session").json()[0]["memberId"] == member["id"]
        member = client.get(route).json()["members"][0]
        assert client.get(route + "/member-operation/old").status_code == 404
    driver = FakeSessionDriver()
    restored = RoomService(SQLiteRoomStore(members.store.path))
    with TestClient(
        create_app(
            logger, room_service=restored, queue_driver=FakeQueueDriver(), session_driver=driver
        )
    ) as client:
        assert [
            item for item in client.get(route).json()["members"] if item["kind"] == "agent"
        ] == [member]
        assert client.get(route).json()["sessions"][0]["name"] == "Existing"
        assert driver.listed == 0 and driver.inspected == []
        driver.error = OSError("secret path and token")
        failed = client.get(route + "/session", headers={"X-Request-Id": "req_session"})
        assert failed.status_code == 503
        assert failed.json()["code"] == "service_unavailable"
        assert failed.json()["requestId"] == "req_session"
        assert "secret" not in failed.text
        assert [
            item for item in client.get(route).json()["members"] if item["kind"] == "agent"
        ] == [member]
