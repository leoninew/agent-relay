import logging
from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import Mock, call

import pytest

from agent_relay.application.delivery.ports import (
    ActivationRejected,
    ClaimedDelivery,
    DeliveryDriver,
    DeliveryRepository,
    InputHistoryUnavailable,
    InputPage,
    QueueHead,
    QueueReceipt,
    ReceivedInput,
    SteerReceipt,
    SubmissionRejected,
    SubmissionUnknown,
)
from agent_relay.application.delivery.service import DeliveryService
from agent_relay.domain.rooms.models import Delivery, Message, Room, SkillReference


@pytest.fixture
def work() -> ClaimedDelivery:
    now = datetime.now(UTC)
    delivery = Delivery(
        id="delivery",
        target_member_id="target",
        target_session_id="original-session",
        client_message_id="client",
        status="submitting",
        updated_at=now,
    )
    message = Message(
        id="message",
        seq=1,
        sender_id="user",
        sender_name="你",
        content="Work",
        topic_ids=[],
        mentioned_member_ids=["target"],
        recipient_ids=["target"],
        created_at=now,
        deliveries=[delivery],
    )
    room = Room(id="room", name="Room", project_path="d:/project", description="")
    return ClaimedDelivery(room.id, room, message, delivery)


@pytest.fixture
def delivery_store() -> Mock:
    store = Mock(spec=DeliveryRepository)
    store.finish_delivery.return_value = True
    store.claim_activation.return_value = True
    return store


@pytest.fixture
def queue_driver() -> Mock:
    driver = Mock(spec=DeliveryDriver)
    driver.submit.return_value = QueueReceipt("queued", {"id": "queued"})
    driver.activation_candidate.return_value = None
    return driver


@pytest.mark.parametrize("rejected", [False, True])
def test_submission_records_rejection_or_uncertainty_without_repeating_the_write(
    work: ClaimedDelivery,
    delivery_store: Mock,
    queue_driver: Mock,
    rejected: bool,
) -> None:
    queue_driver.submit.side_effect = (
        SubmissionRejected("rejected", "steer")
        if rejected
        else SubmissionUnknown("unknown", "steer")
    )
    DeliveryService(delivery_store, queue_driver, logging.getLogger("tests.delivery")).submit(work)
    delivery_store.finish_delivery.assert_called_once()
    room_id, saved = delivery_store.finish_delivery.call_args.args
    assert room_id == work.room_id
    assert saved.status == ("rejected" if rejected else "unknown")
    assert saved.submission_method == "steer"
    queue_driver.submit.assert_called_once()
    queue_driver.activation_candidate.assert_not_called()
    queue_driver.activate.assert_not_called()


def test_activation_rejection_preserves_the_saved_queue_receipt(
    work: ClaimedDelivery,
    delivery_store: Mock,
    queue_driver: Mock,
) -> None:
    queue_driver.activation_candidate.return_value = QueueHead(
        "queued", work.delivery.client_message_id
    )
    queue_driver.activate.side_effect = ActivationRejected("already consumed")
    DeliveryService(delivery_store, queue_driver, logging.getLogger("tests.delivery")).submit(work)
    saved = delivery_store.finish_delivery.call_args.args[1]
    assert saved.status == "queued" and saved.queued_submission_id == "queued"
    assert saved.receipt == {"id": "queued"}
    queue_driver.submit.assert_called_once()
    queue_driver.activate.assert_called_once_with(work.delivery.target_session_id, "queued")
    assert saved.error is None
    assert "启动请求未被接受" in delivery_store.delivery_note.call_args.args[2]


def test_submission_includes_stable_message_lookup_facts_and_capabilities(
    work: ClaimedDelivery,
    delivery_store: Mock,
    queue_driver: Mock,
) -> None:
    references = (SkillReference(id="skill-example", name="Example"),)
    work = replace(work, message=work.message.model_copy(update={"capabilities": references}))
    DeliveryService(delivery_store, queue_driver, logging.getLogger("tests.delivery")).submit(work)
    queue_driver.submit.assert_called_once()
    thread_id, client_id, request = queue_driver.submit.call_args.args
    assert thread_id == work.delivery.target_session_id
    assert client_id == work.delivery.client_message_id
    assert request.capabilities == references and request.project_path == work.room.project_path
    created_at = work.message.model_dump(mode="json", by_alias=True)["createdAt"]
    assert request.text == (
        f"roomId: {work.room_id}\n"
        f"messageId: {work.message.id}\n"
        f"seq: {work.message.seq}\n"
        f"createdAt: {created_at}\n"
        f"sender: {work.message.sender_name}（{work.message.sender_id}）\n\n"
        f"{work.message.content}"
    )


