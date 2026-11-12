from unittest.mock import MagicMock, Mock

import pytest

from agent_relay.application.dto.messages import MessagePage
from agent_relay.application.rooms.queries import RoomReader
from agent_relay.domain.rooms.errors import RoomNotFoundError


def test_snapshot_reads_metadata_and_filtered_messages_in_one_repository_scope(
    room_store: MagicMock, room_repository: Mock
) -> None:
    room_repository.page.return_value = MessagePage(
        messages=[], has_more=False, next_before_seq=None, has_newer=False
    )

    snapshot = RoomReader(room_store).snapshot(
        "agent-relay", "frontend", member_id="user", keyword="接口", before_seq=163, limit=20
    )

    assert snapshot.room.id == "agent-relay" and snapshot.messages == []
    room_store.read.assert_called_once_with()
    room_repository.metadata.assert_called_once_with("agent-relay")
    room_repository.page.assert_called_once_with(
        "agent-relay",
        topic_id="frontend",
        member_id="user",
        keyword="接口",
        before_seq=163,
        limit=20,
    )
    room_store.write.assert_not_called()
    room_store.read.return_value.__exit__.assert_called_once_with(None, None, None)


def test_missing_room_does_not_expose_a_message_from_another_scope(
    room_store: MagicMock, room_repository: Mock
) -> None:
    room_repository.room.side_effect = RoomNotFoundError("聊天室不存在")

    with pytest.raises(RoomNotFoundError):
        RoomReader(room_store).message("missing", "message")

    room_repository.message.assert_not_called()


def test_each_event_poll_releases_its_repository_scope(
    room_store: MagicMock, room_repository: Mock
) -> None:
    reader = RoomReader(room_store)

    reader.events("agent-relay", 160)
    reader.events("agent-relay", 163)

    assert room_store.read.call_count == 2
    assert room_store.read.return_value.__exit__.call_count == 2
    assert room_repository.events.call_count == 2
    room_store.write.assert_not_called()
