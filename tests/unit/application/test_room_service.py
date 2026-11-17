from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import MagicMock, Mock

import pytest

from conflua.application.dto.members import SessionInfo
from conflua.application.dto.rooms import CreateRoom, CreateTopic, UpdateRoom
from conflua.application.members.sessions import SessionDriver, SessionUnavailableError
from conflua.application.rooms.service import RoomService
from conflua.domain.rooms.errors import RoomConflictError, RoomInputError, RoomNotFoundError
from conflua.domain.rooms.models import RoomState


def test_room_creation_persists_business_initialization_without_database_defaults(
    room_store: MagicMock,
    room_repository: Mock,
) -> None:
    room = RoomService(room_store).create_room(
        CreateRoom(name="Another", workspace_path="D:/another")
    )
    state, original = room_repository.save_resources.call_args.args
    assert state.room == room and room.workspace_path == "D:/another"
    assert room.raw_workspace_path == "D:/another"
    assert original.topics == [] and original.members == state.members
    room_repository.insert_room.assert_called_once_with(room, state.members[0])
    room_store.write.return_value.__exit__.assert_called_once_with(None, None, None)


@pytest.mark.parametrize(
    ("raw_path", "normalized_path"),
    [
        ("  D:\\Work\\temp\\..\\Project\\  ", "D:/Work/Project"),
        (" /Work/./temp/../Project/ ", "/Work/Project"),
    ],
)
def test_room_creation_preserves_input_and_uses_normalized_working_path(
    room_store: MagicMock, room_repository: Mock, raw_path: str, normalized_path: str
) -> None:
    room = RoomService(room_store).create_room(CreateRoom(name="Project", workspace_path=raw_path))
    state, _ = room_repository.save_resources.call_args.args
    assert room.raw_workspace_path == raw_path
    assert room.workspace_path == state.working_path == normalized_path
    room_repository.workspace_exists.assert_called_once_with(normalized_path)


def test_room_edit_updates_both_paths_and_excludes_its_own_identity(
    room_state: RoomState, room_store: MagicMock, room_repository: Mock
) -> None:
    raw_path = "  D:\\Other\\temp\\..\\Project\\  "
    result = RoomService(room_store).update_room(
        room_state.room.id, UpdateRoom(name="Updated", workspace_path=raw_path)
    )
    saved, original = room_repository.save_resources.call_args.args
    assert result.raw_workspace_path == raw_path
    assert result.workspace_path == "D:/Other/Project"
    assert saved.room == result and original.room.workspace_path == "d:/project"
    room_repository.workspace_exists.assert_called_once_with(
        "D:/Other/Project", exclude_room_id=room_state.room.id
    )


def test_room_name_only_edit_preserves_both_paths(
    room_state: RoomState, room_store: MagicMock, room_repository: Mock
) -> None:
    original = room_state.room.model_copy(deep=True)
    result = RoomService(room_store).update_room(room_state.room.id, UpdateRoom(name="Updated"))
    assert result.raw_workspace_path == original.raw_workspace_path
    assert result.workspace_path == original.workspace_path
    room_repository.workspace_exists.assert_not_called()


@pytest.mark.parametrize("path", ["relative", "D:relative", "   "])
def test_invalid_room_path_edit_does_not_mutate_resources(
    room_state: RoomState, room_store: MagicMock, room_repository: Mock, path: str
) -> None:
    original = room_state.room.model_copy(deep=True)
    with pytest.raises(RoomInputError):
        RoomService(room_store).update_room(
            room_state.room.id, UpdateRoom(name="Changed", workspace_path=path)
        )
    assert room_state.room == original
    room_repository.save_resources.assert_not_called()


def test_conflicting_room_path_edit_does_not_mutate_resources(
    room_state: RoomState, room_store: MagicMock, room_repository: Mock
) -> None:
    original = room_state.room.model_copy(deep=True)
    room_repository.workspace_exists.return_value = True
    with pytest.raises(RoomConflictError):
        RoomService(room_store).update_room(
            room_state.room.id, UpdateRoom(name="Changed", workspace_path="D:/other")
        )
    assert room_state.room == original
    room_repository.save_resources.assert_not_called()


def test_workspace_path_conflict_uses_normalized_identity_without_writing(
    room_store: MagicMock,
    room_repository: Mock,
) -> None:
    room_repository.workspace_exists.return_value = True
    with pytest.raises(RoomConflictError, match="该路径已有聊天室"):
        RoomService(room_store).create_room(
            CreateRoom(name="Duplicate", workspace_path="D:\\PROJECT\\")
        )
    room_repository.workspace_exists.assert_called_once_with("D:/PROJECT")
    room_repository.insert_room.assert_not_called()
    room_repository.save_resources.assert_not_called()


@pytest.mark.parametrize("status", ["unavailable", "error", "archived", "missing"])
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
        return sessions

    driver.connected_sessions.side_effect = lambda session_ids: discover()

    result = RoomService(room_store).clear_room(room_state.room.id, driver)

    driver.connected_sessions.assert_called_once_with(
        frozenset(member.session_id for member in room_state.members if member.session_id)
    )
    driver.list_sessions.assert_not_called()

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
    driver.connected_sessions.side_effect = TimeoutError("private diagnostic")

    with pytest.raises(SessionUnavailableError, match="无法核验成员连接状态"):
        RoomService(room_store).clear_room("conflua", driver)

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
    room_repository.active_bindings.side_effect = RoomNotFoundError("聊天室不存在")
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