def test_unsaved_receipt_does_not_trigger_activation(
    work: ClaimedDelivery,
    delivery_store: Mock,
    queue_driver: Mock,
) -> None:
    delivery_store.finish_delivery.return_value = False
    queue_driver.activation_candidate.return_value = QueueHead(
        "queued", work.delivery.client_message_id
    )
    DeliveryService(delivery_store, queue_driver, logging.getLogger("tests.delivery")).submit(work)
    queue_driver.submit.assert_called_once()
    delivery_store.finish_delivery.assert_called_once()
    queue_driver.activation_candidate.assert_not_called()
    queue_driver.activate.assert_not_called()


def test_recovery_does_not_attempt_external_resubmission(
    delivery_store: Mock,
    queue_driver: Mock,
) -> None:
    DeliveryService(delivery_store, queue_driver, logging.getLogger("tests.delivery")).recover()
    delivery_store.interrupt_submissions.assert_called_once_with()
    assert queue_driver.mock_calls == []


def test_receipt_observation_continues_to_an_older_page_without_resubmitting(
    work: ClaimedDelivery,
    delivery_store: Mock,
    queue_driver: Mock,
) -> None:
    received = ReceivedInput(work.delivery.client_message_id, "original-item", "original-turn")
    queue_driver.read_input_page.side_effect = [
        InputPage((), "older"),
        InputPage((), "older"),
        InputPage((received,), None),
    ]
    service = DeliveryService(delivery_store, queue_driver, logging.getLogger("tests.delivery"))
    for _ in range(2):
        service.observe(work.delivery.target_session_id, {work.delivery.client_message_id})
    assert queue_driver.read_input_page.call_args_list == [
        call(work.delivery.target_session_id),
        call(work.delivery.target_session_id),
        call(work.delivery.target_session_id, "older"),
    ]
    delivery_store.confirm_input.assert_called_once_with(work.delivery.target_session_id, received)
    queue_driver.submit.assert_not_called()
    queue_driver.activate.assert_not_called()


def test_steer_receipt_is_saved_without_queue_activation_or_false_history_confirmation(
    work: ClaimedDelivery, delivery_store: Mock, queue_driver: Mock
) -> None:
    queue_driver.submit.return_value = SteerReceipt("active-turn")
    DeliveryService(delivery_store, queue_driver, logging.getLogger("tests.delivery")).submit(work)
    saved = delivery_store.finish_delivery.call_args.args[1]
    assert saved.status == "queued" and saved.submission_method == "steer"
    assert saved.steered_turn_id == "active-turn"
    assert saved.received_at is None and saved.received_turn_id is None
    assert saved.queued_submission_id is None and saved.receipt is None
    queue_driver.activation_candidate.assert_not_called()
    queue_driver.activate.assert_not_called()
    delivery_store.confirm_input.assert_not_called()


def test_queue_fallback_reason_survives_activation_note(
    work: ClaimedDelivery, delivery_store: Mock, queue_driver: Mock
) -> None:
    queue_driver.submit.return_value = QueueReceipt("queued", {"id": "queued"}, "Fallback reason")
    DeliveryService(delivery_store, queue_driver, logging.getLogger("tests.delivery")).submit(work)
    assert delivery_store.finish_delivery.call_args.args[1].note == "Fallback reason"
    assert delivery_store.delivery_note.call_args.args[2] == "Fallback reason"


def test_observation_failure_or_unrelated_input_never_confirms_or_resends(
    delivery_store: Mock, queue_driver: Mock
) -> None:
    queue_driver.read_input_page.side_effect = [
        TimeoutError("Unavailable"),
        InputPage((ReceivedInput("other-client", "item", "turn"),), None),
    ]
    service = DeliveryService(delivery_store, queue_driver, logging.getLogger("tests.delivery"))
    service.observe("original-session", {"client"})
    service.observe("original-session", {"client"})
    delivery_store.confirm_input.assert_not_called()
    queue_driver.submit.assert_not_called()
    queue_driver.activate.assert_not_called()


def test_unavailable_history_logs_once_and_observation_recovers_without_resubmission(
    delivery_store: Mock, queue_driver: Mock
) -> None:
    received = ReceivedInput("client", "item", "turn")
    queue_driver.read_input_page.side_effect = [
        InputHistoryUnavailable("Session is not loaded"),
        InputHistoryUnavailable("Session is not loaded"),
        InputPage((received,), None),
        InputHistoryUnavailable("Session is not loaded"),
    ]
    logger = Mock(spec=logging.Logger)
    service = DeliveryService(delivery_store, queue_driver, logger)
    for _ in range(2):
        service.observe("original-session", {"client"})
    logger.info.assert_called_once()
    delivery_store.confirm_input.assert_not_called()
    service.observe("original-session", {"client"})
    delivery_store.confirm_input.assert_called_once_with("original-session", received)
    service.observe("original-session", {"client"})
    assert logger.info.call_count == 2
    logger.exception.assert_not_called()
    queue_driver.submit.assert_not_called()
    queue_driver.activate.assert_not_called()
