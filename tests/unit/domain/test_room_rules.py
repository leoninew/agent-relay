from datetime import UTC, datetime

import pytest

from agent_relay.domain.rooms.errors import RoomConflictError, RoomInputError
from agent_relay.domain.rooms.models import (
    McpServerReference,
    Member,
    Message,
    Room,
    RoomState,
    SkillReference,
    Topic,
)
from agent_relay.domain.rooms.rules import (
    build_message,
    normalize_project_path,
    validate_publication_replay,
    validate_sender_targets,
)


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


@pytest.mark.parametrize(
    ("topics", "mentions"),
    [(["work"], ["sender", "missing"]), (["work", "missing"], ["target"])],
)
def test_invalid_target_rejects_the_whole_routing(topics: list[str], mentions: list[str]) -> None:
    with pytest.raises(RoomInputError, match="不存在"):
        build_message(
            room_state(),
            content="Message",
            topic_ids=topics,
            mentioned_member_ids=mentions,
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


def test_user_publisher_cannot_address_itself() -> None:
    user = next(member for member in room_state().members if member.kind == "human")
    with pytest.raises(RoomInputError, match="不能将消息发送给自己"):
        validate_sender_targets(user, ["user"])


def test_empty_topic_needs_an_explicit_recipient_and_body_mentions_do_not_route() -> None:
    state = room_state()
    state.topics.append(Topic(id="empty", name="Empty", description=""))
    with pytest.raises(RoomInputError, match="所选话题暂无成员"):
        build_message(
            state,
            content="同步进展 @target #work",
            topic_ids=["empty"],
            mentioned_member_ids=[],
            sender_id="user",
            sender_name="你",
            created_at=datetime.now(UTC),
            seq=1,
        )
    message = build_message(
        state,
        content="同步进展",
        topic_ids=["empty"],
        mentioned_member_ids=["target"],
        sender_id="user",
        sender_name="你",
        created_at=datetime.now(UTC),
        seq=1,
    )
    assert message.recipient_ids == ["target"]


@pytest.fixture
def publication() -> Message:
    first = SkillReference(id="skill-example", name="Example skill")
    return build_message(
        room_state(),
        content="Message",
        topic_ids=["work"],
        mentioned_member_ids=["target"],
        sender_id="sender",
        sender_name="Sender",
        created_at=datetime.now(UTC),
        seq=1,
        capabilities=[first, McpServerReference(id="server", name="MCP"), first],
    )


def test_capabilities_are_frozen_and_deduplicated_by_typed_identity(publication: Message) -> None:
    assert publication.capabilities == (
        SkillReference(id="skill-example", name="Example skill"),
        McpServerReference(id="server", name="MCP"),
    )
    validate_publication_replay(
        publication,
        content=publication.content,
        topic_ids=publication.topic_ids,
        mentions=publication.mentioned_member_ids,
        reply_to_message_id=None,
        capabilities=[
            capability.model_copy(update={"name": "Updated name"})
            for capability in reversed(publication.capabilities)
        ],
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"content": "Different"},
        {"topic_ids": []},
        {"mentioned_member_ids": ["user"]},
        {"reply_to_message_id": "another"},
        {"capabilities": []},
        {
            "capabilities": [
                McpServerReference(id="skill-example", name="Same ID, different type"),
                McpServerReference(id="server", name="MCP"),
            ]
        },
    ],
)
def test_publication_replay_rejects_changed_facts(
    publication: Message, changes: dict[str, object]
) -> None:
    proposed = publication.model_copy(update=changes)
    with pytest.raises(RoomConflictError, match="发布编号已用于另一条消息"):
        validate_publication_replay(
            publication,
            content=proposed.content,
            topic_ids=proposed.topic_ids,
            mentions=proposed.mentioned_member_ids,
            reply_to_message_id=proposed.reply_to_message_id,
            capabilities=proposed.capabilities,
        )
