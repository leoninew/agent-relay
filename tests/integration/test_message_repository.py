from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import delete, event, select, update
from sqlalchemy.engine import Connection, ExecutionContext
from sqlalchemy.exc import IntegrityError
from sqlalchemy_message_fixtures import (
    FIRST_TOPIC,
    OBSERVED_AT,
    ROOM_ID,
    SECOND_TOPIC,
    MessageTestStore,
    seed_message_store,
)

from agent_relay.application.rooms.contracts import (
    CreateMessage,
    MessagePage,
    MessageQueuePage,
    UpdateMember,
)
from agent_relay.application.rooms.ports import MessageRepository, RoomQueries
from agent_relay.application.rooms.service import RoomService
from agent_relay.domain.rooms.errors import RoomConflictError, RoomNotFoundError
from agent_relay.domain.rooms.models import Message
from agent_relay.domain.rooms.rules import build_message
from agent_relay.infrastructure.persistence.database import Database
from agent_relay.infrastructure.persistence.message_queries import MessageQueries
from agent_relay.infrastructure.persistence.migrations import run_migrations
from agent_relay.infrastructure.persistence.models import (
    DeliveryRecord,
    MessageRecord,
    RoomEventRecord,
    SessionRecord,
)
from agent_relay.infrastructure.persistence.repositories.messages import SQLAlchemyMessageRepository
from agent_relay.infrastructure.persistence.repositories.rooms import SQLAlchemyRoomRepository
from agent_relay.infrastructure.persistence.room_queries import SQLAlchemyRoomQueries

pytestmark = pytest.mark.integration


@pytest.fixture
def database(tmp_path: Path) -> Iterator[Database]:
    path = tmp_path / "messages.sqlite3"
    run_migrations(path)
    database = Database(path)
    try:
        yield database
    finally:
        database.close()


@pytest.fixture
def store(database: Database) -> MessageTestStore:
    return seed_message_store(database)


def _publish(
    store: MessageTestStore,
    content: str = "Publication",
    *,
    publication_id: str | None = None,
    member_id: str | None = None,
) -> Message:
    return RoomService(store).post_message(
        ROOM_ID,
        CreateMessage(
            publication_id=publication_id or uuid4().hex,
            content=content,
            topic_ids=[FIRST_TOPIC, SECOND_TOPIC],
        ),
        member_id=member_id,
    )


def _history(store: MessageTestStore, total: int = 125) -> list[Message]:
    messages: list[Message] = []
    with store.write_rooms() as repository:
        state = repository.resources(ROOM_ID)
        start = repository.next_message_seq(ROOM_ID)
        for sequence in range(start, total + 1):
            sender = state.members[(sequence - 1) % 3]
            topics = (
                [FIRST_TOPIC, SECOND_TOPIC]
                if sequence % 3 == 0
                else [FIRST_TOPIC]
                if sequence % 3 == 1
                else [SECOND_TOPIC]
            )
            message = build_message(
                state,
                seq=sequence,
                content=f"history {sequence}",
                topic_ids=topics,
                mentioned_member_ids=[],
                sender_id=sender.id,
                sender_name=sender.name,
                created_at=OBSERVED_AT,
                publication_id=f"history-{sequence}",
            )
            repository.insert_message(ROOM_ID, message)
            messages.append(message)
    return messages


