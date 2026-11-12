from datetime import UTC, datetime

import pytest

from agent_relay.domain.rooms.errors import RoomInputError
from agent_relay.domain.rooms.models import Member, Room, RoomState, Topic
from agent_relay.domain.rooms.rules import build_message, normalize_project_path


def room_state() -> RoomState:
    return RoomState(
        room=Room(id="room", name="Room", project_path="d:/project", description=""),
        topics=[Topic(id="work", name="Work", description="")],
        members=[
            Member(
                id="sender",
                session_id="one",
                name="Sender",
                initials="S",
                presence="available",
                activity="",
                topic_ids=["work"],
            ),
            Member(
                id="target",
                session_id="two",
                name="Target",
                initials="T",
                presence="available",
                activity="",
                topic_ids=["work"],
            ),
            Member(
                id="user",
                kind="human",
                session_id=None,
                name="你",
                initials="你",
                presence="available",
                activity="",
                topic_ids=[],
            ),
        ],
    )


@pytest.mark.parametrize(
    ("topics", "mentions", "recipients"),
    [
        (["work"], ["target", "sender"], ["target"]),
        ([], ["user"], ["user"]),
        (["work"], ["user"], ["target", "user"]),
    ],
)
def test_routing_freezes_distinct_recipients_and_only_agents_have_deliveries(
    topics: list[str], mentions: list[str], recipients: list[str]
) -> None:
    message = build_message(
        room_state(),
        content="Message",
        topic_ids=topics,
        mentioned_member_ids=mentions,
        sender_id="sender",
        sender_name="Sender",
        created_at=datetime.now(UTC),
        seq=1,
    )
    assert message.recipient_ids == recipients
    assert [item.target_member_id for item in message.deliveries] == [
        member_id for member_id in recipients if member_id != "user"
    ]


def test_invalid_target_is_rejected_before_sender_exclusion() -> None:
    with pytest.raises(RoomInputError, match="@ 成员不存在"):
        build_message(
            room_state(),
            content="Message",
            topic_ids=["work"],
            mentioned_member_ids=["sender", "missing"],
            sender_id="sender",
            sender_name="Sender",
            created_at=datetime.now(UTC),
            seq=1,
        )


@pytest.mark.parametrize(
    ("topic_ids", "mentions"),
    [(["work"], []), ([], ["sender"]), (["work"], ["sender"])],
)
def test_publication_with_no_other_recipient_is_rejected(
    topic_ids: list[str], mentions: list[str]
) -> None:
    state = room_state()
    state.members = [member for member in state.members if member.id == "sender"]

    with pytest.raises(RoomInputError, match="排除发布成员后没有实际接收人"):
        build_message(
            state,
            seq=1,
            content="只有自己接收",
            topic_ids=topic_ids,
            mentioned_member_ids=mentions,
            sender_id="sender",
            sender_name="Sender",
            created_at=datetime.now(UTC),
        )


@pytest.mark.parametrize(
    ("path", "expected"),
    [("D:\\PROJECT\\", "d:/project"), ("/Work/project/", "/Work/project")],
)
def test_project_paths_follow_platform_identity(path: str, expected: str) -> None:
    assert normalize_project_path(path) == expected
