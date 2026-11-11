import logging
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
from session_fixtures import FakeQueueDriver
from sqlalchemy import event, select, update
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session
from sqlalchemy.pool import ConnectionPoolEntry
from sqlalchemy_message_fixtures import ROOM_ID, MessageTestStore, seed_message_store

from agent_relay.application.delivery.ports import (
    ActivationRejected,
    ClaimedDelivery,
    DeliveryRepository,
    DeliveryStore,
    InputPage,
    QueueHead,
    QueueReceipt,
    QueueRejected,
    ReceivedInput,
)
from agent_relay.application.delivery.service import DeliveryService
from agent_relay.application.rooms.contracts import CreateMessage, UpdateMember
from agent_relay.application.rooms.service import RoomService
from agent_relay.domain.rooms.models import Delivery, Message
from agent_relay.infrastructure.persistence.database import Database
from agent_relay.infrastructure.persistence.delivery_store import SQLAlchemyDeliveryStore
from agent_relay.infrastructure.persistence.migrations import run_migrations
from agent_relay.infrastructure.persistence.models import (
    DeliveryRecord,
    MemberRecord,
    RoomEventRecord,
)
from agent_relay.infrastructure.persistence.repositories.deliveries import (
    SQLAlchemyDeliveryRepository,
)
from agent_relay.infrastructure.persistence.repositories.rooms import SQLAlchemyRoomRepository

pytestmark = pytest.mark.integration


@dataclass
class DeliveryEnvironment:
    database: Database
    rooms: MessageTestStore
    store: SQLAlchemyDeliveryStore


@pytest.fixture
def environment(tmp_path: Path) -> Iterator[DeliveryEnvironment]:
    path = tmp_path / "deliveries.sqlite3"
    run_migrations(path)
    database = Database(path)
    try:
        yield DeliveryEnvironment(
            database, seed_message_store(database), SQLAlchemyDeliveryStore(database)
        )
    finally:
        database.close()


@pytest.fixture
def checked_out(environment: DeliveryEnvironment) -> Iterator[set[int]]:
    active: set[int] = set()

    def checkout(connection: object, record: ConnectionPoolEntry, proxy: object) -> None:
        active.add(id(connection))

    def checkin(connection: object, record: ConnectionPoolEntry) -> None:
        active.remove(id(connection))

    event.listen(environment.database.engine, "checkout", checkout)
    event.listen(environment.database.engine, "checkin", checkin)
    try:
        yield active
        assert not active
    finally:
        event.remove(environment.database.engine, "checkout", checkout)
        event.remove(environment.database.engine, "checkin", checkin)


def _publish(
    environment: DeliveryEnvironment,
    targets: tuple[str, ...] = ("alpha",),
    *,
    room_id: str = ROOM_ID,
    sender_id: str | None = None,
) -> Message:
    return RoomService(environment.rooms).post_message(
        room_id,
        CreateMessage(
            publication_id=uuid4().hex,
            content="Delivery facts",
            mentioned_member_ids=list(targets),
        ),
        member_id=sender_id,
    )


def _saved(environment: DeliveryEnvironment, message: Message, room_id: str = ROOM_ID) -> Delivery:
    return environment.rooms.queries.message(room_id, message.id).deliveries[0]


def _events(environment: DeliveryEnvironment) -> list[tuple[str, str, str | None]]:
    with environment.database.read() as session:
        return list(
            session.execute(
                select(
                    RoomEventRecord.room_id, RoomEventRecord.entity_id, RoomEventRecord.message_id
                )
                .where(RoomEventRecord.kind == "delivery")
                .order_by(RoomEventRecord.event_id)
            )
            .tuples()
            .all()
        )


def _queued(work: ClaimedDelivery) -> Delivery:
    delivery = work.delivery.model_copy(deep=True)
    delivery.status = "queued"
    delivery.updated_at = datetime.now(UTC)
    delivery.queued_at = delivery.updated_at
    delivery.queued_submission_id = "queue-" + delivery.client_message_id
    delivery.receipt = {
        "id": delivery.queued_submission_id,
        "clientUserMessageId": delivery.client_message_id,
        "extra": {"nested": ["preserved"]},
    }
    delivery.note = "waiting"
    return delivery


def _claim(environment: DeliveryEnvironment) -> ClaimedDelivery:
    work = environment.store.claim_delivery()
    assert work is not None
    return work


def _patch(environment: DeliveryEnvironment, delivery: Delivery, **values: object) -> None:
    with environment.database.write() as session:
        session.execute(
            update(DeliveryRecord).where(DeliveryRecord.id == delivery.id).values(**values)
        )


