from datetime import UTC, datetime
from unittest.mock import ANY, MagicMock, Mock, call

import pytest

from agent_relay.application.delivery.ports import QueueDriver
from agent_relay.application.dto.messages import CodexQueueTarget, CreateMessage
from agent_relay.application.messages.service import MessageService
from agent_relay.domain.rooms.errors import RoomConflictError, RoomInputError, RoomNotFoundError
from agent_relay.domain.rooms.models import Message, RoomState


@pytest.fixture
def message() -> Message:
    return Message(
        id="message-one",
        publication_id="publication-one",
        seq=7,
        sender_id="frontend-worker",
        sender_name="Frontend",
        content="Message",
        topic_ids=["backend"],
        mentioned_member_ids=["test-worker"],
        recipient_ids=["test-worker"],
        created_at=datetime.now(UTC),
        deliveries=[],
    )


def test_publication_normalizes_targets_and_saves_the_domain_result(
    room_state: RoomState,
    room_store: MagicMock,
    room_repository: Mock,
    message: Message,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build = Mock(return_value=message)
    monkeypatch.setattr("agent_relay.application.messages.service.build_message", build)
    room_repository.next_message_seq.return_value = message.seq
    request = CreateMessage(
        publication_id="publication-one",
        content=message.content,
        topic_ids=["backend", "backend"],
        mentioned_member_ids=["test-worker", "test-worker"],
    )

    result = MessageService(room_store).post_message(
        "agent-relay", request, member_id="frontend-worker"
    )

    build.assert_called_once_with(
        room_state,
        content=request.content,
        topic_ids=["backend"],
        mentioned_member_ids=["test-worker"],
        sender_id="frontend-worker",
        sender_name="frontend-worker",
        created_at=ANY,
        reply_to_message_id=None,
        publication_id=request.publication_id,
        seq=message.seq,
        capabilities=request.capabilities,
    )
    room_repository.insert_message.assert_called_once_with("agent-relay", message)
    assert result == message and result is not message


def test_domain_rejection_does_not_save_a_partial_publication(
    room_store: MagicMock, room_repository: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "agent_relay.application.messages.service.build_message",
        Mock(side_effect=RoomInputError("无接收人")),
    )

    with pytest.raises(RoomInputError, match="无接收人"):
        MessageService(room_store).post_message(
            "agent-relay",
            CreateMessage(publication_id="invalid", content="Message", topic_ids=["frontend"]),
        )

    room_repository.insert_message.assert_not_called()


def test_publication_replay_returns_saved_facts_without_routing_or_writing_again(
    room_store: MagicMock, room_repository: Mock, message: Message, monkeypatch: pytest.MonkeyPatch
) -> None:
    validate_replay = Mock()
    monkeypatch.setattr(
        "agent_relay.application.messages.service.validate_publication_replay", validate_replay
    )
    room_repository.publication.return_value = message
    room_repository.message_exists.return_value = True
    request = CreateMessage(
        publication_id="publication-one",
        content=message.content,
        topic_ids=message.topic_ids,
        mentioned_member_ids=message.mentioned_member_ids,
    )

    service = MessageService(room_store)
    assert service.post_message("agent-relay", request, member_id="frontend-worker") == message
    assert service.publication("agent-relay", request.publication_id) == message
    validate_replay.assert_called_once_with(
        message,
        content=request.content,
        topic_ids=request.topic_ids,
        mentions=request.mentioned_member_ids,
        reply_to_message_id=request.reply_to_message_id,
        capabilities=request.capabilities,
    )
    room_repository.resources.assert_not_called()
    room_repository.next_message_seq.assert_not_called()
    room_repository.insert_message.assert_not_called()


def test_cleared_publication_cannot_be_replayed_or_found_by_publication_id(
    room_store: MagicMock, room_repository: Mock, message: Message
) -> None:
    room_repository.publication.return_value = message
    room_repository.message_exists.return_value = False
    service = MessageService(room_store)
    request = CreateMessage(publication_id="cleared", content="Message", topic_ids=["frontend"])

    with pytest.raises(RoomConflictError, match="该发布记录已清空"):
        service.post_message("agent-relay", request)
    with pytest.raises(RoomNotFoundError, match="发布记录不存在"):
        service.publication("agent-relay", request.publication_id)

    room_repository.insert_message.assert_not_called()


@pytest.mark.parametrize("removed", [0, 1])
def test_queue_message_deletion_targets_only_the_requested_message(
    room_store: MagicMock, room_repository: Mock, removed: int
) -> None:
    room_repository.message_exists.return_value = True
    room_repository.clear_queue.return_value = removed

    result = MessageService(room_store).delete_queue_message("agent-relay", "message-one")

    room_repository.message_exists.assert_called_once_with("agent-relay", "message-one")
    room_repository.clear_queue.assert_called_once_with(
        "agent-relay", topic_id=None, member_id=None, message_id="message-one", deleted_at=ANY
    )
    assert result.removed_messages == removed
    assert result.codex_queue is None


def test_queue_message_deletion_rejects_a_missing_message_without_clearing_the_queue(
    room_store: MagicMock, room_repository: Mock
) -> None:
    room_repository.message_exists.return_value = False

    with pytest.raises(RoomNotFoundError, match="消息不存在"):
        MessageService(room_store).delete_queue_message("agent-relay", "missing")

    room_repository.clear_queue.assert_not_called()


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
