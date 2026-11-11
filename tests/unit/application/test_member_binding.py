import logging
from dataclasses import replace

import pytest
from support.fakes.rooms import MemoryRoomStore, sample_room
from support.session_fixtures import FakeSessionDriver

from agent_relay.application.members.contracts import CreateMember
from agent_relay.application.members.service import MemberService
from agent_relay.application.members.sessions import SessionInfo, SessionUnavailableError
from agent_relay.domain.rooms.errors import RoomConflictError, RoomInputError


@pytest.mark.parametrize("concurrent_conflict", [False, True])
def test_join_releases_the_read_scope_before_inspection_and_rechecks_current_facts(
    concurrent_conflict: bool,
) -> None:
    state = sample_room()
    store = MemoryRoomStore(state)

    class ObservingDriver(FakeSessionDriver):
        def inspect(self, thread_id: str) -> SessionInfo:
            assert store.active_scopes == 0
            if concurrent_conflict:
                store.data.states[state.room.id].members[0].name = "New member"
            return super().inspect(thread_id)

    driver = ObservingDriver([SessionInfo("fresh", "D:/project", "codex", "Original", "idle")])
    members = MemberService(store, driver)
    request = CreateMember(name="New member", session_id="fresh", topic_ids=[])
    if concurrent_conflict:
        with pytest.raises(RoomConflictError, match="同名"):
            members.add(state.room.id, request)
        assert all(
            member.session_id != "fresh" for member in store.data.states[state.room.id].members
        )
    else:
        member = members.add(state.room.id, request)
        assert member.session_id == "fresh" and member.topic_ids == []
        assert member.metadata.members[-1].id == member.id
    assert driver.inspected == ["fresh"] and store.active_scopes == 0


def test_empty_sessions_and_driver_failure_do_not_create_members() -> None:
    state = sample_room()
    state.members = [member for member in state.members if member.kind == "human"]
    store = MemoryRoomStore(state)
    driver = FakeSessionDriver()
    service = MemberService(store, driver)
    assert service.candidates(state.room.id) == []
    driver.error = TimeoutError("secret upstream detail")
    with pytest.raises(SessionUnavailableError):
        service.candidates(state.room.id)
    with pytest.raises(SessionUnavailableError):
        service.add(
            state.room.id, CreateMember(name="Worker", session_id="one", topic_ids=["frontend"])
        )
    assert [member.id for member in store.data.resources(state.room.id).members] == ["user"]


def test_discovery_keeps_posix_paths_case_sensitive() -> None:
    state = sample_room()
    state.room.project_path = "/Work/project"
    state.members = [member for member in state.members if member.kind == "human"]
    driver = FakeSessionDriver(
        [
            SessionInfo("exact", "/Work/project/", "a", "Exact", "idle"),
            SessionInfo("wrong-case", "/work/project", "a", "Wrong", "idle"),
        ]
    )
    service = MemberService(MemoryRoomStore(state), driver)
    assert [candidate.id for candidate in service.candidates(state.room.id)] == ["exact"]


def test_join_rejects_wrong_directory_identity_and_topic_without_writing() -> None:
    state = sample_room()
    state.members = [member for member in state.members if member.kind == "human"]
    store = MemoryRoomStore(state)
    driver = FakeSessionDriver(
        [
            SessionInfo("one", "D:/project", "codex", "Original", "idle"),
            SessionInfo("other", "D:/other", "codex", "Other", "idle"),
            SessionInfo("child", "D:/project/subdir", "codex", "Child", "idle"),
        ]
    )
    service = MemberService(store, driver)
    for session_id in ("other", "child"):
        with pytest.raises(RoomInputError, match="不属于"):
            service.add(
                state.room.id,
                CreateMember(name="Worker", session_id=session_id, topic_ids=["frontend"]),
            )
    driver.sessions["one"] = driver.sessions["other"]
    with pytest.raises(SessionUnavailableError, match="身份不匹配"):
        service.add(
            state.room.id, CreateMember(name="Worker", session_id="one", topic_ids=["frontend"])
        )
    with pytest.raises(RoomInputError, match="话题不存在"):
        service.add(
            state.room.id, CreateMember(name="Worker", session_id="one", topic_ids=["missing"])
        )
    assert [member.id for member in store.data.resources(state.room.id).members] == ["user"]


@pytest.mark.parametrize("failure", ["unavailable", "identity", "directory"])
def test_presence_failure_records_unknown_and_continues_other_members(
    failure: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = sample_room()
    state.members = [
        member
        for member in state.members
        if member.id in {"frontend-worker", "backend-worker", "user"}
    ]
    store = MemoryRoomStore(state)
    driver = FakeSessionDriver(
        [
            SessionInfo(member.session_id, "D:/project", "codex", member.name, "idle")
            for member in state.members
            if member.session_id is not None
        ]
    )
    inspect = driver.inspect

    def inspect_with_failure(session_id: str) -> SessionInfo:
        assert store.active_scopes == 0
        if session_id != "frontend-worker-session":
            return inspect(session_id)
        if failure == "unavailable":
            raise TimeoutError("upstream unavailable")
        if failure == "identity":
            return replace(driver.sessions[session_id], id="different")
        return replace(driver.sessions[session_id], cwd="D:/other")

    monkeypatch.setattr(driver, "inspect", inspect_with_failure)
    service = MemberService(store, driver)
    logger = logging.getLogger("tests.member-presence")
    service.refresh_presence(logger, lambda: False)

    observations = {item.member_id: item for item in store.data.observations}
    assert set(observations) == {"frontend-worker", "backend-worker"}
    failed = observations["frontend-worker"]
    assert failed.presence == "unknown" and failed.session_name is None
    assert "未能核验" in failed.activity
    assert observations["backend-worker"].presence == "available"
    assert failed.refresh_cutoff < failed.observed_at
    assert driver.listed == 0

    monkeypatch.setattr(driver, "inspect", inspect)
    store.data.observations.clear()
    service.refresh_presence(logger, lambda: False)
    assert all(item.presence == "available" for item in store.data.observations)


def test_candidates_record_current_presence_and_explain_unavailable_sessions() -> None:
    state = sample_room()
    store = MemoryRoomStore(state)
    session_id = "frontend-worker-session"
    driver = FakeSessionDriver(
        [SessionInfo(session_id, "D:/project", "codex", "Existing", "unavailable")]
    )
    service = MemberService(store, driver)
    candidate = service.candidates(state.room.id)[0]
    assert candidate.member_id == "frontend-worker"
    assert candidate.presence == "unknown" and not candidate.usable
    assert candidate.unavailable_reason and "独立实例" in candidate.unavailable_reason
    recorded = next(item for item in store.data.observations if item.session_id == session_id)
    assert recorded.presence == "unknown" and recorded.activity == candidate.unavailable_reason

    store.data.observations.clear()
    driver.sessions[session_id] = replace(driver.sessions[session_id], status="idle")
    assert service.candidates(state.room.id)[0].usable
    recorded = next(item for item in store.data.observations if item.session_id == session_id)
    assert recorded.presence == "available"