def test_claim_keeps_fifo_blocks_only_submitting_sessions_and_returns_durable_values(
    environment: DeliveryEnvironment, checked_out: set[int]
) -> None:
    first = _publish(environment, ("beta", "alpha"))
    second = _publish(environment, ("alpha", "gamma"))
    before = _events(environment)
    claimed = [_claim(environment) for _ in range(3)]
    assert [(work.message.id, work.delivery.target_member_id) for work in claimed] == [
        (first.id, "alpha"),
        (first.id, "beta"),
        (second.id, "gamma"),
    ]
    assert environment.store.claim_delivery() is None
    assert not checked_out
    assert [work.delivery.status for work in claimed] == ["submitting"] * 3
    assert claimed[0].message.deliveries[0] == claimed[0].delivery
    assert claimed[0].room == RoomService(environment.rooms).snapshot(ROOM_ID).room
    assert _events(environment)[len(before) :] == [
        (ROOM_ID, work.delivery.id, work.message.id) for work in claimed
    ]
    alpha = claimed[0]
    assert environment.store.finish_delivery(alpha.room_id, _queued(alpha))
    following = _claim(environment)
    assert (following.message.id, following.delivery.target_member_id) == (second.id, "alpha")
    assert claimed[1].delivery.status == "submitting"


@pytest.mark.parametrize("targets", [("alpha",), ("alpha", "beta", "gamma")])
def test_concurrent_claims_never_duplicate_work_or_share_a_submitting_session(
    environment: DeliveryEnvironment, targets: tuple[str, ...]
) -> None:
    first = _publish(environment, targets)
    _publish(environment, targets)
    barrier = Barrier(8)

    def claim(index: int) -> ClaimedDelivery | None:
        barrier.wait(timeout=5)
        return environment.store.claim_delivery()

    with ThreadPoolExecutor(max_workers=8) as workers:
        results = list(workers.map(claim, range(8)))
    claimed = [work for work in results if work is not None]
    assert len(claimed) == len(targets)
    assert {work.message.id for work in claimed} == {first.id}
    assert {work.delivery.target_member_id for work in claimed} == set(targets)
    assert len({work.delivery.id for work in claimed}) == len(targets)
    assert environment.store.claim_delivery() is None


def test_session_submission_exclusion_spans_rooms(environment: DeliveryEnvironment) -> None:
    with environment.rooms.write_rooms() as repository:
        source = repository.resources(ROOM_ID)
        other = repository.resources("other")
        original = deepcopy(other)
        other.sessions.append(
            next(item for item in source.sessions if item.id == "session-alpha").model_copy(
                deep=True
            )
        )
        other.members.append(
            next(member for member in source.members if member.id == "alpha").model_copy(
                update={"topic_ids": []}, deep=True
            )
        )
        repository.save_resources(other, original)
    first = _publish(environment)
    second = _publish(environment, room_id="other")
    claimed = _claim(environment)
    assert claimed.message.id == first.id
    assert environment.store.claim_delivery() is None
    assert environment.store.finish_delivery(ROOM_ID, _queued(claimed))
    following = _claim(environment)
    assert (following.room_id, following.message.id) == ("other", second.id)


@pytest.mark.parametrize(
    "excluded", ["deleted", "queued", "unknown", "received", "rejected", "unbound", "human"]
)
def test_claim_skips_deleted_terminal_or_unbound_targets(
    environment: DeliveryEnvironment, excluded: str
) -> None:
    first = _publish(environment)
    second = _publish(environment, ("beta",))
    if excluded == "unbound":
        with environment.database.write() as session:
            session.execute(
                update(MemberRecord)
                .where(MemberRecord.room_id == ROOM_ID, MemberRecord.id == "alpha")
                .values(session_id="session-gamma", deleted_at=datetime.now(UTC))
            )
    elif excluded == "human":
        _patch(environment, first.deliveries[0], target_member_id="user")
    elif excluded == "deleted":
        _patch(environment, first.deliveries[0], deleted_at=datetime.now(UTC))
    else:
        _patch(environment, first.deliveries[0], status=excluded)
    assert _claim(environment).message.id == second.id
    assert environment.store.claim_delivery() is None


def test_historical_deleted_member_keeps_its_saved_session_binding(
    environment: DeliveryEnvironment,
) -> None:
    message = _publish(environment)
    with environment.database.write() as session:
        session.execute(
            update(MemberRecord)
            .where(MemberRecord.room_id == ROOM_ID, MemberRecord.id == "alpha")
            .values(deleted_at=datetime.now(UTC))
        )
    assert _claim(environment).message.id == message.id


