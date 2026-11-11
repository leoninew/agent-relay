import logging
from datetime import UTC, datetime

import pytest
from support.fakes.delivery import MemoryDeliveryStore
from support.fakes.rooms import sample_room
from support.session_fixtures import FakeQueueDriver

from agent_relay.application.delivery.ports import (
    ActivationRejected,
    ClaimedDelivery,
    InputPage,
    QueueHead,
    QueueReceipt,
    QueueRejected,
    ReceivedInput,
)
from agent_relay.application.delivery.service import DeliveryService
from agent_relay.domain.rooms.delivery import (
    INTERRUPTED_SUBMISSION,
    PROCESSING_FAILURE,
    REJECTED_SUBMISSION,
    UNCERTAIN_SUBMISSION,
    SubmissionFailure,
    queue_accepted,
    submission_failed,
)
from agent_relay.domain.rooms.rules import build_message


def work_item() -> ClaimedDelivery:
    state = sample_room()
    message = build_message(
        state,
        content="Work",
        topic_ids=[],
        mentioned_member_ids=["frontend-worker"],
        sender_id="user",
        sender_name="你",
        created_at=datetime.now(UTC),
        seq=1,
    )
    delivery = message.deliveries[0].model_copy(update={"status": "submitting"})
    return ClaimedDelivery(state.room.id, state.room, message, delivery)


@pytest.mark.parametrize("rejected", [False, True])
def test_submission_records_rejection_or_uncertainty_without_repeating_the_write(
    rejected: bool,
) -> None:
    work = work_item()
    store = MemoryDeliveryStore(work)

    class FailingQueue(FakeQueueDriver):
        def enqueue(self, thread_id: str, client_message_id: str, text: str) -> QueueReceipt:
            super().enqueue(thread_id, client_message_id, text)
            if rejected:
                raise QueueRejected("rejected")
            raise TimeoutError("unknown")

    driver = FailingQueue()
    service = DeliveryService(store, driver, logging.getLogger("tests.delivery.actions"))
    service.submit(work)
    assert store.saved.status == ("rejected" if rejected else "unknown")
    assert len(driver.calls) == 1 and driver.activations == []
    if not rejected:
        driver.inputs[work.delivery.target_session_id] = [
            ReceivedInput(work.delivery.client_message_id, "input", "turn")
        ]
        service.observe(work.delivery.target_session_id, {work.delivery.client_message_id})
        assert str(store.saved.status) == "received"
        assert (store.saved.received_item_id, store.saved.received_turn_id) == ("input", "turn")
        assert len(driver.calls) == 1


def test_activation_rejection_preserves_the_saved_queue_receipt() -> None:
    work = work_item()
    store = MemoryDeliveryStore(work)

    class RejectedActivation(FakeQueueDriver):
        def activate(self, thread_id: str, queued_submission_id: str) -> str:
            raise ActivationRejected("already consumed")

    driver = RejectedActivation()
    driver.heads[work.delivery.target_session_id] = QueueHead(
        "queued", work.delivery.client_message_id
    )
    DeliveryService(store, driver, logging.getLogger("tests.delivery.activation")).submit(work)
    assert store.saved.status == "queued" and store.saved.queued_submission_id is not None
    assert store.saved.receipt is not None and store.activated
    assert len(driver.calls) == 1


def test_submission_includes_stable_message_lookup_facts() -> None:
    work = work_item()
    driver = FakeQueueDriver()
    DeliveryService(
        MemoryDeliveryStore(work), driver, logging.getLogger("tests.delivery.location")
    ).submit(work)

    assert len(driver.calls) == 1
    _, _, text = driver.calls[0]
    created_at = work.message.model_dump(mode="json", by_alias=True)["createdAt"]
    assert text == (
        f"roomId: {work.room_id}\n"
        f"messageId: {work.message.id}\n"
        f"seq: {work.message.seq}\n"
        f"createdAt: {created_at}\n"
        f"sender: {work.message.sender_name}（{work.message.sender_id}）\n\n"
        f"{work.message.content}"
    )


def test_removed_submission_does_not_trigger_activation_or_overwrite_the_marker() -> None:
    work = work_item()
    store = MemoryDeliveryStore(work)
    store.saved.deleted_at = datetime.now(UTC)
    deleted_at = store.saved.deleted_at
    driver = FakeQueueDriver()
    driver.heads[work.delivery.target_session_id] = QueueHead(
        "queued", work.delivery.client_message_id
    )
    DeliveryService(store, driver, logging.getLogger("tests.delivery.removed")).submit(work)
    assert store.saved.deleted_at == deleted_at
    assert store.saved.status == "submitting"
    assert not store.activated
    assert driver.activations == []


@pytest.mark.parametrize(
    "failure",
    [REJECTED_SUBMISSION, UNCERTAIN_SUBMISSION, PROCESSING_FAILURE, INTERRUPTED_SUBMISSION],
)
def test_submission_failure_preserves_identity_and_does_not_mutate_claim(
    failure: SubmissionFailure,
) -> None:
    original = work_item().delivery
    before = original.model_copy(deep=True)
    at = datetime.now(UTC)
    result = submission_failed(original, failure, at)
    assert original == before and result.id == original.id
    assert result.client_message_id == original.client_message_id
    assert result.status == failure.status and result.error == failure.error
    assert result.updated_at == at and result.queued_submission_id is None


def test_saved_queue_receipt_cannot_be_replaced_by_a_late_failure() -> None:
    delivery = work_item().delivery
    queued = queue_accepted(delivery, "submission", {"id": "receipt"}, datetime.now(UTC))
    with pytest.raises(ValueError):
        submission_failed(queued, PROCESSING_FAILURE, datetime.now(UTC))
    assert queued.status == "queued" and queued.receipt == {"id": "receipt"}
    assert delivery.status == "submitting" and delivery.receipt is None


def test_recovery_does_not_attempt_external_resubmission() -> None:
    store = MemoryDeliveryStore(work_item())
    driver = FakeQueueDriver()
    service = DeliveryService(store, driver, logging.getLogger("tests.delivery.recovery"))
    service.recover()
    service.recover()
    assert store.saved.status == "unknown"
    assert not driver.calls and not driver.activations


def test_receipt_observation_continues_to_an_older_page_without_resubmitting() -> None:
    work = work_item()
    store = MemoryDeliveryStore(work)
    cursors: list[str | None] = []

    class HistoryDriver(FakeQueueDriver):
        def read_input_page(self, thread_id: str, cursor: str | None = None) -> InputPage:
            cursors.append(cursor)
            if cursor is None:
                return InputPage((), "older")
            return InputPage(
                (ReceivedInput(work.delivery.client_message_id, "original-item", "original-turn"),),
                None,
            )

    driver = HistoryDriver()
    service = DeliveryService(store, driver, logging.getLogger("tests.delivery.history"))
    for _ in range(2):
        service.observe(work.delivery.target_session_id, {work.delivery.client_message_id})
    assert cursors == [None, None, "older"]
    assert store.saved.received_item_id == "original-item"
    assert not driver.calls and not driver.activations