def test_message_round_trip_preserves_order_routing_reply_and_events(
    store: MessageTestStore,
) -> None:
    parent = _publish(store, "Parent")
    with store.database.write() as session:
        rooms = SQLAlchemyRoomRepository(session)
        repository: MessageRepository = SQLAlchemyMessageRepository(session)
        cursor = rooms.metadata(ROOM_ID).event_id
        message = build_message(
            rooms.resources(ROOM_ID),
            seq=repository.next_message_seq(ROOM_ID),
            content="Ordered relationships",
            topic_ids=[SECOND_TOPIC, FIRST_TOPIC],
            mentioned_member_ids=["gamma", "alpha", "user"],
            sender_id="beta",
            sender_name="Beta",
            created_at=OBSERVED_AT,
            publication_id="ordered",
            reply_to_message_id=parent.id,
        )
        message.recipient_ids = list(reversed(message.recipient_ids))
        message.deliveries = list(reversed(message.deliveries))
        repository.insert_message(ROOM_ID, message)
        queries: RoomQueries = SQLAlchemyRoomQueries(session)
        assert queries.message(ROOM_ID, message.id) == message
        assert repository.publication(ROOM_ID, "beta", "ordered") == message
        assert repository.publication(ROOM_ID, "alpha", "ordered") is None
        assert repository.message_exists(ROOM_ID, message.id)
        assert not repository.message_exists("other", message.id)
        assert repository.next_message_seq(ROOM_ID) == 3
        assert [(item.kind, item.entity_id) for item in queries.events(ROOM_ID, cursor).events] == [
            ("message", message.id),
            *[("delivery", delivery.id) for delivery in message.deliveries],
        ]
    assert store.queries.message(ROOM_ID, message.id) == message


@pytest.mark.parametrize("changed", ["content", "topics", "mentions", "reply"])
def test_service_idempotency_rejects_reuse_for_a_different_publication(
    store: MessageTestStore, changed: str
) -> None:
    message = _publish(store, publication_id="same")
    request = CreateMessage(
        publication_id="same", content=message.content, topic_ids=message.topic_ids
    )
    if changed == "content":
        request.content = "Different"
    elif changed == "topics":
        request.topic_ids = [FIRST_TOPIC]
    elif changed == "mentions":
        request.mentioned_member_ids = ["alpha"]
    else:
        request.reply_to_message_id = "missing"
    before = store.queries.metadata(ROOM_ID)
    with pytest.raises(RoomConflictError, match="发布编号已用于另一条消息"):
        RoomService(store).post_message(ROOM_ID, request)
    assert store.queries.metadata(ROOM_ID) == before
    assert RoomService(store).publication(ROOM_ID, "same") == message


def test_replay_keeps_original_targets_and_resolves_current_sender_name(
    store: MessageTestStore,
) -> None:
    service = RoomService(store)
    request = CreateMessage(
        publication_id="replay", content="Saved routing", topic_ids=[FIRST_TOPIC]
    )
    original = service.post_message(ROOM_ID, request, member_id="alpha")
    assert original.recipient_ids == ["beta"]
    service.update_member(ROOM_ID, "alpha", UpdateMember(name="Renamed", topic_ids=[SECOND_TOPIC]))
    service.update_member(ROOM_ID, "beta", UpdateMember(name="Beta", topic_ids=[SECOND_TOPIC]))
    cursor = store.queries.metadata(ROOM_ID).event_id
    replay = service.post_message(ROOM_ID, request, member_id="alpha")
    assert replay.sender_name == "Renamed"
    assert replay.recipient_ids == original.recipient_ids
    assert replay.deliveries == original.deliveries
    assert replay.id == original.id and replay.seq == original.seq
    assert store.queries.events(ROOM_ID, cursor).events == []
    other = service.post_message(
        ROOM_ID, request.model_copy(update={"topic_ids": [SECOND_TOPIC]}), member_id="gamma"
    )
    assert other.id != original.id and other.seq == original.seq + 1


def test_concurrent_publications_have_unique_sequences_and_atomic_events(
    store: MessageTestStore,
) -> None:
    def publish(index: int) -> int:
        return _publish(store, f"concurrent {index}", publication_id=f"concurrent-{index}").seq

    cursor = store.queries.metadata(ROOM_ID).event_id
    with ThreadPoolExecutor(max_workers=4) as workers:
        sequences = list(workers.map(publish, range(12)))
    assert sorted(sequences) == list(range(1, 13))
    page = store.queries.page(ROOM_ID)
    assert [message.seq for message in page.messages] == list(range(1, 13))
    events = store.queries.events(ROOM_ID, cursor).events
    assert len(events) == 48
    assert len({item.entity_id for item in events}) == 48


def test_concurrent_replays_create_one_message_and_report_conflicting_content(
    store: MessageTestStore,
) -> None:
    def publish(index: int) -> str:
        try:
            return _publish(store, f"content-{index % 2}", publication_id="racing").id
        except RoomConflictError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=4) as workers:
        results = list(workers.map(publish, range(8)))
    saved = store.queries.page(ROOM_ID).messages
    assert len(saved) == 1
    assert results.count(saved[0].id) == 4
    assert results.count("conflict") == 4
    assert store.queries.metadata(ROOM_ID).summary.pending_count == 3


