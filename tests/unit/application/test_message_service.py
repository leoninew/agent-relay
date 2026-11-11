from unittest.mock import ANY, patch

import pytest
from support.fakes.rooms import MemoryRoomStore, sample_room
from support.session_fixtures import FakeQueueDriver, FakeSessionDriver

from agent_relay.application.members.contracts import UpdateMember
from agent_relay.application.members.service import MemberService
from agent_relay.application.messages.contracts import CreateMessage
from agent_relay.application.messages.ports import CodexQueueTarget
from agent_relay.application.messages.service import MessageService
from agent_relay.domain.rooms.errors import RoomConflictError, RoomInputError, RoomNotFoundError
from agent_relay.domain.rooms.models import Topic
from agent_relay.domain.rooms.state import RoomState


@pytest.fixture
def member_room() -> tuple[MessageService, RoomState]:
    state = sample_room()
    service = MessageService(MemoryRoomStore(state))
    return service, state


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
    changed: str,
) -> None:
    service, _ = member_room
    request = CreateMessage(
        publication_id="stable-audience",
        content="固定接收对象",
        topic_ids=["frontend"],
    )
    original = service.post_message("agent-relay", request, member_id="coordinator")
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
    next_message = service.post_message(
        "agent-relay",
        request.model_copy(update={"publication_id": "next"}),
        member_id="coordinator",
    )
    assert next_message.seq == original.seq + 1


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
def test_invalid_target_rejects_the_whole_publication_without_consuming_a_sequence(
    member_room: tuple[MessageService, RoomState], targets: dict[str, object]
) -> None:
    service, _ = member_room
    with pytest.raises(RoomInputError, match="不存在"):
        service.post_message(
            "agent-relay",
            CreateMessage.model_validate(
                {"publicationId": "invalid", "content": "不能部分投递", **targets}
            ),
        )
    with pytest.raises(RoomNotFoundError, match="发布记录不存在"):
        service.publication("agent-relay", "invalid")
    valid = service.post_message(
        "agent-relay",
        CreateMessage(publication_id="valid", content="Message", topic_ids=["backend"]),
    )
    assert valid.seq == 1


def test_empty_topic_needs_an_explicit_member_and_does_not_save_an_unroutable_message() -> None:
    state = sample_room()
    state.topics.append(Topic(id="empty", name="Empty", description=""))
    store = MemoryRoomStore(state)
    service = MessageService(store)
    request = CreateMessage(publication_id="empty", content="同步进展", topic_ids=["empty"])

    with pytest.raises(RoomInputError, match="所选话题暂无成员"):
        service.post_message(state.room.id, request)
    assert store.data.messages[state.room.id] == []

    message = service.post_message(
        state.room.id, request.model_copy(update={"mentioned_member_ids": ["backend-worker"]})
    )
    assert message.recipient_ids == ["backend-worker"]
    assert message.seq == 1


def test_subscription_edits_change_new_routing_and_preserve_previous_recipients() -> None:
    state = sample_room()
    store = MemoryRoomStore(state)
    service = MessageService(store)
    before = service.post_message(
        state.room.id,
        CreateMessage(publication_id="before", content="Message", topic_ids=["backend"]),
    )
    assert "frontend-worker" not in before.recipient_ids
    MemberService(store, FakeSessionDriver()).update_member(
        state.room.id,
        "frontend-worker",
        UpdateMember(name="Frontend", topic_ids=["frontend", "backend"]),
    )
    after = service.post_message(
        state.room.id,
        CreateMessage(publication_id="after", content="Message", topic_ids=["backend"]),
    )
    assert "frontend-worker" in after.recipient_ids
    assert service.publication(state.room.id, "before") == before


def test_queue_clear_releases_the_store_before_deleting_remote_items() -> None:
    store = MemoryRoomStore(sample_room())

    class CheckingDriver(FakeQueueDriver):
        def delete(self, thread_id: str, queued_submission_id: str) -> bool:
            assert store.active_scopes == 0
            return super().delete(thread_id, queued_submission_id)

    driver = CheckingDriver()
    driver.delete_results[("session-alpha", "queue-alpha")] = True
    targets = [
        CodexQueueTarget("session-alpha", "queue-alpha"),
        CodexQueueTarget("session-beta", "queue-beta"),
        CodexQueueTarget("session-gamma", None),
    ]
    with (
        patch.object(store.data, "clear_queue", return_value=2) as clear,
        patch.object(store.data, "codex_queue_targets", return_value=targets) as pending,
    ):
        result = MessageService(store).clear_queue_with_codex(
            "agent-relay", driver, topic_id="backend", member_id="test-worker"
        )
    clear.assert_called_once_with(
        "agent-relay", topic_id="backend", member_id="test-worker", deleted_at=ANY
    )
    pending.assert_called_once_with("agent-relay", topic_id="backend", member_id="test-worker")
    assert driver.deletions == [("session-alpha", "queue-alpha"), ("session-beta", "queue-beta")]
    assert result.removed_messages == 2
    assert result.codex_queue is not None
    assert result.codex_queue.deleted == result.codex_queue.not_found == 1
    assert result.codex_queue.without_receipt == 1