@pytest.mark.parametrize(
    "mismatch", ["room", "delivery", "client", "deleted", "queued", "received"]
)
def test_late_or_mismatched_finish_cannot_overwrite_saved_facts(
    environment: DeliveryEnvironment, mismatch: str
) -> None:
    message = _publish(environment)
    work = _claim(environment)
    queued = _queued(work)
    room_id = ROOM_ID
    if mismatch == "room":
        room_id = "other"
    elif mismatch == "delivery":
        queued.id = "missing"
    elif mismatch == "client":
        queued.client_message_id = "wrong"
        assert queued.receipt is not None
        queued.receipt["clientUserMessageId"] = "wrong"
    elif mismatch == "deleted":
        _patch(environment, work.delivery, deleted_at=datetime.now(UTC))
    else:
        _patch(environment, work.delivery, status=mismatch)
    before, events = _saved(environment, message), _events(environment)
    assert not environment.store.finish_delivery(room_id, queued)
    assert _saved(environment, message) == before
    assert _events(environment) == events


def test_finish_preserves_saved_identity_and_round_trips_receipt_extras(
    environment: DeliveryEnvironment,
) -> None:
    message = _publish(environment)
    work = _claim(environment)
    queued = _queued(work)
    queued.target_member_id = "gamma"
    queued.target_session_id = "wrong"
    assert environment.store.finish_delivery(ROOM_ID, queued)
    saved = _saved(environment, message)
    assert (saved.target_member_id, saved.target_session_id) == ("alpha", "session-alpha")
    assert saved.receipt == queued.receipt and saved.queued_at == queued.queued_at
    assert saved.updated_at == queued.updated_at
    events = _events(environment)
    assert not environment.store.finish_delivery(ROOM_ID, queued)
    assert _events(environment) == events
    assert saved.receipt is not None
    saved.receipt["extra"] = "changed locally"
    assert _saved(environment, message).receipt == queued.receipt


@pytest.mark.parametrize("field", ["id", "clientUserMessageId"])
def test_invalid_queue_receipt_rolls_back_without_an_event(
    environment: DeliveryEnvironment, field: str, checked_out: set[int]
) -> None:
    message = _publish(environment)
    work = _claim(environment)
    queued = _queued(work)
    assert queued.receipt is not None
    queued.receipt[field] = "wrong"
    events = _events(environment)
    with pytest.raises(ValueError, match="receipt"):
        environment.store.finish_delivery(ROOM_ID, queued)
    assert not checked_out
    assert _saved(environment, message) == work.delivery
    assert _events(environment) == events


@pytest.mark.parametrize(
    "mismatch", ["session", "head", "client", "missing-client", "deleted", "unknown", "received"]
)
def test_activation_requires_the_exact_unattempted_saved_queue_head(
    environment: DeliveryEnvironment, mismatch: str
) -> None:
    message = _publish(environment)
    work = _claim(environment)
    queued = _queued(work)
    assert environment.store.finish_delivery(ROOM_ID, queued)
    head = QueueHead(queued.queued_submission_id or "", queued.client_message_id)
    session_id = queued.target_session_id
    if mismatch == "session":
        session_id = "session-beta"
    elif mismatch == "head":
        head = QueueHead("wrong", head.client_message_id)
    elif mismatch == "client":
        head = QueueHead(head.id, "wrong")
    elif mismatch == "missing-client":
        head = QueueHead(head.id, None)
    elif mismatch == "deleted":
        _patch(environment, queued, deleted_at=datetime.now(UTC))
    else:
        _patch(environment, queued, status=mismatch)
    before, events = _saved(environment, message), _events(environment)
    assert not environment.store.claim_activation(session_id, head)
    assert _saved(environment, message) == before
    assert _events(environment) == events


def test_concurrent_activation_is_attempted_once_and_preserves_other_fields(
    environment: DeliveryEnvironment,
) -> None:
    message = _publish(environment)
    work = _claim(environment)
    queued = _queued(work)
    assert environment.store.finish_delivery(ROOM_ID, queued)
    before = _events(environment)
    head = QueueHead(queued.queued_submission_id or "", queued.client_message_id)
    barrier = Barrier(8)

    def activate(index: int) -> bool:
        barrier.wait(timeout=5)
        return environment.store.claim_activation(queued.target_session_id, head)

    with ThreadPoolExecutor(max_workers=8) as workers:
        assert list(workers.map(activate, range(8))).count(True) == 1
    saved = _saved(environment, message)
    assert saved.activation_attempted_at is not None
    assert saved.model_copy(update={"activation_attempted_at": None}) == queued
    assert _events(environment)[len(before) :] == [(ROOM_ID, queued.id, message.id)]


