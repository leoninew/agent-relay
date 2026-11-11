import pytest
from support.fakes.rooms import MemoryRoomStore, sample_room

from agent_relay.application.rooms.contracts import CreateRoom, CreateTopic
from agent_relay.application.rooms.service import RoomService
from agent_relay.domain.rooms.errors import RoomConflictError
from agent_relay.domain.rooms.resources import DEFAULT_TOPIC_NAMES


def test_room_creation_persists_business_initialization_without_database_defaults() -> None:
    store = MemoryRoomStore(sample_room())
    room = RoomService(store).create_room(CreateRoom(name="Another", project_path="D:/another"))
    state = store.data.resources(room.id)
    assert state.members[0].id == "user"
    assert [topic.name for topic in state.topics] == list(DEFAULT_TOPIC_NAMES)
    assert store.active_scopes == 0


def test_project_path_conflicts_ignore_windows_slashes_and_case() -> None:
    state = sample_room()
    store = MemoryRoomStore(state)
    with pytest.raises(RoomConflictError, match="该项目已有聊天室"):
        RoomService(store).create_room(CreateRoom(name="Duplicate", project_path="D:\\PROJECT\\"))
    assert list(store.data.states) == [state.room.id]


def test_all_default_topics_can_be_edited_and_retired_without_changing_creation_time() -> None:
    store = MemoryRoomStore(sample_room())
    service = RoomService(store)
    room = service.create_room(CreateRoom(name="Another", project_path="D:/another"))
    topics = store.data.resources(room.id).topics

    for topic in topics:
        updated = service.update_topic(
            room.id, topic.id, CreateTopic(name=f"{topic.name}讨论", description="团队讨论")
        )
        assert updated.name == f"{topic.name}讨论" and updated.description == "团队讨论"
        assert updated.created_at == topic.created_at
        deleted = service.delete_topic(room.id, topic.id)
        assert deleted.deleted_at is not None and deleted.created_at == topic.created_at

    assert all(topic.deleted_at for topic in store.data.resources(room.id).topics)
