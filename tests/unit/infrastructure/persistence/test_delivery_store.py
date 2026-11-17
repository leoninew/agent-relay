import logging
from collections.abc import Iterator
from contextvars import Context
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

import pytest
from sqlalchemy import select

from conflua.application.delivery.ports import DeliveryDriver, SubmissionDeferred
from conflua.application.delivery.service import DeliveryService
from conflua.application.dto.delivery import (
    InputPage,
    QueueHead,
    QueuePage,
    QueueReceipt,
    QueueRequest,
    ReceivedInput,
    SteerReceipt,
)
from conflua.application.dto.messages import CreateMessage
from conflua.application.messages.service import MessageService
from conflua.domain.rooms.delivery import queue_accepted
from conflua.infrastructure.persistence.channel_guard import room_operation
from conflua.infrastructure.persistence.delivery_store import SQLAlchemyDeliveryStore
from conflua.infrastructure.persistence.dependencies import create_database
from conflua.infrastructure.persistence.models import (
    ChannelRecord,
    DeliveryRecord,
    MemberRecord,
    MessageRecipientRecord,
    MessageRecord,
    RoomRecord,
    SessionRecord,
)
from conflua.infrastructure.persistence.repositories.deliveries import SQLAlchemyDeliveryRepository
from conflua.infrastructure.persistence.room_store import SQLAlchemyRoomStore


@pytest.fixture
def store(tmp_path: Path) -> Iterator[SQLAlchemyDeliveryStore]:
    database = create_database(tmp_path / "test.sqlite3")
    now = datetime.now(UTC)
    with database.write() as session:
        for room_id in ("first", "second"):
            session.add(RoomRecord(id=room_id, name=room_id, project_path=room_id, description=""))
        session.flush()
        for room_id in ("first", "second"):
            session.add(
                ChannelRecord(
                    room_id=room_id,
                    id="channel-default",
                    name="Default",
                    description="",
                    is_default=True,
                    workspace_kind="existing",
                )
            )
            for number in (1, 2):
                session.add(
                    SessionRecord(
                        room_id=room_id,
                        id=f"{room_id}-session-{number}",
                        name=str(number),
                        provider="codex",
                        presence="available",
                    )
                )
        session.flush()
        for room_id in ("first", "second"):
            for number in (1, 2):
                session.add(
                    MemberRecord(
                        room_id=room_id,
                        channel_id="channel-default",
                        id=f"member-{number}",
                        name=str(number),
                        session_id=f"{room_id}-session-{number}",
                        kind="agent",
                        initials="A",
                        presence="available",
                        activity="",
                        activity_source="",
                    )
                )
        session.flush()
        for room_id in ("first", "second"):
            session.add(
                MessageRecord(
                    room_id=room_id,
                    channel_id="channel-default",
                    id="message",
                    seq=1,
                    publisher_id="member-1",
                    content="test",
                    created_at=now,
                )
            )
        session.flush()
        for room_id in ("first", "second"):
            for number in (1, 2):
                session.add(
                    DeliveryRecord(
                        room_id=room_id,
                        channel_id="channel-default",
                        id=f"delivery-{number}",
                        message_id="message",
                        target_member_id=f"member-{number}",
                        target_session_id=f"{room_id}-session-{number}",
                        client_message_id=f"{room_id}-client-{number}",
                        status="pending",
                        updated_at=now,
                    )
                )
    yield SQLAlchemyDeliveryStore(database)
    database.close()


def add_following(store: SQLAlchemyDeliveryStore) -> None:
    with store.database.write() as session:
        session.add(
            MessageRecord(
                room_id="first",
                channel_id="channel-default",
                id="following",
                seq=2,
                publisher_id="member-1",
                content="following",
                created_at=datetime.now(UTC),
            )
        )
        session.flush()
        session.add(
            DeliveryRecord(
                room_id="first",
                channel_id="channel-default",
                id="following",
                message_id="following",
                target_member_id="member-1",
                target_session_id="first-session-1",
                client_message_id="following-client",
                status="pending",
                updated_at=datetime.now(UTC),
            )
        )


