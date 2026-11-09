from datetime import UTC, datetime
from pathlib import Path

import pytest
from room_fixtures import DemoRoomService, create_room_store

from agent_relay.room_errors import RoomConflictError, RoomInputError
from agent_relay.room_models import CreateMessage
from agent_relay.room_service import RoomService
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

    message = service._build_message(
        state,
        seq=1,
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


@pytest.mark.parametrize(
    ("topic_ids", "mentions"),
    [(["frontend"], []), ([], ["coordinator"]), (["frontend"], ["coordinator"])],
)
def test_publication_with_no_other_recipient_is_rejected(
    member_room: tuple[RoomService, RoomState], topic_ids: list[str], mentions: list[str]
) -> None:
    service, state = member_room
    state.members = [member for member in state.members if member.id == "coordinator"]

    with pytest.raises(RoomInputError, match="排除发布成员后没有实际接收人"):
        service._build_message(
            state,
            seq=1,
            content="只有自己接收",
            topic_ids=topic_ids,
            mentioned_member_ids=mentions,
            sender_id="coordinator",
            sender_name="主会话",
            created_at=datetime.now(UTC),
        )


def test_member_can_mention_the_user_without_agent_recipients(
    member_room: tuple[RoomService, RoomState],
) -> None:
    service, state = member_room

    message = service._build_message(
        state,
        seq=1,
        content="流程测试已就绪",
        topic_ids=[],
        mentioned_member_ids=["user"],
        sender_id="coordinator",
        sender_name="主会话",
        created_at=datetime.now(UTC),
    )

    assert message.mentioned_member_ids == ["user"]
    assert message.recipient_ids == ["user"]
    assert message.deliveries == []


def test_member_can_address_the_user_and_topic_members_together(
    member_room: tuple[RoomService, RoomState],
) -> None:
    service, state = member_room

    message = service._build_message(
        state,
        seq=1,
        content="同步给用户与团队",
        topic_ids=["frontend"],
        mentioned_member_ids=["user"],
        sender_id="coordinator",
        sender_name="主会话",
        created_at=datetime.now(UTC),
    )

    assert message.recipient_ids == ["frontend-worker", "test-worker", "user"]
    assert [delivery.target_member_id for delivery in message.deliveries] == [
        "frontend-worker",
        "test-worker",
    ]


def test_user_publisher_cannot_address_itself(
    member_room: tuple[RoomService, RoomState],
) -> None:
    service, _ = member_room
    request = CreateMessage(
        publication_id="user-self",
        content="不能发给自己",
        mentioned_member_ids=["user"],
    )

    with pytest.raises(RoomInputError, match="不能将消息发送给自己"):
        service.post_message("agent-relay", request)


def test_publication_replay_cannot_change_its_audience(
    member_room: tuple[RoomService, RoomState],
) -> None:
    service, _ = member_room
    request = CreateMessage(
        publication_id="stable-audience",
        content="固定接收对象",
        topic_ids=["frontend"],
    )
    service.post_message("agent-relay", request, member_id="coordinator")

    with pytest.raises(RoomConflictError, match="发布编号已用于另一条消息"):
        service.post_message(
            "agent-relay",
            request.model_copy(update={"mentioned_member_ids": ["user"]}),
            member_id="coordinator",
        )


def test_invalid_explicit_target_is_not_hidden_by_sender_exclusion(
    member_room: tuple[RoomService, RoomState],
) -> None:
    service, state = member_room

    with pytest.raises(RoomInputError, match="@ 成员不存在"):
        service._build_message(
            state,
            seq=1,
            content="不能部分投递",
            topic_ids=["frontend"],
            mentioned_member_ids=["coordinator", "missing"],
            sender_id="coordinator",
            sender_name="主会话",
            created_at=datetime.now(UTC),
        )