@pytest.mark.parametrize(
    "failure", ["topic", "mention", "recipient", "delivery", "receipt", "client"]
)
def test_failed_message_insert_rolls_back_resources_routes_deliveries_and_events(
    store: MessageTestStore, failure: str
) -> None:
    existing = _publish(store)
    with store.database.write() as session:
        session.add(
            SessionRecord(
                room_id="other",
                id="foreign-session",
                name="Foreign",
                provider="codex",
                project_path="D:/other",
                presence="available",
            )
        )
    before = store.queries.snapshot(ROOM_ID)
    error = ValueError if failure == "receipt" else IntegrityError
    with pytest.raises(error), store.database.write() as session:
        rooms = SQLAlchemyRoomRepository(session)
        state = rooms.resources(ROOM_ID)
        original = deepcopy(state)
        state.room.description = "must roll back"
        rooms.save_resources(state, original)
        repository = SQLAlchemyMessageRepository(session)
        message = build_message(
            state,
            seq=repository.next_message_seq(ROOM_ID),
            content="Failure",
            topic_ids=[FIRST_TOPIC, SECOND_TOPIC],
            mentioned_member_ids=[],
            sender_id="user",
            sender_name="你",
            created_at=OBSERVED_AT,
        )
        if failure == "topic":
            message.topic_ids.append("missing")
        elif failure == "mention":
            message.mentioned_member_ids.append("missing")
        elif failure == "recipient":
            message.recipient_ids.append("missing")
        elif failure == "delivery":
            message.deliveries[0].target_session_id = "foreign-session"
        elif failure == "receipt":
            message.deliveries[0].queued_submission_id = "saved"
            message.deliveries[0].receipt = {"id": "wrong", "clientUserMessageId": "wrong"}
        else:
            message.deliveries[0].client_message_id = existing.deliveries[0].client_message_id
        repository.insert_message(ROOM_ID, message)
    assert store.queries.snapshot(ROOM_ID) == before


@pytest.mark.parametrize("commit", [False, True])
def test_request_shares_resource_and_message_writes_until_owner_finishes(
    store: MessageTestStore, commit: bool
) -> None:
    transaction = store.database.request_transaction()
    request_store = store.for_request(transaction)
    assert request_store.queries.rooms() == store.queries.rooms()
    assert transaction.session is None
    service = RoomService(request_store)
    service.update_member(
        ROOM_ID, "alpha", UpdateMember(name="Request alias", topic_ids=[FIRST_TOPIC])
    )
    message = _publish(request_store)
    assert request_store.queries.message(ROOM_ID, message.id) == message
    assert store.queries.page(ROOM_ID).messages == []
    assert store.queries.member_for_session(ROOM_ID, "session-alpha").name == "Alpha"
    transaction.finish(commit=commit)
    assert len(store.queries.page(ROOM_ID).messages) == int(commit)
    assert store.queries.member_for_session(ROOM_ID, "session-alpha").name == (
        "Request alias" if commit else "Alpha"
    )


