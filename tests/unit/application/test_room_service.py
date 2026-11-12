from datetime import UTC, datetime
from unittest.mock import MagicMock, Mock

import pytest

from agent_relay.application.rooms.contracts import CreateRoom, CreateTopic
from agent_relay.application.rooms.service import RoomService
from agent_relay.domain.rooms.errors import RoomConflictError
from agent_relay.domain.rooms.resources import DEFAULT_TOPIC_NAMES
from agent_relay.domain.rooms.state import RoomState


def test_room_creation_persists_business_initialization_without_database_defaults(
    room_store: MagicMock,
    room_repository: Mock,
) -> None:
    room = RoomService(room_store).create_room(
        CreateRoom(name="Another", project_path="D:/another")
    )
    state, original = room_repository.save_resources.call_args.args
    assert state.room == room and room.project_path == "d:/another"
    assert state.members[0].id == "user"
    assert [topic.name for topic in state.topics] == list(DEFAULT_TOPIC_NAMES)
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
        assert all(topic.id not in member.topic_ids for member in room_state.members)
    assert changed.created_at == original_topic.created_at
    saved, original = room_repository.save_resources.call_args.args
    assert saved is room_state and original.room == before
    assert original.topics[0] == original_topic