@pytest.mark.parametrize("commit", [False, True])
def test_request_message_and_routed_delivery_become_visible_only_after_commit(
    store: SQLAlchemyDeliveryStore, commit: bool
) -> None:
    with store.database.write() as session:
        for record in session.scalars(select(DeliveryRecord)):
            record.status = "received"
    transaction = store.database.request_transaction()
    messages = MessageService(
        SQLAlchemyRoomStore(store.database, transaction, channel_id="channel-default")
    )
    request = CreateMessage(
        publication_id="transaction-publication",
        content="transaction message",
        mentioned_member_ids=["member-2"],
    )
    try:
        message = messages.post_message("first", request, member_id="member-1")
        assert messages.post_message("first", request, member_id="member-1").id == message.id
        with store.database.read() as reader:
            assert (
                reader.scalar(select(MessageRecord).where(MessageRecord.id == message.id)) is None
            )
            assert (
                reader.scalar(
                    select(MessageRecipientRecord).where(
                        MessageRecipientRecord.message_id == message.id
                    )
                )
                is None
            )
            assert (
                reader.scalar(select(DeliveryRecord).where(DeliveryRecord.message_id == message.id))
                is None
            )
        transaction.finish(commit=commit)
    finally:
        transaction.finish(commit=False)
    with store.database.read() as reader:
        saved = reader.scalar(select(MessageRecord).where(MessageRecord.id == message.id))
        recipients = list(
            reader.scalars(
                select(MessageRecipientRecord.member_id).where(
                    MessageRecipientRecord.message_id == message.id
                )
            )
        )
        deliveries = list(
            reader.scalars(select(DeliveryRecord).where(DeliveryRecord.message_id == message.id))
        )
        assert (saved is not None) == commit
        assert recipients == (["member-2"] if commit else [])
        assert len(deliveries) == int(commit)
        if saved is not None:
            assert saved.publication_id == request.publication_id
    claimed = store.claim_delivery()
    if commit:
        assert claimed is not None and claimed.message.id == message.id
        assert claimed.delivery.target_member_id == "member-2"
    else:
        assert claimed is None


def test_multi_target_delivery_recovers_unsent_head_without_duplicate_inputs(
    store: SQLAlchemyDeliveryStore,
) -> None:
    add_following(store)
    driver = Mock(spec=DeliveryDriver)
    driver.activation_candidate.return_value = None
    driver.read_queue_page.return_value = QueuePage((), None)
    attempts: list[str] = []
    written: list[tuple[str, str]] = []

    def submit(session_id: str, client_id: str, request: QueueRequest) -> QueueReceipt:
        attempts.append(client_id)
        if client_id == "first-client-1" and attempts.count(client_id) == 1:
            raise SubmissionDeferred("temporary preflight disconnect")
        written.append((session_id, client_id))
        return QueueReceipt(
            f"queued-{client_id}",
            {"id": f"queued-{client_id}", "clientUserMessageId": client_id},
        )

    driver.submit.side_effect = submit
    service = DeliveryService(store, driver, logging.getLogger("tests.delivery"))
    first = store.claim_delivery()
    assert first is not None and first.delivery.client_message_id == "first-client-1"
    assert service.submit(first) is None
    assert written == []
    reopened = SQLAlchemyDeliveryStore(store.database)
    service = DeliveryService(reopened, driver, logging.getLogger("tests.delivery"))
    excluded = frozenset({"first-session-1"})
    while (other := reopened.claim_delivery(excluded)) is not None:
        assert service.submit(other) is None
    assert ("first-session-2", "first-client-2") in written
    assert len(written) == 3
    with reopened.database.write() as session:
        repository = SQLAlchemyDeliveryRepository(session)
        original = session.get(DeliveryRecord, ("first", "delivery-1", "channel-default"))
        following = session.get(DeliveryRecord, ("first", "following", "channel-default"))
        assert original is not None and original.next_attempt_at is not None
        assert following is not None and following.status == "pending"
        due = original.next_attempt_at
        assert repository.claim_delivery(frozenset(), due - timedelta(seconds=1)) is None
        retry = repository.claim_delivery(frozenset(), due)
    assert retry is not None and retry.delivery.id == first.delivery.id
    assert retry.delivery.client_message_id == first.delivery.client_message_id
    assert service.submit(retry) is None
    next_work = reopened.claim_delivery()
    assert next_work is not None and next_work.delivery.id == "following"
    assert service.submit(next_work) is None
    assert [client_id for session_id, client_id in written if session_id == "first-session-1"] == [
        "first-client-1",
        "following-client",
    ]
    assert len(written) == len(set(written)) == 5
    assert attempts.count("first-client-1") == 2
    with reopened.database.read() as session:
        records = list(session.scalars(select(DeliveryRecord)))
        assert all(record.status == "queued" and record.received_at is None for record in records)
    for session_id, client_ids in reopened.unconfirmed_inputs().items():
        driver.read_input_page.return_value = InputPage(
            tuple(
                ReceivedInput(client_id, f"item-{client_id}", "turn") for client_id in client_ids
            ),
            None,
        )
        service.observe(session_id, client_ids)
    with reopened.database.read() as session:
        records = list(session.scalars(select(DeliveryRecord)))
        assert all(record.status == "received" and record.received_at for record in records)
    assert len(written) == 5
    driver.activate.assert_not_called()