@pytest.mark.parametrize(
    ("topic_id", "member_id", "keyword", "before_seq", "limit"),
    [
        (None, None, None, None, 50),
        (FIRST_TOPIC, None, None, None, 9),
        (None, "alpha", None, None, 9),
        (FIRST_TOPIC, "alpha", None, 76, 7),
        (SECOND_TOPIC, "beta", None, 26, 7),
        (FIRST_TOPIC, "user", None, None, 5),
        (None, None, " history 1 ", 100, 5),
        (FIRST_TOPIC, "alpha", "history 1", 100, 5),
        (None, None, "   ", 1, 5),
        (None, None, None, 1000, 200),
        ("empty-topic", None, None, None, 5),
    ],
)
def test_query_pages_match_existing_scope_order_totals_and_cursors(
    store: MessageTestStore,
    topic_id: str | None,
    member_id: str | None,
    keyword: str | None,
    before_seq: int | None,
    limit: int,
) -> None:
    messages = _history(store)
    queries = store.queries
    scoped = [
        message
        for message in messages
        if (topic_id is None or topic_id in message.topic_ids)
        and (
            member_id is None
            or message.sender_id == member_id
            or member_id in message.recipient_ids
        )
    ]
    matching = [
        message for message in scoped if keyword is None or keyword.strip() in message.content
    ]
    older = [message for message in matching if before_seq is None or message.seq < before_seq]
    selected = older[-limit:]
    expected_page = MessagePage(
        messages=selected,
        has_more=len(older) > limit,
        next_before_seq=selected[0].seq if len(older) > limit else None,
        has_newer=before_seq is not None and any(message.seq >= before_seq for message in matching),
    )
    page = queries.page(
        ROOM_ID,
        topic_id=topic_id,
        member_id=member_id,
        keyword=keyword,
        before_seq=before_seq,
        limit=limit,
    )
    assert page == expected_page
    snapshot = queries.snapshot(
        ROOM_ID,
        topic_id=topic_id,
        member_id=member_id,
        keyword=keyword,
        before_seq=before_seq,
        limit=limit,
    )
    assert snapshot.messages == expected_page.messages
    assert snapshot.has_more == expected_page.has_more
    assert snapshot.next_before_seq == expected_page.next_before_seq
    assert snapshot.has_newer == expected_page.has_newer
    assert snapshot.summary == queries.metadata(ROOM_ID).summary
    queued = [
        message for message in reversed(scoped) if before_seq is None or message.seq < before_seq
    ]
    assert queries.queue(
        ROOM_ID,
        topic_id=topic_id,
        member_id=member_id,
        before_seq=before_seq,
        limit=limit,
    ) == MessageQueuePage(
        messages=queued[:limit],
        total_messages=len(scoped),
        has_more=len(queued) > limit,
        next_before_seq=queued[limit - 1].seq if len(queued) > limit else None,
    )
    assert queries.snapshot(ROOM_ID).summary.total_messages == 125


def test_queue_counts_each_message_once_and_keeps_partial_delivery_history(
    store: MessageTestStore,
) -> None:
    messages = _history(store, 6)
    with store.database.write() as session:
        session.execute(update(DeliveryRecord).values(status="received"))
        for message, status in zip(
            messages[1:], ("queued", "pending", "submitting", "rejected", "unknown"), strict=True
        ):
            session.execute(
                update(DeliveryRecord)
                .where(
                    DeliveryRecord.message_id == message.id,
                )
                .values(status=status)
            )
        session.execute(
            update(DeliveryRecord)
            .where(
                DeliveryRecord.message_id == messages[1].id,
                DeliveryRecord.target_member_id == "gamma",
            )
            .values(status="received")
        )
    page = store.queries.queue(ROOM_ID)
    assert [message.seq for message in page.messages] == [4, 3, 2]
    assert page.total_messages == 3
    assert {delivery.status for delivery in page.messages[-1].deliveries} == {"queued", "received"}
    assert store.queries.queue("other").messages == []
    with store.database.write() as session:
        session.execute(update(DeliveryRecord).values(status="received"))
    assert store.queries.queue(ROOM_ID).total_messages == 0
    assert store.queries.message(ROOM_ID, messages[1].id).deliveries


def test_history_keysets_remain_stable_during_a_new_publication(store: MessageTestStore) -> None:
    _history(store)
    first = store.queries.snapshot(ROOM_ID)
    assert [message.seq for message in first.messages] == list(range(76, 126))
    assert first.has_more and not first.has_newer and first.next_before_seq == 76
    latest = _publish(store, "after first page")
    assert latest.seq == 126
    second = store.queries.page(ROOM_ID, before_seq=first.next_before_seq)
    third = store.queries.page(ROOM_ID, before_seq=second.next_before_seq)
    assert [message.seq for message in second.messages] == list(range(26, 76))
    assert [message.seq for message in third.messages] == list(range(1, 26))
    assert second.has_more and second.has_newer
    assert not third.has_more and third.has_newer and third.next_before_seq is None
    assert store.queries.snapshot(ROOM_ID).summary.total_messages == 126


