from unittest.mock import ANY, MagicMock, Mock, call

import pytest

from agent_relay.application.delivery.ports import QueueDriver
from agent_relay.application.messages.contracts import CreateMessage
from agent_relay.application.messages.ports import CodexQueueTarget
from agent_relay.application.messages.service import MessageService
from agent_relay.domain.rooms.errors import RoomConflictError, RoomInputError
from agent_relay.domain.rooms.models import McpServerReference, SkillReference, Topic
from agent_relay.domain.rooms.state import RoomState


@pytest.fixture
def member_room(room_state: RoomState, room_store: MagicMock) -> tuple[MessageService, RoomState]:
    return MessageService(room_store), room_state


@pytest.mark.parametrize(
    ("topics", "mentions", "recipients"),
    [
        (["frontend"], [], ["coordinator", "test-worker"]),
        ([], ["frontend-worker", "backend-worker"], ["backend-worker"]),
        (
            ["backend"],
            ["frontend-worker", "backend-worker"],
            ["coordinator", "backend-worker", "test-worker"],
        ),
    ],
)
def test_member_message_service_routes_the_explicit_targets(
    member_room: tuple[MessageService, RoomState],
    topics: list[str],
    mentions: list[str],
    recipients: list[str],
) -> None:
    service, _ = member_room
    message = service.post_message(
        "agent-relay",
        CreateMessage(
            publication_id="member-publication",
            content="Message",
            topic_ids=topics,
            mentioned_member_ids=mentions,
        ),
        member_id="frontend-worker",
    )
    assert message.sender_id == "frontend-worker"
    assert message.recipient_ids == recipients
    assert [delivery.target_member_id for delivery in message.deliveries] == recipients


def test_user_publisher_cannot_address_itself(
    member_room: tuple[MessageService, RoomState],
) -> None:
    service, _ = member_room
    request = CreateMessage(
        publication_id="user-self",
        content="不能发给自己",
        mentioned_member_ids=["user"],
    )

    with pytest.raises(RoomInputError, match="不能将消息发送给自己"):
        service.post_message("agent-relay", request)


@pytest.mark.parametrize("changed", ["content", "topics", "mentions", "reply"])
def test_publication_replay_rejects_changed_facts_without_another_write(
    member_room: tuple[MessageService, RoomState],
    room_repository: Mock,
    changed: str,
) -> None:
    service, _ = member_room
    request = CreateMessage(
        publication_id="stable-audience",
        content="固定接收对象",
        topic_ids=["frontend"],
    )
    original = service.post_message("agent-relay", request, member_id="coordinator")
    room_repository.publication.return_value = original
    changes: dict[str, object] = {
        "content": "Different",
        "topics": ["backend"],
        "mentions": ["user"],
        "reply": "missing",
    }
    fields = {
        "content": "content",
        "topics": "topic_ids",
        "mentions": "mentioned_member_ids",
        "reply": "reply_to_message_id",
    }

    with pytest.raises(RoomConflictError, match="发布编号已用于另一条消息"):
        service.post_message(
            "agent-relay",
            request.model_copy(update={fields[changed]: changes[changed]}),
            member_id="coordinator",
        )
    assert (
        service.publication("agent-relay", "stable-audience", member_id="coordinator") == original
    )
    room_repository.insert_message.assert_called_once()
    room_repository.next_message_seq.assert_called_once_with("agent-relay")


def test_body_mentions_do_not_affect_explicit_routing(
    member_room: tuple[MessageService, RoomState],
) -> None:
    service, _ = member_room
    message = service.post_message(
        "agent-relay",
        CreateMessage(
            publication_id="body-mentions",
            content="同步前端进展 @backend-worker #backend",
            topic_ids=["frontend"],
        ),
    )
    assert message.mentioned_member_ids == []
    assert message.recipient_ids == ["coordinator", "frontend-worker", "test-worker"]
    assert [delivery.target_member_id for delivery in message.deliveries] == message.recipient_ids


@pytest.mark.parametrize("topic_payload", [{}, {"topicIds": []}])
def test_direct_mentions_do_not_require_a_topic(
    member_room: tuple[MessageService, RoomState], topic_payload: dict[str, object]
) -> None:
    service, _ = member_room
    message = service.post_message(
        "agent-relay",
        CreateMessage.model_validate(
            {
                "publicationId": "direct",
                "content": "请核对界面",
                "mentionedMemberIds": ["frontend-worker"],
                **topic_payload,
            }
        ),
    )
    assert message.topic_ids == []
    assert message.mentioned_member_ids == message.recipient_ids == ["frontend-worker"]
    assert len(message.deliveries) == 1 and message.deliveries[0].status == "pending"


def test_mentions_and_subscriptions_combine_without_duplicate_deliveries(
    member_room: tuple[MessageService, RoomState],
) -> None:
    service, _ = member_room
    message = service.post_message(
        "agent-relay",
        CreateMessage(
            publication_id="combined",
            content="请前后端一起核对",
            topic_ids=["backend", "backend"],
            mentioned_member_ids=["frontend-worker", "test-worker", "frontend-worker"],
        ),
    )
    assert message.topic_ids == ["backend"]
    assert message.mentioned_member_ids == ["frontend-worker", "test-worker"]
    assert message.recipient_ids == [
        "coordinator",
        "frontend-worker",
        "backend-worker",
        "test-worker",
    ]
    assert [delivery.target_member_id for delivery in message.deliveries] == message.recipient_ids