@pytest.mark.parametrize("method", ["queue", "steer"])
def test_each_session_receives_only_its_own_recipient_header(
    store: SQLAlchemyDeliveryStore, method: str
) -> None:
    with store.database.write() as session:
        for member in session.scalars(select(MemberRecord)):
            member.name = f"{member.room_id}-{member.id}"
    driver = Mock(spec=DeliveryDriver)

    def submit(
        session_id: str, client_id: str, request: QueueRequest
    ) -> QueueReceipt | SteerReceipt:
        if method == "steer":
            return SteerReceipt("turn")
        return QueueReceipt("queued", {"id": "queued", "clientUserMessageId": client_id})

    driver.submit.side_effect = submit
    driver.activation_candidate.return_value = None
    service = DeliveryService(store, driver, logging.getLogger("tests.delivery"))
    while (work := store.claim_delivery()) is not None:
        assert service.submit(work) is None
    assert driver.submit.call_count == 4
    for submission in driver.submit.call_args_list:
        session_id, _, request = submission.args
        room_id, _, number = session_id.split("-")
        member_id = f"member-{number}"
        header, content = request.text.split("\n\n", 1)
        assert [line for line in header.splitlines() if line.startswith("recipient:")] == [
            f"recipient: {room_id}-{member_id}（{member_id}）"
        ]
        assert content == "test"


def test_different_targets_in_same_room_can_be_claimed_while_first_is_submitting(
    store: SQLAlchemyDeliveryStore,
) -> None:
    add_following(store)
    first = store.claim_delivery()
    second = store.claim_delivery()
    assert first is not None and second is not None
    assert first.room_id == second.room_id == "first"
    assert first.delivery.target_session_id != second.delivery.target_session_id
    while store.claim_delivery() is not None:
        pass
    with store.database.read() as session:
        following = session.get(DeliveryRecord, ("first", "following", "channel-default"))
        assert following is not None and following.status == "pending"


def test_persistent_backoff_blocks_only_same_target_and_preserves_order(
    store: SQLAlchemyDeliveryStore,
) -> None:
    add_following(store)
    work = store.claim_delivery()
    assert work is not None
    due = datetime.now(UTC) + timedelta(seconds=10)
    assert store.defer_delivery(work, "waiting", due)
    reopened = SQLAlchemyDeliveryStore(store.database)
    other = reopened.claim_delivery()
    assert other is not None and other.delivery.target_session_id == "first-session-2"
    while reopened.claim_delivery() is not None:
        pass
    with store.database.write() as session:
        retry = SQLAlchemyDeliveryRepository(session).claim_delivery(frozenset(), due)
    assert retry is not None and retry.delivery.id == work.delivery.id
    assert retry.delivery.client_message_id == work.delivery.client_message_id
    assert retry.attempt_count == 2


@pytest.mark.parametrize("change", ["deleted", "received"])
def test_defer_does_not_revive_changed_delivery(
    store: SQLAlchemyDeliveryStore, change: str
) -> None:
    work = store.claim_delivery()
    assert work is not None
    with store.database.write() as session:
        record = session.get(DeliveryRecord, (work.room_id, work.delivery.id, work.channel_id))
        assert record is not None
        if change == "deleted":
            record.deleted_at = datetime.now(UTC)
        else:
            record.status = "received"
    assert not store.defer_delivery(work, "waiting", datetime.now(UTC))