def test_queue_pages_descend_over_the_entire_scope_without_duplicate_messages(
    store: MessageTestStore,
) -> None:
    _history(store)
    cursor = None
    messages: list[Message] = []
    while True:
        page = store.queries.queue(ROOM_ID, before_seq=cursor)
        assert page.total_messages == 125
        messages.extend(page.messages)
        if not page.has_more:
            assert page.next_before_seq is None
            break
        assert page.next_before_seq == page.messages[-1].seq
        cursor = page.next_before_seq
    assert [message.seq for message in messages] == list(range(125, 0, -1))
    assert len({message.id for message in messages}) == 125


@pytest.mark.parametrize(
    ("keyword", "expected"),
    [
        ("%", [1]),
        ("_", [1]),
        ("TOKEN", [3]),
        ("token", [4]),
        (" literal ", [1, 2]),
        ("   ", [1, 2, 3, 4, 5]),
        (None, [1, 2, 3, 4, 5]),
        ("' OR 1=1 --", [5]),
    ],
)
def test_keyword_search_is_literal_case_sensitive_and_strips_blank_edges(
    store: MessageTestStore, keyword: str | None, expected: list[int]
) -> None:
    for content in (
        "literal 100%_done",
        "literal 100Xdone",
        "Case TOKEN",
        "case token",
        "' OR 1=1 --",
    ):
        _publish(store, content)
    page = store.queries.page(ROOM_ID, keyword=keyword)
    assert [message.seq for message in page.messages] == expected
    assert store.queries.snapshot(ROOM_ID, keyword=keyword).summary.total_messages == 5


def test_member_scope_uses_senders_and_saved_recipients_with_explicit_topic_intersection(
    store: MessageTestStore,
) -> None:
    _publish(store)
    RoomService(store).post_message(
        ROOM_ID,
        CreateMessage(
            publication_id="to-human",
            content="Direct routing",
            mentioned_member_ids=["user", "gamma"],
        ),
        member_id="beta",
    )
    assert [message.seq for message in store.queries.page(ROOM_ID, member_id="user").messages] == [
        1,
        2,
    ]
    assert [message.seq for message in store.queries.queue(ROOM_ID, member_id="user").messages] == [
        2,
        1,
    ]
    assert [
        message.seq
        for message in store.queries.page(
            ROOM_ID,
            member_id="user",
            topic_id=SECOND_TOPIC,
        ).messages
    ] == [1]


def test_soft_deleted_topics_and_members_remain_in_historical_queries(
    store: MessageTestStore,
) -> None:
    messages = _history(store, 6)
    service = RoomService(store)
    service.update_member(
        ROOM_ID, "alpha", UpdateMember(name="Historical alias", topic_ids=[FIRST_TOPIC])
    )
    service.delete_topic(ROOM_ID, FIRST_TOPIC)
    service.delete_member(ROOM_ID, "alpha")
    page = store.queries.page(ROOM_ID, topic_id=FIRST_TOPIC, member_id="alpha")
    assert page.messages
    assert page.messages == [
        message.model_copy(update={"sender_name": "Historical alias"})
        if message.sender_id == "alpha"
        else message
        for message in messages
        if FIRST_TOPIC in message.topic_ids
        and (message.sender_id == "alpha" or "alpha" in message.recipient_ids)
    ]
    assert all(
        message.sender_name == "Historical alias"
        for message in page.messages
        if message.sender_id == "alpha"
    )
    assert any(
        delivery.target_member_id == "alpha"
        for message in page.messages
        for delivery in message.deliveries
    )


@pytest.mark.parametrize(("topic_id", "member_id"), [("missing", None), (None, "missing")])
def test_query_and_clear_validate_scope_without_changing_events(
    store: MessageTestStore, topic_id: str | None, member_id: str | None
) -> None:
    _history(store, 3)
    before = store.queries.metadata(ROOM_ID)
    for read in (store.queries.page, store.queries.queue, store.queries.snapshot):
        with pytest.raises(RoomNotFoundError):
            read(ROOM_ID, topic_id=topic_id, member_id=member_id)
    with pytest.raises(RoomNotFoundError):
        RoomService(store).clear_queue(ROOM_ID, topic_id=topic_id, member_id=member_id)
    assert store.queries.metadata(ROOM_ID) == before
    with pytest.raises(RoomNotFoundError, match="聊天室不存在"):
        store.queries.queue("missing")
    with pytest.raises(RoomNotFoundError, match="消息不存在"):
        store.queries.message(ROOM_ID, "missing")


