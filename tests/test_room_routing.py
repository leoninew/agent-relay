from datetime import UTC, datetime
from pathlib import Path

import pytest
from room_fixtures import DemoRoomService, create_room_store

from agent_relay.room_service import RoomInputError, RoomService
from agent_relay.room_state import RoomState


@pytest.fixture
def member_room(tmp_path: Path) -> tuple[RoomService, RoomState]:
    service = DemoRoomService(create_room_store(tmp_path / "routing.sqlite3"))
    snapshot = service.snapshot("agent-relay")
    state = RoomState(room=snapshot.room, topics=snapshot.topics, members=snapshot.members)
    return service, state


@pytest.mark.parametrize(
    ("topic_ids", "mentions", "recipients"),
    [
        (["frontend"], [], ["frontend-worker", "test-worker"]),
        ([], ["coordinator", "backend-worker"], ["backend-worker"]),
        (
            ["frontend"],
            ["coordinator", "frontend-worker", "backend-worker"],
            ["frontend-worker", "backend-worker", "test-worker"],
        ),
    ],
)
def test_member_publication_excludes_sender_and_preserves_explicit_targets(
    member_room: tuple[RoomService, RoomState],
    topic_ids: list[str],
    mentions: list[str],
    recipients: list[str],
) -> None:
    service, state = member_room

    message = service._append_message(
        state,
        content="同步协作进展",
        topic_ids=topic_ids,
        mentioned_member_ids=mentions,
        sender_id="coordinator",
        sender_name="主会话",
        created_at=datetime.now(UTC),
    )

    assert message.topic_ids == topic_ids
    assert message.mentioned_member_ids == mentions
    assert message.recipient_ids == recipients
    assert [delivery.target_member_id for delivery in message.deliveries] == recipients
    assert state.messages == [message]


@pytest.mark.parametrize(
    ("topic_ids", "mentions"),
    [(["frontend"], []), ([], ["coordinator"]), (["frontend"], ["coordinator"])],
)
def test_publication_with_no_other_recipient_is_rejected_without_saving(
    member_room: tuple[RoomService, RoomState], topic_ids: list[str], mentions: list[str]
) -> None:
    service, state = member_room
    state.members = [member for member in state.members if member.id == "coordinator"]

    with pytest.raises(RoomInputError, match="排除发布成员后没有实际接收人"):
        service._append_message(
            state,
            content="只有自己接收",
            topic_ids=topic_ids,
            mentioned_member_ids=mentions,
            sender_id="coordinator",
            sender_name="主会话",
            created_at=datetime.now(UTC),
        )

    assert state.messages == []


def test_invalid_explicit_target_is_not_hidden_by_sender_exclusion(
    member_room: tuple[RoomService, RoomState],
) -> None:
    service, state = member_room

    with pytest.raises(RoomInputError, match="@ 成员不存在"):
        service._append_message(
            state,
            content="不能部分投递",
            topic_ids=["frontend"],
            mentioned_member_ids=["coordinator", "missing"],
            sender_id="coordinator",
            sender_name="主会话",
            created_at=datetime.now(UTC),
        )

    assert state.messages == []