@pytest.mark.parametrize("invalid", ["deleted-member", "rebound", "archived-channel"])
def test_invalid_earlier_target_does_not_block_valid_same_session_work(
    store: SQLAlchemyDeliveryStore, invalid: str
) -> None:
    with store.database.write() as session:
        session.add(
            SessionRecord(
                room_id="second",
                id="first-session-1",
                name="shared",
                provider="codex",
                presence="available",
            )
        )
        session.add(
            SessionRecord(
                room_id="first",
                id="replacement-session",
                name="replacement",
                provider="codex",
                presence="available",
            )
        )
        session.flush()
        session.add(
            MemberRecord(
                room_id="second",
                channel_id="channel-default",
                id="new-member",
                name="new",
                session_id="first-session-1",
                kind="agent",
                initials="A",
                presence="available",
                activity="",
                activity_source="",
            )
        )
        session.add(
            MessageRecord(
                room_id="second",
                channel_id="channel-default",
                id="new-message",
                seq=2,
                publisher_id="new-member",
                content="test",
                created_at=datetime.now(UTC),
            )
        )
        session.flush()
        session.add(
            DeliveryRecord(
                room_id="second",
                channel_id="channel-default",
                id="new-delivery",
                message_id="new-message",
                target_member_id="new-member",
                target_session_id="first-session-1",
                client_message_id="new-client",
                status="pending",
                updated_at=datetime.now(UTC),
            )
        )
        member = session.get(MemberRecord, ("first", "member-1", "channel-default"))
        channel = session.get(ChannelRecord, ("first", "channel-default"))
        assert member is not None and channel is not None
        if invalid == "deleted-member":
            member.deleted_at = datetime.now(UTC)
        elif invalid == "rebound":
            member.session_id = "replacement-session"
        else:
            channel.archived_at = datetime.now(UTC)
    with store.database.write() as session:
        claimed = SQLAlchemyDeliveryRepository(session).claim_delivery(
            frozenset({"first-session-2", "second-session-1", "second-session-2"}),
            datetime.now(UTC),
        )
    assert claimed is not None and claimed.delivery.id == "new-delivery"


def test_submission_and_activation_hold_no_room_or_database_write_lock(
    store: SQLAlchemyDeliveryStore,
) -> None:
    work = store.claim_delivery()
    assert work is not None
    driver = Mock(spec=DeliveryDriver)
    receipt = QueueReceipt(
        "queued",
        {
            "id": "queued",
            "clientUserMessageId": work.delivery.client_message_id,
        },
    )
    driver.activation_candidate.return_value = QueueHead("queued", work.delivery.client_message_id)

    def check_unlocked() -> QueueReceipt:
        with room_operation(store.database.path, work.room_id), store.database.write():
            return receipt

    def external_call(*args: object) -> QueueReceipt:
        return Context().run(check_unlocked)

    driver.submit.side_effect = external_call
    driver.activate.side_effect = external_call
    service = DeliveryService(store, driver, logging.getLogger("tests.delivery"))
    assert service.submit(work) is None
    driver.submit.assert_called_once()
    driver.activate.assert_called_once()


def test_queue_evidence_and_input_history_record_distinct_facts(
    store: SQLAlchemyDeliveryStore,
) -> None:
    work = store.claim_delivery()
    assert work is not None
    store.interrupt_submissions()
    receipt = QueueReceipt(
        "queued",
        {
            "id": "queued",
            "clientUserMessageId": work.delivery.client_message_id,
        },
    )
    store.confirm_queue(work.delivery.target_session_id, work.delivery.client_message_id, receipt)
    with store.database.read() as session:
        record = session.get(DeliveryRecord, (work.room_id, work.delivery.id, work.channel_id))
        assert record is not None and record.status == "queued" and record.received_at is None
    received = ReceivedInput(work.delivery.client_message_id, "item", "turn")
    store.confirm_input(work.delivery.target_session_id, received)
    with store.database.read() as session:
        record = session.get(DeliveryRecord, (work.room_id, work.delivery.id, work.channel_id))
        assert record is not None and record.status == "received"
        assert record.received_item_id == "item"


@pytest.mark.parametrize("legacy", [False, True])
def test_new_unknown_blocks_following_input_but_legacy_unknown_keeps_existing_behavior(
    store: SQLAlchemyDeliveryStore, legacy: bool
) -> None:
    add_following(store)
    work = store.claim_delivery()
    assert work is not None
    store.interrupt_submissions()
    if legacy:
        with store.database.write() as session:
            record = session.get(DeliveryRecord, (work.room_id, work.delivery.id, work.channel_id))
            assert record is not None
            record.attempt_count = 0
    excluded = frozenset({"first-session-2", "second-session-1", "second-session-2"})
    following = store.claim_delivery(excluded)
    if legacy:
        assert following is not None and following.delivery.id == "following"
    else:
        assert following is None
    receipt = QueueReceipt(
        "queued", {"id": "queued", "clientUserMessageId": work.delivery.client_message_id}
    )
    store.confirm_queue(work.delivery.target_session_id, work.delivery.client_message_id, receipt)
    if not legacy:
        following = store.claim_delivery(excluded)
        assert following is not None and following.delivery.id == "following"
    else:
        with store.database.read() as session:
            record = session.get(DeliveryRecord, (work.room_id, work.delivery.id, work.channel_id))
            assert record is not None and record.status == "unknown"