def test_clear_spans_all_pages_counts_messages_and_preserves_receipts_and_history(
    store: MessageTestStore,
) -> None:
    _history(store)
    with store.database.write() as session:
        session.execute(
            update(DeliveryRecord).values(
                status="queued",
                queued_at=OBSERVED_AT,
                queued_submission_id=DeliveryRecord.id,
                receipt_metadata={"accepted": True},
            )
        )
        session.execute(
            update(DeliveryRecord)
            .where(
                DeliveryRecord.message_id == f"{ROOM_ID}-msg-0003",
                DeliveryRecord.target_member_id == "alpha",
            )
            .values(status="received", received_at=OBSERVED_AT)
        )
    original = store.queries.message(ROOM_ID, f"{ROOM_ID}-msg-0003")
    cursor = store.queries.metadata(ROOM_ID).event_id
    total = store.queries.queue(
        ROOM_ID, topic_id=FIRST_TOPIC, member_id="alpha", limit=1
    ).total_messages
    assert total > 50
    result = RoomService(store).clear_queue(ROOM_ID, topic_id=FIRST_TOPIC, member_id="alpha")
    assert result.removed_messages == total
    assert store.queries.queue(ROOM_ID, topic_id=FIRST_TOPIC, member_id="alpha").messages == []
    assert store.queries.queue(ROOM_ID).total_messages > 0
    saved = store.queries.message(ROOM_ID, original.id)
    for before, after in zip(original.deliveries, saved.deliveries, strict=True):
        assert after.status == before.status
        assert after.queued_at == before.queued_at
        assert after.received_at == before.received_at
        assert after.receipt == before.receipt
        assert (after.deleted_at is not None) == (before.status != "received")
    metadata = store.queries.metadata(ROOM_ID)
    assert metadata.summary.total_messages == 125
    assert metadata.summary.received_count == 1
    events = store.queries.events(ROOM_ID, cursor).events
    assert all(item.kind == "delivery" for item in events)
    assert len({item.message_id for item in events}) == total
    remaining = store.queries.queue(ROOM_ID)
    assert remaining.total_messages == 125 - total
    assert all(FIRST_TOPIC not in message.topic_ids for message in remaining.messages)
    assert metadata.summary.queued_count == sum(
        len(message.deliveries) for message in remaining.messages
    )
    assert (
        RoomService(store)
        .clear_queue(ROOM_ID, topic_id=FIRST_TOPIC, member_id="alpha")
        .removed_messages
        == 0
    )
    assert store.queries.events(ROOM_ID, metadata.event_id).events == []


def test_codex_targets_use_only_deleted_waiting_deliveries_and_saved_receipt_columns(
    store: MessageTestStore,
) -> None:
    messages = _history(store, 6)
    with store.database.write() as session:
        for message, status in zip(
            messages,
            ("queued", "submitting", "pending", "received", "rejected", "unknown"),
            strict=True,
        ):
            session.execute(
                update(DeliveryRecord)
                .where(
                    DeliveryRecord.message_id == message.id,
                )
                .values(status=status, queued_submission_id=DeliveryRecord.id)
            )
        session.execute(
            update(DeliveryRecord)
            .where(
                DeliveryRecord.message_id == messages[1].id,
            )
            .values(queued_submission_id=None)
        )
    with store.write_rooms() as repository:
        assert repository.codex_queue_targets(ROOM_ID, topic_id=None, member_id=None) == []
        assert (
            repository.clear_queue(ROOM_ID, topic_id=None, member_id=None, deleted_at=OBSERVED_AT)
            == 3
        )
        targets = repository.codex_queue_targets(ROOM_ID, topic_id=None, member_id=None)
        assert len(targets) == len(messages[0].deliveries) + len(messages[1].deliveries)
        assert {target.submission_id for target in targets if target.submission_id is not None} == {
            delivery.id for delivery in messages[0].deliveries
        }
        assert len([target for target in targets if target.submission_id is None]) == len(
            messages[1].deliveries
        )
    assert {(target.session_id, target.submission_id) for target in targets} == {
        *[(delivery.target_session_id, delivery.id) for delivery in messages[0].deliveries],
        *[(delivery.target_session_id, None) for delivery in messages[1].deliveries],
    }
    with store.read_rooms() as repository:
        assert repository.codex_queue_targets(ROOM_ID, topic_id=None, member_id=None) == targets