@pytest.mark.parametrize(
    "status", ["queued", "unknown", "pending", "submitting", "received", "rejected", "deleted"]
)
def test_confirm_input_only_accepts_original_pending_receipts_and_is_idempotent(
    environment: DeliveryEnvironment, status: str
) -> None:
    message = _publish(environment)
    work = _claim(environment)
    queued = _queued(work)
    assert environment.store.finish_delivery(ROOM_ID, queued)
    _patch(
        environment,
        queued,
        status="unknown" if status == "deleted" else status,
        deleted_at=datetime.now(UTC) if status == "deleted" else None,
        error="old error",
    )
    received = ReceivedInput(queued.client_message_id, "original-item", "original-turn")
    before, events = _saved(environment, message), _events(environment)
    environment.store.confirm_input("session-beta", received)
    environment.store.confirm_input(
        queued.target_session_id, ReceivedInput("wrong", "item", "turn")
    )
    assert _saved(environment, message) == before and _events(environment) == events
    environment.store.confirm_input(queued.target_session_id, received)
    saved = _saved(environment, message)
    if status in {"queued", "unknown"}:
        assert saved.status == "received"
        assert saved.received_at == saved.updated_at and saved.received_at is not None
        assert (saved.received_item_id, saved.received_turn_id) == (
            "original-item",
            "original-turn",
        )
        assert saved.note is None and saved.error is None
        assert saved.receipt == queued.receipt and saved.queued_at == queued.queued_at
        assert _events(environment)[len(events) :] == [(ROOM_ID, queued.id, message.id)]
    else:
        assert saved == before and _events(environment) == events
    events = _events(environment)
    environment.store.confirm_input(
        queued.target_session_id, ReceivedInput(queued.client_message_id, "late", "late")
    )
    assert _saved(environment, message) == saved and _events(environment) == events


def test_interrupt_only_changes_active_submissions_without_requeuing_unknowns(
    environment: DeliveryEnvironment,
) -> None:
    messages = [_publish(environment, (target,)) for target in ("alpha", "beta", "gamma")]
    claimed = [_claim(environment) for _ in range(3)]
    assert environment.store.finish_delivery(ROOM_ID, _queued(claimed[1]))
    _patch(environment, claimed[2].delivery, deleted_at=datetime.now(UTC))
    before = [_saved(environment, message) for message in messages]
    events = _events(environment)
    environment.store.interrupt_submissions()
    after = [_saved(environment, message) for message in messages]
    assert after[0].status == "unknown" and after[0].error == "提交中断，入队结果未知；不会自动重发"
    assert after[0].updated_at >= before[0].updated_at
    assert after[1:] == before[1:]
    assert _events(environment)[len(events) :] == [(ROOM_ID, after[0].id, messages[0].id)]
    assert environment.store.claim_delivery() is None
    assert environment.store.unconfirmed_inputs() == {
        "session-alpha": {after[0].client_message_id},
        "session-beta": {after[1].client_message_id},
    }
    events = _events(environment)
    environment.store.interrupt_submissions()
    assert _events(environment) == events


@pytest.mark.parametrize("status", ["queued", "unknown", "received", "deleted"])
def test_note_only_updates_the_saved_active_queued_delivery(
    environment: DeliveryEnvironment, status: str
) -> None:
    message = _publish(environment)
    queued = _queued(_claim(environment))
    assert environment.store.finish_delivery(ROOM_ID, queued)
    _patch(
        environment,
        queued,
        status="queued" if status == "deleted" else status,
        deleted_at=datetime.now(UTC) if status == "deleted" else None,
    )
    before, events = _saved(environment, message), _events(environment)
    environment.store.delivery_note("wrong", queued.client_message_id, "wrong")
    environment.store.delivery_note(queued.target_session_id, "wrong", "wrong")
    assert _saved(environment, message) == before and _events(environment) == events
    environment.store.delivery_note(
        queued.target_session_id, queued.client_message_id, "latest note"
    )
    if status == "queued":
        assert _saved(environment, message) == before.model_copy(update={"note": "latest note"})
        assert _events(environment)[len(events) :] == [(ROOM_ID, queued.id, message.id)]
    else:
        assert _saved(environment, message) == before and _events(environment) == events


