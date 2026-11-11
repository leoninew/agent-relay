import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import event, update
from sqlalchemy.orm import Session
from sqlalchemy.pool import QueuePool
from support.databases import MemoryDatabases
from support.session_fixtures import FakeQueueDriver
from support.sqlalchemy_message_fixtures import ROOM_ID, MessageTestStore, seed_message_store

from agent_relay.application.delivery.ports import (
    ClaimedDelivery,
    QueueHead,
    QueueReceipt,
    ReceivedInput,
)
from agent_relay.application.delivery.service import DeliveryService
from agent_relay.application.messages.contracts import CreateMessage
from agent_relay.application.messages.service import MessageService
from agent_relay.domain.rooms.models import Delivery, Message
from agent_relay.infrastructure.persistence.delivery_store import SQLAlchemyDeliveryStore
from agent_relay.infrastructure.persistence.models import DeliveryRecord, RoomEventRecord


@pytest.fixture
def store(tmp_path: Path, databases: MemoryDatabases) -> MessageTestStore:
    return seed_message_store(databases.create(tmp_path / "deliveries.sqlite3"))


@pytest.fixture
def deliveries(store: MessageTestStore) -> SQLAlchemyDeliveryStore:
    return SQLAlchemyDeliveryStore(store.database)


def publish(store: MessageTestStore, targets: list[str]) -> Message:
    return MessageService(store).post_message(
        ROOM_ID,
        CreateMessage(publication_id=uuid4().hex, content="Delivery", mentioned_member_ids=targets),
    )


def claim(deliveries: SQLAlchemyDeliveryStore) -> ClaimedDelivery:
    work = deliveries.claim_delivery()
    assert work is not None
    return work


def queued(work: ClaimedDelivery) -> Delivery:
    result = work.delivery.model_copy(deep=True)
    result.status = "queued"
    result.queued_submission_id = "queue-" + result.client_message_id
    result.queued_at = result.updated_at = datetime.now(UTC)
    result.receipt = {
        "id": result.queued_submission_id,
        "clientUserMessageId": result.client_message_id,
    }
    return result


def test_claim_is_fifo_and_excludes_concurrent_submissions_for_the_same_session(
    store: MessageTestStore, deliveries: SQLAlchemyDeliveryStore
) -> None:
    first = publish(store, ["alpha", "beta"])
    second = publish(store, ["alpha"])
    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(lambda _: deliveries.claim_delivery(), range(4)))
    claimed = [work for work in results if work is not None]
    assert {work.message.id for work in claimed} == {first.id}
    assert {work.delivery.target_member_id for work in claimed} == {"alpha", "beta"}
    assert len({work.delivery.id for work in claimed}) == 2
    alpha = next(work for work in claimed if work.delivery.target_member_id == "alpha")
    assert deliveries.finish_delivery(ROOM_ID, queued(alpha))
    assert claim(deliveries).message.id == second.id


def test_finish_preserves_identity_and_rejects_repeated_or_wrong_receipts(
    store: MessageTestStore, deliveries: SQLAlchemyDeliveryStore
) -> None:
    message = publish(store, ["alpha"])
    work = claim(deliveries)
    result = queued(work)
    wrong = result.model_copy(deep=True)
    wrong.client_message_id = "wrong"
    assert wrong.receipt is not None
    wrong.receipt["clientUserMessageId"] = "wrong"
    assert not deliveries.finish_delivery(ROOM_ID, wrong)
    result.target_session_id = "wrong"
    assert deliveries.finish_delivery(ROOM_ID, result)
    assert not deliveries.finish_delivery(ROOM_ID, result)
    saved = store.queries.message(ROOM_ID, message.id).deliveries[0]
    assert saved.target_session_id == work.delivery.target_session_id
    assert saved.receipt == result.receipt


def test_activation_matches_the_saved_head_and_is_claimed_once(
    store: MessageTestStore, deliveries: SQLAlchemyDeliveryStore
) -> None:
    publish(store, ["alpha"])
    work = claim(deliveries)
    result = queued(work)
    assert deliveries.finish_delivery(ROOM_ID, result)
    session_id = result.target_session_id
    assert not deliveries.claim_activation(session_id, QueueHead("wrong", result.client_message_id))
    head = QueueHead(result.queued_submission_id or "", result.client_message_id)
    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(
            workers.map(lambda _: deliveries.claim_activation(session_id, head), range(2))
        )
    assert results.count(True) == 1