def test_persistent_events_keep_paging_and_request_resync_for_missing_or_foreign_cursors(
    store: MessageTestStore,
) -> None:
    _history(store, 6)
    with store.database.read() as session:
        expected_ids = list(
            session.scalars(
                select(RoomEventRecord.event_id)
                .where(
                    RoomEventRecord.room_id == ROOM_ID,
                )
                .order_by(RoomEventRecord.event_id)
            )
        )
    cursor = 0
    event_ids: list[int] = []
    while True:
        page = store.queries.events(ROOM_ID, cursor, limit=3)
        assert not page.resync_required
        event_ids.extend(item.event_id for item in page.events)
        cursor = page.next_event_id
        if not page.has_more:
            break
    assert event_ids == sorted(set(event_ids))
    assert event_ids == expected_ids
    assert cursor == store.queries.metadata(ROOM_ID).event_id
    assert store.queries.events(ROOM_ID, cursor).next_event_id == cursor
    with store.database.write() as session:
        foreign = session.scalar(
            select(RoomEventRecord.event_id).where(RoomEventRecord.room_id == "other").limit(1)
        )
        session.execute(delete(RoomEventRecord).where(RoomEventRecord.event_id == event_ids[0]))
    assert foreign is not None
    for invalid_cursor in (event_ids[0], foreign, cursor + 100):
        page = store.queries.events(ROOM_ID, invalid_cursor)
        assert page.resync_required and page.events == [] and not page.has_more
        assert page.next_event_id == cursor


def test_identical_replay_ignores_topic_order_and_duplicates(store: MessageTestStore) -> None:
    original = _publish(store, publication_id="same-set")
    cursor = store.queries.metadata(ROOM_ID).event_id
    replay = RoomService(store).post_message(
        ROOM_ID,
        CreateMessage(
            publication_id="same-set",
            content=original.content,
            topic_ids=[SECOND_TOPIC, FIRST_TOPIC, SECOND_TOPIC],
        ),
    )
    assert replay == original
    assert store.queries.events(ROOM_ID, cursor).events == []


def test_queue_clear_synchronizes_cached_models_and_rolls_back_with_its_events(
    store: MessageTestStore,
) -> None:
    original = _publish(store)
    before = store.queries.snapshot(ROOM_ID)
    with pytest.raises(RuntimeError, match="abort"), store.database.write() as session:
        record = session.get(DeliveryRecord, (ROOM_ID, original.deliveries[0].id))
        assert record is not None
        repository = SQLAlchemyMessageRepository(session)
        assert (
            repository.clear_queue(
                ROOM_ID,
                topic_id=None,
                member_id=None,
                deleted_at=OBSERVED_AT,
            )
            == 1
        )
        assert record.deleted_at == OBSERVED_AT and record.updated_at == OBSERVED_AT
        assert record.status == "pending"
        assert SQLAlchemyRoomQueries(session).queue(ROOM_ID).total_messages == 0
        saved = MessageQueries(session).message(ROOM_ID, original.id)
        assert all(delivery.deleted_at == OBSERVED_AT for delivery in saved.deliveries)
        raise RuntimeError("abort")
    assert store.queries.snapshot(ROOM_ID) == before