@pytest.mark.parametrize("source", ["saved-receipt", "reconciled-queue"])
def test_first_activation_check_survives_restart_and_never_repeats_uncertain_start(
    store: SQLAlchemyDeliveryStore, source: str
) -> None:
    work = store.claim_delivery()
    assert work is not None
    receipt = QueueReceipt(
        "queued", {"id": "queued", "clientUserMessageId": work.delivery.client_message_id}
    )
    if source == "reconciled-queue":
        store.interrupt_submissions()
        store.confirm_queue(
            work.delivery.target_session_id, work.delivery.client_message_id, receipt
        )
    else:
        queued = queue_accepted(work.delivery, receipt.id, receipt.metadata, datetime.now(UTC))
        assert store.finish_delivery(work.room_id, queued)
    first = store.claim_activation_work(frozenset())
    assert first is not None
    reopened = SQLAlchemyDeliveryStore(store.database)
    assert reopened.claim_activation_work(frozenset({first.session_id})) is None
    with reopened.database.write() as session:
        restored = SQLAlchemyDeliveryRepository(session).claim_activation_work(
            frozenset(), datetime.now(UTC) + timedelta(seconds=3)
        )
    assert restored == first
    driver = Mock(spec=DeliveryDriver)
    driver.activation_candidate.return_value = QueueHead(
        receipt.id, work.delivery.client_message_id
    )
    driver.activate.side_effect = TimeoutError("lost start response")
    service = DeliveryService(reopened, driver, logging.getLogger("tests.delivery"))
    service.check_activation(restored)
    service.check_activation(restored)
    driver.activate.assert_called_once()
    with reopened.database.write() as session:
        assert (
            SQLAlchemyDeliveryRepository(session).claim_activation_work(
                frozenset(), datetime.now(UTC) + timedelta(seconds=10)
            )
            is None
        )


@pytest.mark.parametrize("change", ["received", "deleted", "legacy"])
def test_saved_receipt_and_activation_claim_do_not_revive_changed_work(
    store: SQLAlchemyDeliveryStore, change: str
) -> None:
    work = store.claim_delivery()
    assert work is not None
    receipt = QueueReceipt(
        "queued", {"id": "queued", "clientUserMessageId": work.delivery.client_message_id}
    )
    queued = queue_accepted(work.delivery, receipt.id, receipt.metadata, datetime.now(UTC))
    assert store.finish_delivery(work.room_id, queued)
    with store.database.write() as session:
        record = session.get(DeliveryRecord, (work.room_id, work.delivery.id, work.channel_id))
        assert record is not None
        if change == "received":
            record.status = "received"
        elif change == "deleted":
            record.deleted_at = datetime.now(UTC)
        else:
            record.attempt_count = 0
    assert not store.finish_delivery(work.room_id, queued)
    assert store.claim_activation_work(frozenset()) is None


def test_slow_first_activation_checks_give_other_due_sessions_their_turn(
    store: SQLAlchemyDeliveryStore,
) -> None:
    first = store.claim_delivery()
    second = store.claim_delivery()
    assert first is not None and second is not None
    for work in (first, second):
        receipt: dict[str, object] = {
            "id": work.delivery.id,
            "clientUserMessageId": work.delivery.client_message_id,
        }
        assert store.finish_delivery(
            work.room_id,
            queue_accepted(work.delivery, work.delivery.id, receipt, datetime.now(UTC)),
        )
    now = datetime.now(UTC) + timedelta(seconds=1)
    sessions = []
    for turn in range(4):
        with store.database.write() as session:
            check = SQLAlchemyDeliveryRepository(session).claim_activation_work(
                frozenset(), now + timedelta(seconds=turn * 3)
            )
        assert check is not None
        sessions.append(check.session_id)
    assert sessions == [
        first.delivery.target_session_id,
        second.delivery.target_session_id,
        first.delivery.target_session_id,
        second.delivery.target_session_id,
    ]