def test_unconfirmed_input_groups_follow_insertion_order_and_exclude_removed_history(
    environment: DeliveryEnvironment,
) -> None:
    messages = [
        _publish(environment, (target,)) for target in ("beta", "alpha", "beta", "gamma", "alpha")
    ]
    statuses = ["unknown", "queued", "queued", "received", "unknown"]
    for message, status in zip(messages, statuses, strict=True):
        _patch(environment, message.deliveries[0], status=status)
    _patch(environment, messages[-1].deliveries[0], deleted_at=datetime.now(UTC))
    pending = environment.store.unconfirmed_inputs()
    assert list(pending) == ["session-beta", "session-alpha"]
    assert pending == {
        "session-beta": {
            messages[0].deliveries[0].client_message_id,
            messages[2].deliveries[0].client_message_id,
        },
        "session-alpha": {messages[1].deliveries[0].client_message_id},
    }


@pytest.mark.parametrize("order", ["clear-first", "finish-first", "race"])
def test_queue_clear_and_late_result_never_resurrect_a_delivery(
    environment: DeliveryEnvironment, order: str
) -> None:
    message = _publish(environment)
    work = _claim(environment)
    queued = _queued(work)
    events = _events(environment)

    def clear() -> int:
        return RoomService(environment.rooms).clear_queue(ROOM_ID).removed_messages

    if order == "clear-first":
        assert clear() == 1
        finished = environment.store.finish_delivery(ROOM_ID, queued)
    elif order == "finish-first":
        finished = environment.store.finish_delivery(ROOM_ID, queued)
        assert clear() == 1
    else:
        barrier = Barrier(2)

        def racing_clear() -> int:
            barrier.wait(timeout=5)
            return clear()

        def racing_finish() -> bool:
            barrier.wait(timeout=5)
            return environment.store.finish_delivery(ROOM_ID, queued)

        with ThreadPoolExecutor(max_workers=2) as workers:
            clearing = workers.submit(racing_clear)
            finishing = workers.submit(racing_finish)
            assert clearing.result(timeout=10) == 1
            finished = finishing.result(timeout=10)
    saved = _saved(environment, message)
    assert saved.deleted_at is not None
    assert saved.status == ("queued" if finished else "submitting")
    assert saved.receipt == (queued.receipt if finished else None)
    assert len(_events(environment)) == len(events) + 1 + int(finished)
    events = _events(environment)
    assert environment.store.claim_delivery() is None
    assert environment.store.unconfirmed_inputs() == {}
    assert not environment.store.claim_activation(
        queued.target_session_id,
        QueueHead(queued.queued_submission_id or "", queued.client_message_id),
    )
    environment.store.confirm_input(
        queued.target_session_id, ReceivedInput(queued.client_message_id, "late", "late")
    )
    environment.store.delivery_note(queued.target_session_id, queued.client_message_id, "late")
    environment.store.interrupt_submissions()
    assert _saved(environment, message) == saved and _events(environment) == events


@pytest.mark.parametrize(
    "operation", ["claim", "finish", "activation", "note", "confirm", "interrupt"]
)
def test_event_failure_rolls_back_each_atomic_action_and_releases_its_session(
    environment: DeliveryEnvironment, operation: str, checked_out: set[int]
) -> None:
    message = _publish(environment)
    work = _claim(environment) if operation != "claim" else None
    queued = _queued(work) if work is not None else None
    if operation in {"activation", "note", "confirm"}:
        assert queued is not None
        assert environment.store.finish_delivery(ROOM_ID, queued)
    before, events = _saved(environment, message), _events(environment)

    def fail_event(session: Session, context: object, instances: object) -> None:
        if any(isinstance(record, RoomEventRecord) for record in session.new):
            raise RuntimeError("event insertion failed")

    event.listen(Session, "before_flush", fail_event)
    try:
        with pytest.raises(RuntimeError, match="event insertion"):
            if operation == "claim":
                environment.store.claim_delivery()
            elif operation == "finish":
                assert queued is not None
                environment.store.finish_delivery(ROOM_ID, queued)
            elif operation == "activation":
                assert queued is not None
                environment.store.claim_activation(
                    queued.target_session_id,
                    QueueHead(queued.queued_submission_id or "", queued.client_message_id),
                )
            elif operation == "note":
                environment.store.delivery_note(
                    before.target_session_id, before.client_message_id, "new"
                )
            elif operation == "confirm":
                environment.store.confirm_input(
                    before.target_session_id,
                    ReceivedInput(before.client_message_id, "item", "turn"),
                )
            else:
                environment.store.interrupt_submissions()
    finally:
        event.remove(Session, "before_flush", fail_event)
    assert not checked_out
    assert _saved(environment, message) == before and _events(environment) == events