def test_message_and_publication_keys_do_not_leak_across_rooms(store: MessageTestStore) -> None:
    original = _publish(store, publication_id="room-scoped")
    foreign = original.model_copy(
        deep=True,
        update={
            "content": "Other room",
            "topic_ids": [],
            "mentioned_member_ids": [],
            "recipient_ids": [],
            "deliveries": [],
        },
    )
    with store.database.write() as session:
        SQLAlchemyMessageRepository(session).insert_message("other", foreign)
    assert store.queries.message(ROOM_ID, original.id) == original
    assert store.queries.message("other", original.id) == foreign
    with store.read_rooms() as repository:
        assert repository.publication(ROOM_ID, "user", "room-scoped") == original
        assert repository.publication("other", "user", "room-scoped") == foreign
    RoomService(store).clear_queue(ROOM_ID)
    assert store.queries.message("other", original.id) == foreign


@pytest.mark.parametrize(
    "historical_time",
    [
        "2026-11-11T12:34:56.123456+08:00",
        "2026-11-10T21:34:56.000001-07:00",
        "2026-11-11T04:34:56Z",
    ],
)
def test_message_reads_preserve_current_head_historical_time_receipt_and_deletion_formats(
    store: MessageTestStore, historical_time: str
) -> None:
    original = _publish(store)
    delivery = original.deliveries[0]
    with store.database.write() as session:
        connection = session.connection()
        connection.exec_driver_sql(
            "UPDATE messages SET created_at = ? WHERE room_id = ? AND id = ?",
            (historical_time, ROOM_ID, original.id),
        )
        connection.exec_driver_sql(
            "UPDATE deliveries SET status = 'queued', updated_at = ?, queued_at = ?, "
            "deleted_at = ?, queued_submission_id = 'historical-queue', "
            "receipt_metadata = ? WHERE room_id = ? AND id = ?",
            (
                historical_time,
                historical_time,
                historical_time,
                '{"accepted":true,"详情":{"次数":1}}',
                ROOM_ID,
                delivery.id,
            ),
        )
    saved = store.queries.message(ROOM_ID, original.id)
    assert saved.content == original.content and saved.recipient_ids == original.recipient_ids
    expected = datetime.fromisoformat(historical_time)
    assert saved.created_at.isoformat() == expected.isoformat()
    receipt = saved.deliveries[0]
    assert receipt.updated_at.isoformat() == expected.isoformat()
    assert receipt.queued_at is not None and receipt.deleted_at is not None
    assert receipt.queued_at.isoformat() == expected.isoformat()
    assert receipt.deleted_at.isoformat() == expected.isoformat()
    assert receipt.received_at is None
    assert receipt.receipt == {
        "accepted": True,
        "详情": {"次数": 1},
        "id": "historical-queue",
        "clientUserMessageId": delivery.client_message_id,
    }


@pytest.mark.parametrize("limit", [1, 25])
def test_message_page_batches_relationship_and_delivery_reads(
    store: MessageTestStore, limit: int
) -> None:
    _history(store, 30)
    statements: list[str] = []

    def record_select(
        connection: Connection,
        cursor: object,
        statement: str,
        parameters: object,
        context: ExecutionContext,
        executemany: bool,
    ) -> None:
        if statement.startswith("SELECT"):
            statements.append(statement)

    event.listen(store.database.engine, "before_cursor_execute", record_select)
    try:
        page = store.queries.page(ROOM_ID, limit=limit)
        assert len(page.messages) == limit
        assert all(
            message.topic_ids and message.recipient_ids and message.deliveries
            for message in page.messages
        )
    finally:
        event.remove(store.database.engine, "before_cursor_execute", record_select)
    assert len(statements) == 6


def test_shared_message_reader_accepts_visibility_expression_without_fetching_deliveries(
    store: MessageTestStore,
) -> None:
    _history(store, 6)
    with store.database.read() as session:
        queries = MessageQueries(session)
        targeted = (
            select(DeliveryRecord.message_id)
            .where(
                DeliveryRecord.room_id == MessageRecord.room_id,
                DeliveryRecord.message_id == MessageRecord.id,
                DeliveryRecord.target_member_id == "alpha",
            )
            .correlate(MessageRecord)
            .exists()
        )
        messages = queries.read(
            ROOM_ID,
            queries.statement()
            .where(
                MessageRecord.room_id == ROOM_ID,
                targeted,
            )
            .order_by(MessageRecord.seq),
            include_deliveries=False,
        )
        assert messages
        assert all(message.deliveries == [] for message in messages)
        assert all("alpha" in message.recipient_ids for message in messages)
