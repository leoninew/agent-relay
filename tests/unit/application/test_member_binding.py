import logging
from dataclasses import replace
from unittest.mock import MagicMock, Mock

import pytest

from agent_relay.application.dto.members import CreateMember, SessionInfo
from agent_relay.application.members.service import MemberService
from agent_relay.application.members.sessions import (
    SessionDriver,
    SessionUnavailableError,
)
from agent_relay.domain.rooms.errors import RoomConflictError, RoomInputError
from agent_relay.domain.rooms.models import RoomState


@pytest.fixture
def session_driver() -> Mock:
    driver = Mock(spec=SessionDriver)
    driver.list_sessions.return_value = []
    return driver


@pytest.mark.parametrize("changed_facts", [False, True])
def test_join_releases_read_scope_and_validates_current_resources_before_saving(
    room_state: RoomState,
    room_store: MagicMock,
    room_repository: Mock,
    session_driver: Mock,
    changed_facts: bool,
) -> None:
    def inspect(thread_id: str) -> SessionInfo:
        room_store.read.return_value.__exit__.assert_called_once()
        if changed_facts:
            room_state.members[0].name = "New member"
        return SessionInfo(thread_id, "D:/project", "codex", "Original", "idle")

    session_driver.inspect.side_effect = inspect
    service = MemberService(room_store, session_driver)
    request = CreateMember(name="New member", session_id="fresh", topic_ids=[])
    if changed_facts:
        with pytest.raises(RoomConflictError, match="同名"):
            service.add(room_state.room.id, request)
        room_repository.save_resources.assert_not_called()
    else:
        member = service.add(room_state.room.id, request)
        assert member.session_id == "fresh" and member.topic_ids == []
        assert member.metadata.members[-1].id == member.id
        room_repository.save_resources.assert_called_once()
    session_driver.inspect.assert_called_once_with("fresh")


def test_empty_sessions_and_driver_failure_do_not_create_members(
    room_store: MagicMock,
    room_repository: Mock,
    session_driver: Mock,
) -> None:
    service = MemberService(room_store, session_driver)
    assert service.candidates("agent-relay") == []
    session_driver.list_sessions.side_effect = TimeoutError("secret upstream detail")
    session_driver.inspect.side_effect = TimeoutError("secret upstream detail")
    with pytest.raises(SessionUnavailableError):
        service.candidates("agent-relay")
    with pytest.raises(SessionUnavailableError):
        service.add("agent-relay", CreateMember(name="Worker", session_id="one", topic_ids=[]))
    room_repository.save_resources.assert_not_called()


def test_discovery_keeps_posix_paths_case_sensitive(
    room_state: RoomState,
    room_store: MagicMock,
    session_driver: Mock,
) -> None:
    room_state.room.project_path = "/Work/project"
    session_driver.list_sessions.return_value = [
        SessionInfo("exact", "/Work/project/", "codex", "Exact", "idle"),
        SessionInfo("wrong-case", "/work/project", "codex", "Wrong", "idle"),
    ]
    candidates = MemberService(room_store, session_driver).candidates("agent-relay")
    assert [candidate.id for candidate in candidates] == ["exact"]


@pytest.mark.parametrize(
    ("info", "topics", "error", "message"),
    [
        (SessionInfo("one", "D:/other", "codex", "Other", "idle"), [], RoomInputError, "不属于"),
        (
            SessionInfo("one", "D:/project/subdir", "codex", "Child", "idle"),
            [],
            RoomInputError,
            "不属于",
        ),
        (
            SessionInfo("other", "D:/project", "codex", "Other", "idle"),
            [],
            SessionUnavailableError,
            "身份不匹配",
        ),
        (
            SessionInfo("one", "D:/project", "codex", "One", "idle"),
            ["missing"],
            RoomInputError,
            "话题不存在",
        ),
    ],
)
def test_invalid_join_does_not_save_resources(
    room_store: MagicMock,
    room_repository: Mock,
    session_driver: Mock,
    info: SessionInfo,
    topics: list[str],
    error: type[Exception],
    message: str,
) -> None:
    session_driver.inspect.return_value = info
    with pytest.raises(error, match=message):
        MemberService(room_store, session_driver).add(
            "agent-relay", CreateMember(name="Worker", session_id="one", topic_ids=topics)
        )
    room_repository.save_resources.assert_not_called()
    if topics == ["missing"]:
        session_driver.inspect.assert_not_called()


@pytest.mark.parametrize("failure", ["unavailable", "identity", "directory"])
def test_presence_failure_records_unknown_and_continues_other_members(
    failure: str,
    room_store: MagicMock,
    room_repository: Mock,
    session_driver: Mock,
) -> None:
    room_repository.bindings.return_value = [
        ("agent-relay", "frontend-worker-session"),
        ("agent-relay", "backend-worker-session"),
    ]
    room_repository.joined_members.return_value = {
        "frontend-worker-session": "frontend-worker",
        "backend-worker-session": "backend-worker",
    }

    def inspect(session_id: str) -> SessionInfo:
        room_store.read.return_value.__exit__.assert_called_once()
        info = SessionInfo(session_id, "D:/project", "codex", "Original", "idle")
        if session_id == "backend-worker-session":
            return info
        if failure == "unavailable":
            raise TimeoutError("upstream unavailable")
        if failure == "identity":
            return replace(info, id="different")
        return replace(info, cwd="D:/other")

    session_driver.inspect.side_effect = inspect
    MemberService(room_store, session_driver).refresh_presence(
        logging.getLogger("tests.member-presence"), lambda: False
    )
    observations = {
        observation.args[1]: observation
        for observation in room_repository.save_observation.call_args_list
    }
    assert set(observations) == {"frontend-worker", "backend-worker"}
    failed = observations["frontend-worker"]
    assert failed.args[3] == "unknown" and failed.args[6] is None
    assert "未能核验" in failed.args[4]
    assert failed.kwargs["refresh_cutoff"] < failed.args[5]
    assert observations["backend-worker"].args[3] == "available"
    session_driver.list_sessions.assert_not_called()


@pytest.mark.parametrize("status", ["unavailable", "idle"])
def test_candidates_explain_unavailable_sessions_and_record_presence(
    status: str,
    room_store: MagicMock,
    room_repository: Mock,
    session_driver: Mock,
) -> None:
    info = SessionInfo("frontend-worker-session", "D:/project", "codex", "Existing", "idle")
    if status == "unavailable":
        info = replace(info, status="unavailable")
    session_driver.list_sessions.return_value = [info]
    candidate = MemberService(room_store, session_driver).candidates("agent-relay")[0]
    assert candidate.member_id == "frontend-worker"
    assert candidate.usable is (status == "idle")
    if status == "unavailable":
        assert candidate.unavailable_reason and "独立实例" in candidate.unavailable_reason
    recorded = next(
        observation
        for observation in room_repository.save_observation.call_args_list
        if observation.args[2] == info.id
    )
    assert recorded.args[3] == candidate.presence
    if not candidate.usable:
        assert recorded.args[4] == candidate.unavailable_reason