def test_borrowed_repository_shares_resource_rollback_and_updates_cached_records(
    environment: DeliveryEnvironment,
) -> None:
    message = _publish(environment)
    events = _events(environment)
    with (
        pytest.raises(RuntimeError, match="abort owner"),
        environment.database.write() as session,
    ):
        resources = SQLAlchemyRoomRepository(session)
        state = resources.resources(ROOM_ID)
        original = deepcopy(state)
        state.room.name = "uncommitted"
        resources.save_resources(state, original)
        repository: DeliveryRepository = SQLAlchemyDeliveryRepository(session)
        cached = session.get(DeliveryRecord, (ROOM_ID, message.deliveries[0].id))
        assert cached is not None
        work = repository.claim_delivery()
        assert work is not None and cached.status == "submitting"
        assert repository.finish_delivery(ROOM_ID, _queued(work))
        assert cached.status == "queued" and cached.receipt_metadata is not None
        assert repository.claim_activation(
            cached.target_session_id,
            QueueHead(cached.queued_submission_id or "", cached.client_message_id),
        )
        assert cached.activation_attempted_at is not None
        repository.confirm_input(
            cached.target_session_id, ReceivedInput(cached.client_message_id, "item", "turn")
        )
        assert cached.status == "received" and cached.received_item_id == "item"
        assert environment.rooms.queries.metadata(ROOM_ID).room.name == "Messages"
        raise RuntimeError("abort owner")
    assert _saved(environment, message).status == "pending"
    assert environment.rooms.queries.metadata(ROOM_ID).room.name == "Messages"
    assert _events(environment) == events


def test_commit_failure_does_not_return_success_or_leak_a_session(
    environment: DeliveryEnvironment, checked_out: set[int]
) -> None:
    message = _publish(environment)
    work = _claim(environment)
    events = _events(environment)

    def fail_commit(connection: Connection) -> None:
        raise RuntimeError("commit failed")

    event.listen(environment.database.engine, "commit", fail_commit)
    try:
        with pytest.raises(RuntimeError, match="commit failed"):
            environment.store.finish_delivery(ROOM_ID, _queued(work))
    finally:
        event.remove(environment.database.engine, "commit", fail_commit)
    assert not checked_out
    assert _saved(environment, message) == work.delivery and _events(environment) == events


def test_claim_racing_clear_leaves_no_dispatchable_or_resurrected_work(
    environment: DeliveryEnvironment,
) -> None:
    message = _publish(environment)
    events = _events(environment)
    barrier = Barrier(2)

    def claim() -> ClaimedDelivery | None:
        barrier.wait(timeout=5)
        return environment.store.claim_delivery()

    def clear() -> int:
        barrier.wait(timeout=5)
        return RoomService(environment.rooms).clear_queue(ROOM_ID).removed_messages

    with ThreadPoolExecutor(max_workers=2) as workers:
        claiming = workers.submit(claim)
        clearing = workers.submit(clear)
        claimed = claiming.result(timeout=10)
        assert clearing.result(timeout=10) == 1
    saved = _saved(environment, message)
    assert saved.deleted_at is not None
    assert saved.status == ("pending" if claimed is None else "submitting")
    assert len(_events(environment)) == len(events) + 1 + int(claimed is not None)
    if claimed is not None:
        assert not environment.store.finish_delivery(ROOM_ID, _queued(claimed))
    assert environment.store.claim_delivery() is None
    assert _saved(environment, message) == saved