@pytest.mark.parametrize(
    "targets",
    [
        {"topicIds": ["backend"], "mentionedMemberIds": ["test-worker", "missing"]},
        {"topicIds": ["backend", "missing"], "mentionedMemberIds": ["test-worker"]},
    ],
)
def test_invalid_target_rejects_the_whole_publication_without_writing(
    member_room: tuple[MessageService, RoomState],
    room_repository: Mock,
    targets: dict[str, object],
) -> None:
    service, _ = member_room
    with pytest.raises(RoomInputError, match="不存在"):
        service.post_message(
            "agent-relay",
            CreateMessage.model_validate(
                {"publicationId": "invalid", "content": "不能部分投递", **targets}
            ),
        )
    room_repository.insert_message.assert_not_called()


def test_empty_topic_needs_an_explicit_member_and_does_not_save_an_unroutable_message(
    room_state: RoomState,
    room_store: MagicMock,
    room_repository: Mock,
) -> None:
    state = room_state
    state.topics.append(Topic(id="empty", name="Empty", description=""))
    service = MessageService(room_store)
    request = CreateMessage(publication_id="empty", content="同步进展", topic_ids=["empty"])

    with pytest.raises(RoomInputError, match="所选话题暂无成员"):
        service.post_message(state.room.id, request)
    room_repository.insert_message.assert_not_called()

    message = service.post_message(
        state.room.id, request.model_copy(update={"mentioned_member_ids": ["backend-worker"]})
    )
    assert message.recipient_ids == ["backend-worker"]
    room_repository.insert_message.assert_called_once_with(state.room.id, message)


def test_publication_replay_preserves_recipients_after_subscription_changes(
    room_state: RoomState,
    room_store: MagicMock,
    room_repository: Mock,
) -> None:
    state = room_state
    service = MessageService(room_store)
    request = CreateMessage(publication_id="before", content="Message", topic_ids=["backend"])
    before = service.post_message(state.room.id, request)
    assert "frontend-worker" not in before.recipient_ids
    next(member for member in state.members if member.id == "frontend-worker").topic_ids.append(
        "backend"
    )
    room_repository.publication.return_value = before
    assert service.post_message(state.room.id, request) == before
    room_repository.insert_message.assert_called_once()


def test_queue_clear_releases_the_store_before_deleting_remote_items(
    room_store: MagicMock,
    room_repository: Mock,
) -> None:
    driver = Mock(spec=QueueDriver)

    def delete(thread_id: str, queued_submission_id: str) -> bool:
        room_store.write.return_value.__exit__.assert_called_once_with(None, None, None)
        return thread_id == "session-alpha"

    driver.delete.side_effect = delete
    targets = [
        CodexQueueTarget("session-alpha", "queue-alpha"),
        CodexQueueTarget("session-beta", "queue-beta"),
        CodexQueueTarget("session-gamma", None),
    ]
    room_repository.clear_queue.return_value = 2
    room_repository.codex_queue_targets.return_value = targets
    result = MessageService(room_store).clear_queue_with_codex(
        "agent-relay", driver, topic_id="backend", member_id="test-worker"
    )
    room_repository.clear_queue.assert_called_once_with(
        "agent-relay", topic_id="backend", member_id="test-worker", deleted_at=ANY
    )
    room_repository.codex_queue_targets.assert_called_once_with(
        "agent-relay", topic_id="backend", member_id="test-worker"
    )
    assert driver.delete.call_args_list == [
        call("session-alpha", "queue-alpha"),
        call("session-beta", "queue-beta"),
    ]
    assert result.removed_messages == 2
    assert result.codex_queue is not None
    assert result.codex_queue.deleted == result.codex_queue.not_found == 1
    assert result.codex_queue.without_receipt == 1


def test_capabilities_are_frozen_deduplicated_and_replayed_by_typed_identity(
    room_store: MagicMock,
    room_repository: Mock,
) -> None:
    service = MessageService(room_store)
    first = SkillReference(id="skill-example", name="Example skill")
    second = McpServerReference(id="example", name="Example MCP")
    third = SkillReference(id="skill-third", name="Third skill")
    request = CreateMessage(
        publication_id="capabilities",
        content="Use these capabilities",
        topic_ids=["frontend"],
        capabilities=[
            first,
            second,
            first.model_copy(update={"name": "Later display name"}),
            third,
        ],
    )
    original = service.post_message("agent-relay", request)
    room_repository.publication.return_value = original
    assert original.capabilities == (first, second, third)
    request.capabilities.clear()
    assert service.publication("agent-relay", "capabilities").capabilities == (
        first,
        second,
        third,
    )
    replay = request.model_copy(
        update={
            "capabilities": [
                third,
                second,
                first.model_copy(update={"name": "New display snapshot"}),
            ]
        }
    )
    assert service.post_message("agent-relay", replay) == original
    for changed in (
        [],
        [second],
        [McpServerReference(id=first.id, name=first.name), second],
    ):
        with pytest.raises(RoomConflictError):
            service.post_message(
                "agent-relay", request.model_copy(update={"capabilities": changed})
            )
    room_repository.insert_message.assert_called_once()
