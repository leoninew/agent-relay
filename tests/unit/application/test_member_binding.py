import logging
from dataclasses import replace
from unittest.mock import MagicMock, Mock

import pytest

from conflua.application.dto.members import CreateMember, SessionChannel, SessionInfo, SessionStatus
from conflua.application.members.service import MemberService
from conflua.application.members.sessions import (
    SessionDriver,
    SessionUnavailableError,
)
from conflua.domain.rooms.errors import RoomConflictError, RoomInputError
from conflua.domain.rooms.models import RoomState


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
        return SessionInfo(thread_id, "codex", "Original", "idle")

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
    assert service.candidates("conflua") == []
    session_driver.list_sessions.side_effect = TimeoutError("secret upstream detail")
    session_driver.inspect.side_effect = TimeoutError("secret upstream detail")
    with pytest.raises(SessionUnavailableError):
        service.candidates("conflua")
    with pytest.raises(SessionUnavailableError):
        service.add("conflua", CreateMember(name="Worker", session_id="one", topic_ids=[]))
    room_repository.save_resources.assert_not_called()


def test_join_stores_session_metadata_without_a_directory(
    room_store: MagicMock,
    session_driver: Mock,
) -> None:
    session_driver.inspect.return_value = SessionInfo("fresh", "codex", "Original", "idle")
    member = MemberService(room_store, session_driver).add(
        "conflua", CreateMember(name="New member", session_id="fresh", topic_ids=[])
    )
    assert member.session.id == "fresh" and member.session.name == "Original"
    assert "projectPath" not in member.session.model_dump(by_alias=True)


@pytest.mark.parametrize("working_path", ["d:/project", "d:/worktrees/feature"])
def test_discovery_queries_sessions_in_the_channel_working_directory(
    room_state: RoomState,
    room_store: MagicMock,
    session_driver: Mock,
    working_path: str,
) -> None:
    room_state.working_path = working_path
    session_driver.list_sessions.return_value = [
        SessionInfo("matching", "codex", "Matching", "idle"),
    ]
    candidates = MemberService(room_store, session_driver).candidates("conflua")
    session_driver.list_sessions.assert_called_once_with(working_path)
    assert [candidate.id for candidate in candidates] == ["matching"]


def test_candidates_exclude_archived_sessions(
    room_store: MagicMock,
    session_driver: Mock,
) -> None:
    session_driver.list_sessions.return_value = [
        SessionInfo("archived", "codex", "Archived", "idle", archived=True),
        SessionInfo("unavailable", "codex", "Unavailable", "unavailable"),
        SessionInfo("available", "codex", "Available", "idle"),
    ]

    candidates = MemberService(room_store, session_driver).candidates("conflua")

    assert [candidate.id for candidate in candidates] == ["unavailable", "available"]


@pytest.mark.parametrize("status", ["idle", "unavailable"])
def test_candidates_include_joined_channels_without_changing_current_membership(
    room_store: MagicMock,
    room_repository: Mock,
    session_driver: Mock,
    status: SessionStatus,
) -> None:
    session_driver.list_sessions.return_value = [
        SessionInfo("shared", "codex", "Shared", status),
        SessionInfo("current", "codex", "Current", "idle"),
        SessionInfo("fresh", "codex", "Fresh", "idle"),
    ]
    channels = [
        SessionChannel(id="channel-api", name="API"),
        SessionChannel(id="channel-web", name="Web"),
    ]
    room_repository.joined_members.return_value = {"current": "current-member"}
    room_repository.joined_channels.return_value = {
        "shared": channels,
        "current": [SessionChannel(id="channel-default", name="默认")],
    }

    shared, current, fresh = MemberService(room_store, session_driver).candidates("conflua")

    assert shared.joined_channels == channels
    assert shared.member_id is None
    assert shared.usable == (status == "idle")
    assert shared.model_dump(by_alias=True)["joinedChannels"] == [
        {"id": "channel-api", "name": "API"},
        {"id": "channel-web", "name": "Web"},
    ]
    assert current.member_id == "current-member"
    assert current.joined_channels == [SessionChannel(id="channel-default", name="默认")]
    assert fresh.joined_channels == []
    assert fresh.member_id is None
    room_repository.joined_channels.assert_called_once_with("conflua")


@pytest.mark.parametrize(
    ("info", "topics", "error", "message"),
    [
        (
            SessionInfo("other", "codex", "Other", "idle"),
            [],
            SessionUnavailableError,
            "身份不匹配",
        ),
        (
            SessionInfo("one", "codex", "One", "idle"),
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
            "conflua", CreateMember(name="Worker", session_id="one", topic_ids=topics)
        )
    room_repository.save_resources.assert_not_called()
    if topics == ["missing"]:
        session_driver.inspect.assert_not_called()


@pytest.mark.parametrize("failure", ["unavailable", "identity"])
def test_presence_failure_records_unknown_and_continues_other_members(
    failure: str,
    room_state: RoomState,
    room_store: MagicMock,
    room_repository: Mock,
    session_driver: Mock,
) -> None:
    room_repository.bindings.return_value = [
        ("conflua", "channel-default", "frontend-worker-session"),
        ("conflua", "channel-default", "backend-worker-session"),
    ]
    room_state.members = [
        member
        for member in room_state.members
        if member.id in {"frontend-worker", "backend-worker"}
    ]

    def inspect(session_id: str) -> SessionInfo:
        room_store.read.return_value.__exit__.assert_called_once()
        info = SessionInfo(session_id, "codex", "Original", "idle")
        if session_id == "backend-worker-session":
            return info
        if failure == "unavailable":
            raise TimeoutError("upstream unavailable")
        return replace(info, id="different")

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
    room_repository.resources.assert_not_called()


def test_presence_failure_logs_once_until_the_session_recovers(
    room_store: MagicMock,
    room_repository: Mock,
    session_driver: Mock,
) -> None:
    room_repository.bindings.return_value = [
        ("conflua", "channel-default", "frontend-worker-session")
    ]
    first_error = TimeoutError("upstream unavailable")
    session_driver.inspect.side_effect = [
        first_error,
        TimeoutError("still unavailable"),
        SessionInfo("frontend-worker-session", "codex", "Original", "idle"),
    ]
    logger = Mock(spec=logging.Logger)
    service = MemberService(room_store, session_driver)

    for _ in range(3):
        service.refresh_presence(logger, lambda: False)

    logger.warning.assert_called_once_with(
        "Member presence unavailable session=%s reason=%s",
        "frontend-worker-session",
        first_error,
    )
    logger.exception.assert_not_called()
    assert "frontend-worker-session" not in service.unavailable_presence_sessions


@pytest.mark.parametrize("status", ["unavailable", "idle"])
def test_candidates_explain_unavailable_sessions_and_record_presence(
    status: str,
    room_store: MagicMock,
    room_repository: Mock,
    session_driver: Mock,
) -> None:
    info = SessionInfo("frontend-worker-session", "codex", "Existing", "idle")
    if status == "unavailable":
        info = replace(info, status="unavailable")
    session_driver.list_sessions.return_value = [info]
    candidate = MemberService(room_store, session_driver).candidates("conflua")[0]
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
