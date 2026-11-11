import logging
from datetime import UTC, datetime

import pytest
from fakes.delivery import MemoryDeliveryStore
from fakes.rooms import sample_room
from session_fixtures import FakeQueueDriver

from agent_relay.application.delivery.ports import (
    ActivationRejected,
    ClaimedDelivery,
    QueueHead,
    QueueReceipt,
    QueueRejected,
    ReceivedInput,
)
from agent_relay.application.delivery.service import DeliveryService
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