@pytest.mark.parametrize("status", ["queued", "unknown"])
def test_only_the_original_input_can_confirm_an_unresolved_delivery(
    store: MessageTestStore, deliveries: SQLAlchemyDeliveryStore, status: str
) -> None:
    message = publish(store, ["alpha"])
    work = claim(deliveries)
    result = queued(work)
    assert deliveries.finish_delivery(ROOM_ID, result)
    with store.database.write() as session:
        session.execute(
            update(DeliveryRecord).where(DeliveryRecord.id == result.id).values(status=status)
        )
    deliveries.confirm_input(
        "session-beta", ReceivedInput(result.client_message_id, "wrong", "wrong")
    )
    assert store.queries.message(ROOM_ID, message.id).deliveries[0].status == status
    received = ReceivedInput(result.client_message_id, "original-item", "original-turn")
    deliveries.confirm_input(result.target_session_id, received)
    saved = store.queries.message(ROOM_ID, message.id).deliveries[0]
    assert saved.status == "received" and saved.received_item_id == "original-item"
    deliveries.confirm_input(
        result.target_session_id, ReceivedInput(result.client_message_id, "late", "late")
    )
    assert store.queries.message(ROOM_ID, message.id).deliveries[0] == saved


def test_recovery_marks_interrupted_submissions_unknown_without_requeuing(
    store: MessageTestStore, deliveries: SQLAlchemyDeliveryStore
) -> None:
    message = publish(store, ["alpha"])
    claim(deliveries)
    deliveries.interrupt_submissions()
    assert store.queries.message(ROOM_ID, message.id).deliveries[0].status == "unknown"
    assert deliveries.claim_delivery() is None


def test_clear_racing_with_claim_cannot_be_undone_by_a_late_result(
    store: MessageTestStore, deliveries: SQLAlchemyDeliveryStore
) -> None:
    message = publish(store, ["alpha"])
    barrier = Barrier(2)

    def take() -> ClaimedDelivery | None:
        barrier.wait(timeout=5)
        return deliveries.claim_delivery()

    def clear() -> None:
        barrier.wait(timeout=5)
        MessageService(store).clear_queue(ROOM_ID)

    with ThreadPoolExecutor(max_workers=2) as workers:
        claimed = workers.submit(take)
        workers.submit(clear).result(timeout=5)
        work = claimed.result(timeout=5)
    if work is not None:
        assert not deliveries.finish_delivery(ROOM_ID, queued(work))
    assert deliveries.claim_delivery() is None
    assert store.queries.message(ROOM_ID, message.id).deliveries[0].deleted_at is not None


def test_claim_and_its_event_roll_back_together(
    store: MessageTestStore, deliveries: SQLAlchemyDeliveryStore
) -> None:
    message = publish(store, ["alpha"])

    def fail_event(session: Session, context: object, instances: object) -> None:
        if any(isinstance(record, RoomEventRecord) for record in session.new):
            raise RuntimeError("event failed")

    event.listen(Session, "before_flush", fail_event)
    try:
        with pytest.raises(RuntimeError, match="event failed"):
            deliveries.claim_delivery()
    finally:
        event.remove(Session, "before_flush", fail_event)
    assert store.queries.message(ROOM_ID, message.id).deliveries[0].status == "pending"
    assert claim(deliveries).message.id == message.id


def test_submission_releases_its_connection_before_the_rpc(
    store: MessageTestStore, deliveries: SQLAlchemyDeliveryStore
) -> None:
    publish(store, ["alpha"])
    work = claim(deliveries)

    class ObservingDriver(FakeQueueDriver):
        def enqueue(self, thread_id: str, client_message_id: str, text: str) -> QueueReceipt:
            pool = store.database.engine.pool
            assert isinstance(pool, QueuePool) and pool.checkedout() == 0
            with store.database.write():
                pass
            return super().enqueue(thread_id, client_message_id, text)

    driver = ObservingDriver()
    DeliveryService(deliveries, driver, logging.getLogger("tests.delivery.boundary")).submit(work)
    assert len(driver.calls) == 1
    assert store.queries.message(ROOM_ID, work.message.id).deliveries[0].status == "queued"
