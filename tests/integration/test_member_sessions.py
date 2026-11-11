import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from threading import Event

import pytest
from fastapi.testclient import TestClient
from room_fixtures import StoredMemberSessions as MemberSessions
from room_fixtures import StoredRoomService as RoomService
from room_fixtures import create_room_store, open_room_store
from session_fixtures import FakeQueueDriver, FakeSessionDriver

from agent_relay.application.members.sessions import SessionInfo, SessionUnavailableError
from agent_relay.application.rooms.contracts import (
    CreateMember,
    CreateRoom,
    CreateTopic,
    UpdateMember,
)
from agent_relay.bootstrap.http import create_app
from agent_relay.domain.rooms.errors import RoomConflictError, RoomInputError
from agent_relay.domain.rooms.state import RoomState
from agent_relay.infrastructure.dispatch.presence import (
    MemberPresenceRunner as MemberPresenceService,
)
from agent_relay.infrastructure.persistence.repositories.rooms import SQLAlchemyRoomRepository
from agent_relay.infrastructure.persistence.room_queries import SQLAlchemyRoomQueries as RoomQueries


def setup(tmp_path: Path) -> tuple[MemberSessions, RoomService, FakeSessionDriver, str, str]:
    store = create_room_store(tmp_path / "rooms.sqlite3")
    rooms = RoomService(store)
    room = rooms.create_room(CreateRoom(name="Project", project_path="D:/project"))
    topic = rooms.add_topic(room.id, CreateTopic(name="Work"))
    driver = FakeSessionDriver(
        [
            SessionInfo("one", "D:\\PROJECT\\", "provider-a", "Existing", "active"),
            SessionInfo("two", "d:/project", "provider-b", "History", "unavailable", True),
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
    driver.sessions["one"] = SessionInfo(
        "one", "D:/project", "provider-a", "Existing", "unavailable"
    )
    candidate = members.candidates(room_id)[0]
    assert candidate.presence == "unknown" and not candidate.usable
    assert candidate.unavailable_reason and "独立实例" in candidate.unavailable_reason
    current = RoomQueries(rooms.store.database).metadata(room_id).members[0]
    assert current.presence == "unknown"
    assert current.activity == candidate.unavailable_reason
    driver.sessions["one"] = SessionInfo("one", "D:/project", "provider-a", "Existing", "idle")
    assert members.candidates(room_id)[0].usable
    assert RoomQueries(rooms.store.database).metadata(room_id).members[0].presence == "available"


def test_presence_worker_updates_joined_members_and_emits_events_without_listing_sessions(
    tmp_path: Path,
) -> None:
    members, rooms, driver, room_id, topic_id = setup(tmp_path)
    member = members.add(room_id, request(topic_id))
    rooms.update_member(room_id, member.id, UpdateMember(name="Renamed", topic_ids=[topic_id]))
    queries = RoomQueries(rooms.store.database)
    cursor = queries.events(room_id, 0).next_event_id
    driver.inspected.clear()
    worker = MemberPresenceService(members, logging.getLogger("tests.member-presence"))
    driver.sessions["one"] = replace(driver.sessions["one"], status="idle", name="Renamed session")

    worker.refresh()

    current = queries.metadata(room_id).members[0]
    assert current.presence == "available"
    assert current.name == "Renamed" and current.topic_ids == [topic_id]
    assert queries.metadata(room_id).sessions[0].presence == "available"
    assert queries.metadata(room_id).sessions[0].name == "Renamed session"
    assert {event.kind for event in queries.events(room_id, cursor).events} == {"member", "session"}
    assert driver.inspected == ["one"] and driver.listed == 0
    driver.sessions["one"] = replace(driver.sessions["one"], status="active")
    worker.refresh()
    assert queries.metadata(room_id).members[0].presence == "busy"
    rooms.delete_member(room_id, member.id)
    worker.refresh()
    assert driver.inspected == ["one", "one"]


@pytest.mark.parametrize("failure", ["unavailable", "identity", "directory"])
def test_presence_worker_marks_failed_observations_unknown_and_continues_other_members(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    members, rooms, driver, room_id, topic_id = setup(tmp_path)
    member = members.add(room_id, request(topic_id))
    driver.sessions["two"] = replace(driver.sessions["two"], status="active", archived=False)
    other = members.add(room_id, CreateMember(name="Other", session_id="two", topic_ids=[]))
    driver.sessions["two"] = replace(driver.sessions["two"], status="idle")
    inspect = driver.inspect

    def inspect_with_failure(session_id: str) -> SessionInfo:
        if session_id != "one":
            return inspect(session_id)
        if failure == "unavailable":
            raise TimeoutError("upstream unavailable")
        if failure == "identity":
            return replace(driver.sessions[session_id], id="different")
        return replace(driver.sessions[session_id], cwd="D:/other")

    monkeypatch.setattr(driver, "inspect", inspect_with_failure)
    worker = MemberPresenceService(members, logging.getLogger("tests.member-presence"))
    worker.refresh()

    current = {item.id: item for item in rooms.snapshot(room_id).members}
    assert current[member.id].presence == "unknown"
    assert current[other.id].presence == "available"
    assert current["user"].presence == "available" and current["user"].observed_at is None
    monkeypatch.setattr(driver, "inspect", inspect)
    worker.refresh()
    assert RoomQueries(rooms.store.database).metadata(room_id).members[0].presence == "busy"


def test_unchanged_observations_checkpoint_without_emitting_events_on_every_poll(
    tmp_path: Path,
) -> None:
    members, rooms, driver, room_id, topic_id = setup(tmp_path)
    member = members.add(room_id, request(topic_id))
    assert member.observed_at is not None
    queries = RoomQueries(rooms.store.database)
    cursor = queries.events(room_id, 0).next_event_id
    members.record_observations(
        room_id, list(driver.sessions.values()), member.observed_at + timedelta(seconds=5)
    )
    assert queries.events(room_id, cursor).events == []
    assert queries.metadata(room_id).members[0].observed_at == member.observed_at
    checkpoint = member.observed_at + timedelta(seconds=31)
    members.record_observations(room_id, list(driver.sessions.values()), checkpoint)
    assert {event.kind for event in queries.events(room_id, cursor).events} == {"member", "session"}
    assert queries.metadata(room_id).members[0].observed_at == checkpoint


def test_session_renames_sync_without_overwriting_member_aliases_and_survive_restart(
    tmp_path: Path,
) -> None:
    members, rooms, driver, room_id, topic_id = setup(tmp_path)
    member = members.add(room_id, request(topic_id))
    rooms.update_member(room_id, member.id, UpdateMember(name="Alias", topic_ids=[topic_id]))
    assert member.observed_at is not None
    queries = RoomQueries(rooms.store.database)
    cursor = queries.events(room_id, 0).next_event_id
    driver.sessions["one"] = replace(driver.sessions["one"], name="Renamed Codex session")
    members.record_observations(
        room_id, list(driver.sessions.values()), member.observed_at + timedelta(seconds=1)
    )
    assert {event.kind for event in queries.events(room_id, cursor).events} == {"session"}
    metadata = RoomQueries(open_room_store(tmp_path / "rooms.sqlite3").database).metadata(room_id)
    assert metadata.sessions[0].name == "Renamed Codex session"
    assert metadata.members[0].name == "Alias"
    assert metadata.members[0].topic_ids == [topic_id]
    members.record_observations(room_id, [], member.observed_at + timedelta(seconds=2))
    assert queries.metadata(room_id).sessions[0].name == "Renamed Codex session"


@pytest.mark.parametrize("fail_first", [False, True])
def test_application_observes_presence_and_stops_worker_on_shutdown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fail_first: bool
) -> None:
    members, rooms, driver, room_id, topic_id = setup(tmp_path)
    members.add(room_id, request(topic_id))
    driver.sessions["one"] = replace(driver.sessions["one"], status="idle")
    app = create_app(
        logging.getLogger("tests.member-presence"),
        database=rooms.store.database,
        queue_driver=FakeQueueDriver(),
        session_driver=driver,
    )
    worker: MemberPresenceService = app.state.presence_runner
    worker.interval = 0.01
    observed = Event()
    refresh = worker.refresh
    attempts = 0

    def observe() -> None:
        nonlocal attempts
        attempts += 1
        if fail_first and attempts == 1:
            raise RuntimeError("temporary observation failure")
        refresh()
        observed.set()

    monkeypatch.setattr(worker, "refresh", observe)
    with TestClient(app) as client:
        assert observed.wait(timeout=2)
        assert worker.thread.is_alive()
        assert client.get(f"/api/room/{room_id}/metadata").json()["members"][0]["presence"] == (
            "available"
        )
    assert not worker.thread.is_alive()


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
    second = MemberSessions(open_room_store(members.store.path), driver)

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
    original = SQLAlchemyRoomRepository.save_resources

    def fail(repository: SQLAlchemyRoomRepository, current: RoomState, before: RoomState) -> None:
        original(repository, current, before)
        raise RuntimeError("injected failure")

    monkeypatch.setattr(SQLAlchemyRoomRepository, "save_resources", fail)
    with pytest.raises(RuntimeError, match="injected failure"):
        members.add(room_id, request(topic_id))
    assert [member.id for member in rooms.snapshot(room_id).members] == ["user"]
    assert RoomQueries(rooms.store.database).metadata(room_id).sessions == []


def test_api_preserves_bindings_on_restart_and_hides_upstream_errors(tmp_path: Path) -> None:
    members, rooms, driver, room_id, topic_id = setup(tmp_path)
    route = f"/api/room/{room_id}"
    logger = logging.getLogger("tests.member-sessions")
    with TestClient(
        create_app(
            logger,
            database=rooms.store.database,
            queue_driver=FakeQueueDriver(),
            session_driver=driver,
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
    driver = FakeSessionDriver([driver.sessions["one"]])
    restored = RoomService(open_room_store(members.store.path))
    with TestClient(
        create_app(
            logger,
            database=restored.store.database,
            queue_driver=FakeQueueDriver(),
            session_driver=driver,
        )
    ) as client:
        assert [
            item for item in client.get(route).json()["members"] if item["kind"] == "agent"
        ] == [member]
        assert client.get(route).json()["sessions"][0]["name"] == "Existing"
        assert driver.listed == 0
        driver.error = OSError("secret path and token")
        failed = client.get(route + "/session", headers={"X-Request-Id": "req_session"})
        assert failed.status_code == 503
        assert failed.json()["code"] == "service_unavailable"
        assert failed.json()["requestId"] == "req_session"
        assert "secret" not in failed.text
        assert [
            item for item in client.get(route).json()["members"] if item["kind"] == "agent"
        ] == [member]