def test_clear_during_enqueue_releases_database_and_discards_the_late_receipt(
    environment: DeliveryEnvironment, checked_out: set[int]
) -> None:
    message = _publish(environment)
    work = _claim(environment)
    barrier = Barrier(2)

    class PausedDriver(FakeQueueDriver):
        def enqueue(self, thread_id: str, client_message_id: str, text: str) -> QueueReceipt:
            assert not checked_out
            barrier.wait(timeout=5)
            barrier.wait(timeout=5)
            return super().enqueue(thread_id, client_message_id, text)

    driver = PausedDriver()
    service = DeliveryService(
        environment.store, driver, logging.getLogger("tests.sqlalchemy.inflight")
    )
    with ThreadPoolExecutor(max_workers=1) as workers:
        submitting = workers.submit(service.submit, work)
        barrier.wait(timeout=5)
        cleared = RoomService(environment.rooms).clear_queue_with_codex(ROOM_ID, driver)
        assert cleared.removed_messages == 1
        assert cleared.codex_queue is not None and cleared.codex_queue.without_receipt == 1
        events = _events(environment)
        barrier.wait(timeout=5)
        submitting.result(timeout=10)
    saved = _saved(environment, message)
    assert saved.status == "submitting" and saved.deleted_at is not None
    assert saved.receipt is None and saved.queued_submission_id is None
    assert len(driver.calls) == 1 and driver.activations == [] and driver.deletions == []
    assert _events(environment) == events


def test_original_session_consumption_keeps_receipt_and_survives_reopening(
    environment: DeliveryEnvironment,
) -> None:
    message = _publish(environment)
    work = _claim(environment)

    class ConsumingDriver(FakeQueueDriver):
        def enqueue(self, thread_id: str, client_message_id: str, text: str) -> QueueReceipt:
            receipt = super().enqueue(thread_id, client_message_id, text)
            self.heads[thread_id] = QueueHead(receipt.id, client_message_id)
            return receipt

    driver = ConsumingDriver()
    service = DeliveryService(
        environment.store, driver, logging.getLogger("tests.sqlalchemy.consume")
    )
    service.submit(work)
    queued = _saved(environment, message)
    service.observe(queued.target_session_id, {queued.client_message_id})
    received = _saved(environment, message)
    assert received.status == "received"
    assert received.receipt == queued.receipt and received.queued_at == queued.queued_at
    assert received.activation_attempted_at == queued.activation_attempted_at
    assert received.received_at is not None
    assert received.received_item_id == "item-" + received.client_message_id
    assert received.received_turn_id == "turn-" + received.client_message_id
    reopened = Database(environment.database.path)
    try:
        assert MessageTestStore(reopened).queries.message(ROOM_ID, message.id).deliveries == [
            received
        ]
        store = SQLAlchemyDeliveryStore(reopened)
        store.interrupt_submissions()
        assert store.unconfirmed_inputs() == {} and store.claim_delivery() is None
    finally:
        reopened.close()
    assert len(driver.calls) == len(driver.activations) == 1


def test_real_services_release_transactions_before_all_queue_rpcs_and_persist_receipts(
    environment: DeliveryEnvironment, checked_out: set[int]
) -> None:
    room_service = RoomService(environment.rooms)
    message = _publish(environment, ("beta",), sender_id="alpha")
    room_service.update_member(ROOM_ID, "alpha", UpdateMember(name="Renamed", topic_ids=[]))
    work = _claim(environment)
    assert work.message.sender_name == "Renamed"
    boundaries: list[str] = []

    def boundary(name: str) -> None:
        assert not checked_out
        with environment.database.write() as session:
            assert session.scalar(select(DeliveryRecord.id)) is not None
        boundaries.append(name)

    class BoundaryDriver(FakeQueueDriver):
        def enqueue(self, thread_id: str, client_message_id: str, text: str) -> QueueReceipt:
            boundary("enqueue")
            assert _saved(environment, message).status == "submitting"
            receipt = super().enqueue(thread_id, client_message_id, text)
            self.heads[thread_id] = QueueHead(receipt.id, client_message_id)
            return receipt

        def activation_candidate(self, thread_id: str) -> QueueHead | None:
            boundary("candidate")
            return super().activation_candidate(thread_id)

        def activate(self, thread_id: str, queued_submission_id: str) -> str:
            boundary("activate")
            assert _saved(environment, message).activation_attempted_at is not None
            return super().activate(thread_id, queued_submission_id)

        def read_input_page(self, thread_id: str, cursor: str | None = None) -> InputPage:
            boundary("read")
            return super().read_input_page(thread_id, cursor)

        def delete(self, thread_id: str, queued_submission_id: str) -> bool:
            boundary("delete")
            assert _saved(environment, message).deleted_at is not None
            self.deletions.append((thread_id, queued_submission_id))
            return True

    driver = BoundaryDriver()
    store: DeliveryStore = environment.store
    service = DeliveryService(store, driver, logging.getLogger("tests.sqlalchemy.delivery"))
    service.submit(work)
    queued = _saved(environment, message)
    assert queued.status == "queued" and queued.activation_attempted_at is not None
    created_at = work.message.model_dump(mode="json", by_alias=True)["createdAt"]
    assert driver.calls == [
        (
            "session-beta",
            queued.client_message_id,
            f"roomId: {ROOM_ID}\nmessageId: {message.id}\nseq: {message.seq}\n"
            f"createdAt: {created_at}\nsender: Renamed（alpha）\n\nDelivery facts",
        )
    ]
    cleared = room_service.clear_queue_with_codex(ROOM_ID, driver)
    assert cleared.removed_messages == 1
    assert cleared.codex_queue is not None and cleared.codex_queue.deleted == 1
    service.observe(queued.target_session_id, {queued.client_message_id})
    saved = _saved(environment, message)
    assert saved.status == "queued" and saved.deleted_at is not None
    assert boundaries == ["enqueue", "candidate", "activate", "delete", "read"]
    reopened = Database(environment.database.path)
    try:
        assert MessageTestStore(reopened).queries.message(ROOM_ID, message.id).deliveries == [saved]
        assert SQLAlchemyDeliveryStore(reopened).unconfirmed_inputs() == {}
    finally:
        reopened.close()


