from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import MagicMock, Mock

import pytest

from agent_relay.application.dto.members import SessionInfo
from agent_relay.application.dto.rooms import CreateRoom, CreateTopic
from agent_relay.application.members.sessions import SessionDriver, SessionUnavailableError
from agent_relay.application.rooms.service import RoomService
from agent_relay.domain.rooms.errors import RoomConflictError, RoomNotFoundError
from agent_relay.domain.rooms.models import RoomState


def test_room_creation_persists_business_initialization_without_database_defaults(
    room_store: MagicMock,
    room_repository: Mock,
) -> None:
    room = RoomService(room_store).create_room(
        CreateRoom(name="Another", project_path="D:/another")
    )
    state, original = room_repository.save_resources.call_args.args
    assert state.room == room and room.project_path == "d:/another"
    assert original.topics == [] and original.members == state.members
    room_repository.insert_room.assert_called_once_with(room, state.members[0])
    room_store.write.return_value.__exit__.assert_called_once_with(None, None, None)


def test_project_path_conflict_uses_normalized_identity_without_writing(
    room_store: MagicMock,
    room_repository: Mock,
) -> None:
    room_repository.project_exists.return_value = True
    with pytest.raises(RoomConflictError, match="该项目已有聊天室"):
        RoomService(room_store).create_room(
            CreateRoom(name="Duplicate", project_path="D:\\PROJECT\\")
        )
    room_repository.project_exists.assert_called_once_with("d:/project")
    room_repository.insert_room.assert_not_called()
    room_repository.save_resources.assert_not_called()


@pytest.mark.parametrize("status", ["unavailable", "error", "archived", "missing", "other-project"])
def test_room_clear_soft_deletes_only_unreachable_members_after_fresh_discovery(
    room_state: RoomState,
    room_store: MagicMock,
    room_repository: Mock,
    status: str,
) -> None:
    driver = Mock(spec=SessionDriver)
    target = room_state.members[1]
    room_state.members[2].presence = "unknown"
    room_state.members[3].presence = "busy"
    room_repository.clear_messages.return_value = 5

    def discover() -> list[SessionInfo]:
        room_store.read.return_value.__exit__.assert_called_once()
        room_store.write.assert_not_called()
        sessions = [
            SessionInfo(
                id=member.session_id,
                cwd="D:/project",
                provider="codex",
                name=member.name,
                status="active",
            )
            for member in room_state.members
            if member.session_id is not None
        ]
        if status == "missing":
            return sessions[1:]
        if status in {"unavailable", "error"}:
            sessions[0] = replace(
                sessions[0], status="error" if status == "error" else "unavailable"
            )
        elif status == "archived":
            sessions[0] = replace(sessions[0], archived=True)
        else:
            sessions[0] = replace(sessions[0], cwd="D:/other")
        return sessions

    driver.list_sessions.side_effect = discover

    result = RoomService(room_store).clear_room(room_state.room.id, driver)

    assert result.removed_messages == 5 and result.removed_members == 1
    assert target.deleted_at is not None and target.topic_ids == []
    assert all(member.deleted_at is None for member in room_state.members if member.id != target.id)
    assert room_state.members[0].kind == "human"
    saved, original = room_repository.save_resources.call_args.args
    assert saved is room_state and original.members[1].deleted_at is None
    assert saved.topics == original.topics and saved.sessions == original.sessions
    room_repository.clear_messages.assert_called_once_with(room_state.room.id, target.deleted_at)
    room_repository.delete_room.assert_not_called()


def test_room_clear_does_not_write_when_session_discovery_fails(
    room_store: MagicMock, room_repository: Mock
) -> None:
    driver = Mock(spec=SessionDriver)
    driver.list_sessions.side_effect = TimeoutError("private diagnostic")

    with pytest.raises(SessionUnavailableError, match="无法核验成员连接状态"):
        RoomService(room_store).clear_room("agent-relay", driver)

    room_store.write.assert_not_called()
    room_repository.clear_messages.assert_not_called()
    room_repository.save_resources.assert_not_called()


def test_room_clear_does_not_need_codex_when_only_the_fixed_user_remains(
    room_state: RoomState, room_store: MagicMock, room_repository: Mock
) -> None:
    room_state.members = room_state.members[:1]
    driver = Mock(spec=SessionDriver)
    room_repository.clear_messages.return_value = 0

    result = RoomService(room_store).clear_room(room_state.room.id, driver)

    assert result.removed_messages == result.removed_members == 0
    driver.list_sessions.assert_not_called()
    assert room_state.members[0].deleted_at is None


def test_room_clear_checks_room_existence_before_contacting_codex(
    room_store: MagicMock, room_repository: Mock
) -> None:
    room_repository.resources.side_effect = RoomNotFoundError("聊天室不存在")
    driver = Mock(spec=SessionDriver)

    with pytest.raises(RoomNotFoundError):
        RoomService(room_store).clear_room("missing", driver)

    driver.list_sessions.assert_not_called()
    room_store.write.assert_not_called()


@pytest.mark.parametrize("operation", ["update", "delete"])
def test_topic_changes_preserve_creation_time_and_original_resources(
    room_state: RoomState,
    room_store: MagicMock,
    room_repository: Mock,
    operation: str,
) -> None:
    topic = room_state.topics[0]
    topic.created_at = datetime.now(UTC)
    before = room_state.room.model_copy(deep=True)
    original_topic = topic.model_copy(deep=True)
    service = RoomService(room_store)
    if operation == "update":
        changed = service.update_topic(
            room_state.room.id, topic.id, CreateTopic(name="团队讨论", description="  讨论  ")
        )
        assert changed.name == "团队讨论" and changed.description == "讨论"
    else:
        changed = service.delete_topic(room_state.room.id, topic.id)
        assert changed.deleted_at is not None
    assert changed.created_at == original_topic.created_at
    saved, original = room_repository.save_resources.call_args.args
    assert saved is room_state and original.room == before
    assert original.topics[0] == original_topic