@pytest.mark.parametrize(
    "failure", ["rejected", "unknown", "activation-rejected", "activation-unknown"]
)
def test_submission_failures_keep_receipts_and_never_automatically_resubmit(
    environment: DeliveryEnvironment, failure: str, checked_out: set[int]
) -> None:
    message = _publish(environment)
    work = _claim(environment)

    class FailingDriver(FakeQueueDriver):
        def enqueue(self, thread_id: str, client_message_id: str, text: str) -> QueueReceipt:
            assert not checked_out
            receipt = super().enqueue(thread_id, client_message_id, text)
            if failure == "rejected":
                raise QueueRejected("rejected")
            if failure == "unknown":
                raise TimeoutError("unknown")
            self.heads[thread_id] = QueueHead(receipt.id, client_message_id)
            return receipt

        def activate(self, thread_id: str, queued_submission_id: str) -> str:
            assert not checked_out
            self.activations.append((thread_id, queued_submission_id))
            if failure == "activation-rejected":
                raise ActivationRejected("already consumed")
            raise TimeoutError("activation unknown")

    driver = FailingDriver()
    service = DeliveryService(
        environment.store, driver, logging.getLogger("tests.sqlalchemy.failures")
    )
    service.submit(work)
    saved = _saved(environment, message)
    assert saved.status == (
        "rejected" if failure == "rejected" else "unknown" if failure == "unknown" else "queued"
    )
    assert (saved.receipt is not None) == failure.startswith("activation")
    assert (saved.activation_attempted_at is not None) == failure.startswith("activation")
    assert environment.store.claim_delivery() is None
    assert len(driver.calls) == 1
    if failure.startswith("activation"):
        service.activate_after_submission(saved.target_session_id, saved.client_message_id)
        assert len(driver.activations) == 1
        assert _saved(environment, message).receipt == saved.receipt


def test_unknown_submission_can_be_confirmed_from_an_older_original_history_page(
    environment: DeliveryEnvironment, checked_out: set[int]
) -> None:
    message = _publish(environment)
    work = _claim(environment)
    _patch(environment, work.delivery, status="unknown", error="unknown result")
    cursors: list[str | None] = []

    class HistoryDriver(FakeQueueDriver):
        def read_input_page(self, thread_id: str, cursor: str | None = None) -> InputPage:
            assert not checked_out and thread_id == work.delivery.target_session_id
            cursors.append(cursor)
            if cursor is None:
                return InputPage((ReceivedInput("unrelated", "other-item", "other-turn"),), "older")
            assert cursor == "older"
            return InputPage(
                (ReceivedInput(work.delivery.client_message_id, "original-item", "original-turn"),),
                None,
            )

    driver = HistoryDriver()
    service = DeliveryService(
        environment.store, driver, logging.getLogger("tests.sqlalchemy.history")
    )
    pending = environment.store.unconfirmed_inputs()
    service.observe(work.delivery.target_session_id, pending[work.delivery.target_session_id])
    assert _saved(environment, message).status == "unknown"
    service.observe(work.delivery.target_session_id, pending[work.delivery.target_session_id])
    saved = _saved(environment, message)
    assert saved.status == "received" and saved.error is None
    assert (saved.received_item_id, saved.received_turn_id) == ("original-item", "original-turn")
    assert saved.queued_at is None and saved.receipt is None
    assert cursors == [None, None, "older"]
    assert driver.calls == [] and driver.activations == []
    assert environment.store.unconfirmed_inputs() == {}
