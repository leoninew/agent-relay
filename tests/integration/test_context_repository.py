from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import event, select, update
from sqlalchemy.engine import Connection, ExecutionContext
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import ConnectionPoolEntry
from sqlalchemy_message_fixtures import (
    FIRST_TOPIC,
    OBSERVED_AT,
    ROOM_ID,
    SECOND_TOPIC,
    MessageTestStore,
    seed_message_store,
)

from agent_relay.application.members.context import (
    ContextQuery,
    ContextRepository,
    ContextResult,
    MemberContext,
)
from agent_relay.application.rooms.contracts import CreateMessage, UpdateMember
from agent_relay.application.rooms.service import RoomService
from agent_relay.domain.rooms.errors import RoomNotFoundError
from agent_relay.domain.rooms.models import Message, TopicPosition
from agent_relay.domain.rooms.rules import build_message
from agent_relay.infrastructure.persistence.database import Database
from agent_relay.infrastructure.persistence.member_context import SQLAlchemyMemberContext
from agent_relay.infrastructure.persistence.message_queries import MessageQueries
from agent_relay.infrastructure.persistence.migrations import run_migrations
from agent_relay.infrastructure.persistence.models import (
    ContextMessageRecord,
    ContextQueryRecord,
    DeliveryRecord,
    MemberRecord,
    RoomEventRecord,
    TopicPositionRecord,
    TopicRecord,
)
from agent_relay.infrastructure.persistence.repositories.context import SQLAlchemyContextRepository
from agent_relay.infrastructure.persistence.repositories.rooms import SQLAlchemyRoomRepository
from agent_relay.infrastructure.persistence.resource_queries import ResourceQueries

pytestmark = pytest.mark.integration


@dataclass
class ContextEnvironment:
    database: Database
    rooms: MessageTestStore
    context: SQLAlchemyMemberContext


@dataclass(frozen=True)
class StoredFacts:
    queries: list[str]
    provided: list[tuple[str, str, str, int]]
    positions: list[tuple[str, str, str, int, datetime]]
    events: list[tuple[str, str, str]]


@pytest.fixture
def environment(tmp_path: Path) -> Iterator[ContextEnvironment]:
    path = tmp_path / "context.sqlite3"
    run_migrations(path)
    database = Database(path)
    try:
        yield ContextEnvironment(
            database, seed_message_store(database), SQLAlchemyMemberContext(database)
        )
    finally:
        database.close()


@pytest.fixture
def checked_out(environment: ContextEnvironment) -> Iterator[set[int]]:
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
    environment: ContextEnvironment,
    *,
    topics: tuple[str, ...] = (),
    targets: tuple[str, ...] = ("beta",),
    sender_id: str | None = None,
    content: str = "Context facts",
    room_id: str = ROOM_ID,
) -> Message:
    return RoomService(environment.rooms).post_message(
        room_id,
        CreateMessage(
            publication_id=uuid4().hex,
            content=content,
            topic_ids=list(topics),
            mentioned_member_ids=list(targets),
        ),
        member_id=sender_id,
    )


def _subscribe(
    environment: ContextEnvironment, topics: list[str], member_id: str = "alpha"
) -> None:
    RoomService(environment.rooms).update_member(
        ROOM_ID, member_id, UpdateMember(name=member_id.title(), topic_ids=topics)
    )


def _history(environment: ContextEnvironment, total: int = 65) -> list[Message]:
    messages: list[Message] = []
    with environment.rooms.write_rooms() as repository:
        state = repository.resources(ROOM_ID)
        for sequence in range(1, total + 1):
            message = build_message(
                state,
                seq=sequence,
                content=f"Context%_ marker {sequence}",
                topic_ids=[FIRST_TOPIC, SECOND_TOPIC] if sequence % 10 == 0 else [FIRST_TOPIC],
                mentioned_member_ids=[],
                sender_id="user",
                sender_name="你",
                created_at=OBSERVED_AT,
            )
            repository.insert_message(ROOM_ID, message)
            messages.append(message)
    return messages


def _query(
    environment: ContextEnvironment, request: ContextQuery, member_id: str = "alpha"
) -> ContextResult:
    return environment.context.query(ROOM_ID, member_id, request)


def _positions(result: ContextResult) -> dict[str, TopicPosition]:
    return {position.topic_id: position for position in result.positions}


def _facts(environment: ContextEnvironment) -> StoredFacts:
    with environment.database.read() as session:
        return StoredFacts(
            list(session.scalars(select(ContextQueryRecord.id).order_by(ContextQueryRecord.id))),
            list(
                session.execute(
                    select(
                        ContextMessageRecord.room_id,
                        ContextMessageRecord.query_id,
                        ContextMessageRecord.message_id,
                        ContextMessageRecord.position,
                    ).order_by(ContextMessageRecord.query_id, ContextMessageRecord.position)
                )
                .tuples()
                .all()
            ),
            list(
                session.execute(
                    select(
                        TopicPositionRecord.room_id,
                        TopicPositionRecord.member_id,
                        TopicPositionRecord.topic_id,
                        TopicPositionRecord.seq,
                        TopicPositionRecord.updated_at,
                    ).order_by(
                        TopicPositionRecord.room_id,
                        TopicPositionRecord.member_id,
                        TopicPositionRecord.topic_id,
                    )
                )
                .tuples()
                .all()
            ),
            list(
                session.execute(
                    select(
                        RoomEventRecord.room_id, RoomEventRecord.kind, RoomEventRecord.entity_id
                    ).order_by(RoomEventRecord.event_id)
                )
                .tuples()
                .all()
            ),
        )


def _assert_provided(
    environment: ContextEnvironment, result: ContextResult, room_id: str = ROOM_ID
) -> None:
    assert result.query_id is not None
    with environment.database.read() as session:
        assert list(
            session.execute(
                select(
                    ContextMessageRecord.room_id,
                    ContextMessageRecord.message_id,
                    ContextMessageRecord.position,
                )
                .where(ContextMessageRecord.query_id == result.query_id)
                .order_by(ContextMessageRecord.position)
            ).tuples()
        ) == [(room_id, message.id, position) for position, message in enumerate(result.messages)]


def _clone_other_resources(environment: ContextEnvironment) -> None:
    with environment.rooms.write_rooms() as repository:
        source = repository.resources(ROOM_ID)
        other = repository.resources("other")
        original = deepcopy(other)
        other.topics = deepcopy(source.topics)
        other.sessions = deepcopy(source.sessions)
        other.members.extend(deepcopy([member for member in source.members if member.id != "user"]))
        repository.save_resources(other, original)


def test_catalog_and_positions_are_lightweight_ordered_reads_without_side_effects(
    environment: ContextEnvironment, checked_out: set[int]
) -> None:
    _history(environment, 12)
    before = _facts(environment)
    context: MemberContext = environment.context
    catalog = context.catalog(ROOM_ID, "alpha")
    assert not checked_out
    assert (catalog.room_id, catalog.room_name, catalog.room_description, catalog.project_path) == (
        ROOM_ID,
        "Messages",
        "Queries",
        "D:/messages",
    )
    assert [(topic.id, topic.subscribed) for topic in catalog.topics] == [
        (FIRST_TOPIC, True),
        (SECOND_TOPIC, True),
        ("empty-topic", False),
    ]
    assert [member.id for member in catalog.members] == ["user", "alpha", "beta", "gamma"]
    assert catalog.members[1].topic_ids == [FIRST_TOPIC, SECOND_TOPIC]
    current = context.positions(ROOM_ID, "alpha")
    assert [(position.topic_id, position.seq, position.later_count) for position in current] == [
        (FIRST_TOPIC, 0, 12),
        (SECOND_TOPIC, 0, 1),
    ]
    assert all(position.updated_at is None for position in current)
    assert not checked_out and _facts(environment) == before
    catalog.members[1].topic_ids.clear()
    assert context.catalog(ROOM_ID, "alpha").members[1].topic_ids == [FIRST_TOPIC, SECOND_TOPIC]


def test_catalog_filters_deleted_resources_but_preserves_stored_member_topic_order(
    environment: ContextEnvironment,
) -> None:
    with environment.database.write() as session:
        session.execute(
            update(TopicRecord)
            .where(TopicRecord.room_id == ROOM_ID, TopicRecord.id == SECOND_TOPIC)
            .values(deleted_at=OBSERVED_AT)
        )
        session.execute(
            update(MemberRecord)
            .where(MemberRecord.room_id == ROOM_ID, MemberRecord.id == "gamma")
            .values(deleted_at=OBSERVED_AT)
        )
    catalog = environment.context.catalog(ROOM_ID, "alpha")
    assert [topic.id for topic in catalog.topics] == [FIRST_TOPIC, "empty-topic"]
    assert [member.id for member in catalog.members] == ["user", "alpha", "beta"]
    assert catalog.members[1].topic_ids == [FIRST_TOPIC, SECOND_TOPIC]
    assert [position.topic_id for position in environment.context.positions(ROOM_ID, "alpha")] == [
        FIRST_TOPIC
    ]


@pytest.mark.parametrize("action", ["catalog", "positions", "query"])
@pytest.mark.parametrize("missing", ["room", "member", "deleted"])
def test_all_context_actions_reject_missing_or_inactive_members_without_writes(
    environment: ContextEnvironment, action: str, missing: str, checked_out: set[int]
) -> None:
    room_id, member_id = ROOM_ID, "alpha"
    if missing == "room":
        room_id = "missing"
    elif missing == "member":
        member_id = "missing"
    else:
        with environment.database.write() as session:
            session.execute(
                update(MemberRecord)
                .where(MemberRecord.room_id == ROOM_ID, MemberRecord.id == member_id)
                .values(deleted_at=OBSERVED_AT)
            )
    before = _facts(environment)
    with pytest.raises(RoomNotFoundError, match="成员不存在"):
        if action == "query":
            environment.context.query(room_id, member_id, ContextQuery())
        elif action == "catalog":
            environment.context.catalog(room_id, member_id)
        else:
            environment.context.positions(room_id, member_id)
    assert not checked_out and _facts(environment) == before


def test_context_visibility_combines_own_publications_deliveries_and_current_subscriptions(
    environment: ContextEnvironment,
) -> None:
    _subscribe(environment, [])
    own = _publish(environment, sender_id="alpha")
    direct = _publish(environment, targets=("alpha",), sender_id="beta")
    subscribed = _publish(environment, topics=(FIRST_TOPIC,))
    invisible = _publish(environment, topics=(SECOND_TOPIC,), targets=("gamma",))
    assert all(delivery.target_member_id != "alpha" for delivery in subscribed.deliveries)
    _subscribe(environment, [FIRST_TOPIC])
    result = _query(environment, ContextQuery())
    assert [message.id for message in result.messages] == [own.id, direct.id, subscribed.id]
    assert _positions(result)[FIRST_TOPIC].seq == subscribed.seq
    _assert_provided(environment, result)
    before = _facts(environment)
    with pytest.raises(RoomNotFoundError, match="查阅范围"):
        _query(environment, ContextQuery(message_id=invisible.id))
    assert _facts(environment) == before
    _subscribe(environment, [])
    recent = _query(environment, ContextQuery())
    assert [message.id for message in recent.messages] == [own.id, direct.id]
    assert recent.positions == []
    _subscribe(environment, [SECOND_TOPIC])
    assert _query(environment, ContextQuery(message_id=invisible.id)).messages[0].id == invisible.id


def test_saved_human_recipient_does_not_replace_an_actual_delivery_visibility_rule(
    environment: ContextEnvironment,
) -> None:
    message = _publish(environment, sender_id="beta", targets=("user",))
    assert message.recipient_ids == ["user"] and message.deliveries == []
    with environment.database.read() as session:
        messages = MessageQueries(session)
        managed = messages.read(
            ROOM_ID,
            messages.statement().where(messages.scope(ROOM_ID, topic_id=None, member_id="user")),
        )
        assert [item.id for item in managed] == [message.id]
    with pytest.raises(RoomNotFoundError, match="查阅范围"):
        _query(environment, ContextQuery(message_id=message.id), "user")
    assert _query(environment, ContextQuery(), "user").messages == []


def test_deleting_a_topic_removes_subscription_visibility_but_keeps_historical_deliveries(
    environment: ContextEnvironment,
) -> None:
    _subscribe(environment, [])
    subscribed = _publish(environment, topics=(FIRST_TOPIC,))
    direct = _publish(environment, topics=(FIRST_TOPIC,), targets=("alpha",), sender_id="beta")
    _subscribe(environment, [FIRST_TOPIC])
    assert [message.id for message in _query(environment, ContextQuery()).messages] == [
        subscribed.id,
        direct.id,
    ]
    with environment.database.write() as session:
        session.execute(
            update(TopicRecord)
            .where(TopicRecord.room_id == ROOM_ID, TopicRecord.id == FIRST_TOPIC)
            .values(deleted_at=OBSERVED_AT)
        )
        session.execute(
            update(MemberRecord)
            .where(MemberRecord.room_id == ROOM_ID, MemberRecord.id == "beta")
            .values(deleted_at=OBSERVED_AT, name="Historical publisher")
        )
    before = _facts(environment)
    with pytest.raises(RoomNotFoundError, match="查阅范围"):
        _query(environment, ContextQuery(message_id=subscribed.id))
    assert _facts(environment) == before
    result = _query(environment, ContextQuery())
    assert [message.id for message in result.messages] == [direct.id]
    assert result.messages[0].sender_name == "Historical publisher"
    assert result.messages[0].topic_ids == [FIRST_TOPIC] and result.positions == []


@pytest.mark.parametrize(
    "status", ["pending", "submitting", "queued", "received", "unknown", "rejected"]
)
def test_direct_history_remains_visible_after_delivery_or_topic_soft_deletion(
    environment: ContextEnvironment, status: str
) -> None:
    _subscribe(environment, [])
    message = _publish(environment, topics=(SECOND_TOPIC,), targets=("alpha",))
    with environment.database.write() as session:
        session.execute(
            update(DeliveryRecord)
            .where(DeliveryRecord.room_id == ROOM_ID)
            .values(status=status, deleted_at=OBSERVED_AT)
        )
        session.execute(
            update(TopicRecord)
            .where(TopicRecord.room_id == ROOM_ID, TopicRecord.id == SECOND_TOPIC)
            .values(deleted_at=OBSERVED_AT)
        )
    result = _query(environment, ContextQuery(message_id=message.id))
    assert result.messages[0].id == message.id and result.messages[0].topic_ids == [SECOND_TOPIC]
    assert result.positions == []
    _assert_provided(environment, result)


@pytest.mark.parametrize("topic_id", ["empty-topic", "missing", SECOND_TOPIC])
def test_topic_context_requires_a_current_effective_subscription(
    environment: ContextEnvironment, topic_id: str
) -> None:
    _history(environment, 10)
    if topic_id == SECOND_TOPIC:
        with environment.database.write() as session:
            session.execute(
                update(TopicRecord)
                .where(TopicRecord.room_id == ROOM_ID, TopicRecord.id == SECOND_TOPIC)
                .values(deleted_at=OBSERVED_AT)
            )
    before = _facts(environment)
    with pytest.raises(RoomNotFoundError, match="未订阅"):
        _query(environment, ContextQuery(topic_id=topic_id))
    assert _facts(environment) == before


def test_bidirectional_context_pagination_keeps_chronology_and_only_records_returned_rows(
    environment: ContextEnvironment,
) -> None:
    history = _history(environment)
    backwards: list[ContextResult] = []
    request = ContextQuery(topic_id=FIRST_TOPIC, limit=20)
    while True:
        result = _query(environment, request)
        _assert_provided(environment, result)
        backwards.append(result)
        assert _positions(result)[FIRST_TOPIC].seq == 65
        assert _positions(result)[SECOND_TOPIC].seq == 0
        assert result.next_after_seq is None
        if not result.has_more:
            assert result.next_before_seq is None
            break
        assert result.next_before_seq == result.messages[0].seq
        request = ContextQuery(topic_id=FIRST_TOPIC, limit=20, before_seq=result.next_before_seq)
    assert len(backwards) == 4
    assert [message.id for page in reversed(backwards) for message in page.messages] == [
        message.id for message in history
    ]
    forward: list[int] = []
    request = ContextQuery(topic_id=FIRST_TOPIC, limit=20, after_seq=0)
    while True:
        result = _query(environment, request)
        _assert_provided(environment, result)
        forward.extend(message.seq for message in result.messages)
        assert result.next_before_seq is None
        if not result.has_more:
            assert result.next_after_seq is None
            break
        assert result.next_after_seq == result.messages[-1].seq
        request = ContextQuery(topic_id=FIRST_TOPIC, limit=20, after_seq=result.next_after_seq)
    assert forward == list(range(1, 66))


@pytest.mark.parametrize(
    ("after_seq", "limit", "expected", "more"),
    [
        (None, 3, [2, 3, 4], True),
        (None, 4, [1, 2, 3, 4], False),
        (0, 3, [1, 2, 3], True),
        (0, 4, [1, 2, 3, 4], False),
    ],
)
def test_page_lookahead_is_never_a_provided_message(
    environment: ContextEnvironment,
    after_seq: int | None,
    limit: int,
    expected: list[int],
    more: bool,
) -> None:
    _history(environment, 4)
    result = _query(environment, ContextQuery(limit=limit, after_seq=after_seq))
    assert [message.seq for message in result.messages] == expected and result.has_more == more
    assert len(_facts(environment).provided) == len(expected)
    assert _positions(result)[FIRST_TOPIC].seq == max(expected)
    _assert_provided(environment, result)


@pytest.mark.parametrize(
    ("keyword", "expected"),
    [
        ("%_", [1]),
        ("_", [1, 2]),
        ("Case", [1]),
        ("case", [2]),
        ("  Case%_  ", [1]),
        ("' OR 1=1 --", [3]),
    ],
)
def test_context_search_uses_literal_case_sensitive_body_text(
    environment: ContextEnvironment, keyword: str, expected: list[int]
) -> None:
    for content in ("Case%_ body", "case_ body", "' OR 1=1 --"):
        _publish(environment, topics=(FIRST_TOPIC,), content=content)
    result = _query(environment, ContextQuery(keyword=keyword))
    assert [message.seq for message in result.messages] == expected
    _assert_provided(environment, result)
    with environment.database.read() as session:
        record = session.get(ContextQueryRecord, result.query_id)
        assert record is not None and record.keyword == keyword.strip()


def test_provided_record_preserves_request_fields_order_time_and_only_context_message_fields(
    environment: ContextEnvironment,
) -> None:
    _history(environment, 25)
    request = ContextQuery(topic_id=FIRST_TOPIC, keyword="  Context%_  ", before_seq=19, limit=5)
    result = _query(environment, request)
    assert [message.seq for message in result.messages] == [14, 15, 16, 17, 18]
    assert result.next_before_seq == 14
    _assert_provided(environment, result)
    with environment.database.read() as session:
        record = session.get(ContextQueryRecord, result.query_id)
        assert record is not None
        assert (
            record.room_id,
            record.member_id,
            record.message_id,
            record.topic_id,
            record.keyword,
            record.before_seq,
            record.after_seq,
            record.page_limit,
        ) == (ROOM_ID, "alpha", None, FIRST_TOPIC, "Context%_", 19, None, 5)
        assert record.provided_at.tzinfo is not None
        assert _positions(result)[FIRST_TOPIC].updated_at == record.provided_at
    assert result.messages[0].created_at == OBSERVED_AT
    assert set(result.messages[0].model_dump()) == {
        "id",
        "seq",
        "sender_id",
        "sender_name",
        "content",
        "topic_ids",
        "mentioned_member_ids",
        "reply_to_message_id",
        "created_at",
    }


def test_single_lookup_preserves_current_sender_name_reply_and_relation_order(
    environment: ContextEnvironment,
) -> None:
    first = _publish(
        environment,
        topics=(SECOND_TOPIC, FIRST_TOPIC),
        targets=("alpha", "gamma"),
        sender_id="beta",
    )
    second = RoomService(environment.rooms).post_message(
        ROOM_ID,
        CreateMessage(
            publication_id=uuid4().hex,
            content="Reply",
            mentioned_member_ids=["alpha"],
            reply_to_message_id=first.id,
        ),
        member_id="beta",
    )
    RoomService(environment.rooms).update_member(
        ROOM_ID, "beta", UpdateMember(name="Renamed", topic_ids=[FIRST_TOPIC])
    )
    result = _query(environment, ContextQuery(message_id=second.id))
    assert result.messages[0].sender_name == "Renamed"
    assert result.messages[0].reply_to_message_id == first.id
    original = _query(environment, ContextQuery(message_id=first.id))
    assert original.messages[0].topic_ids == [SECOND_TOPIC, FIRST_TOPIC]
    assert original.messages[0].mentioned_member_ids == ["alpha", "gamma"]


@pytest.mark.parametrize(
    "selection",
    [
        ContextQuery(),
        ContextQuery(keyword="missing"),
        ContextQuery(after_seq=50),
        ContextQuery(before_seq=1),
    ],
)
def test_empty_context_does_not_create_query_records_or_move_positions(
    environment: ContextEnvironment, selection: ContextQuery, checked_out: set[int]
) -> None:
    if selection != ContextQuery():
        _history(environment, 10)
    before = _facts(environment)
    result = _query(environment, selection)
    assert result.query_id is None and result.messages == [] and not result.has_more
    assert result.next_before_seq is None and result.next_after_seq is None
    assert not checked_out and _facts(environment) == before


def test_positions_advance_only_for_returned_subscribed_topics_and_never_regress(
    environment: ContextEnvironment,
) -> None:
    history = _history(environment, 30)
    both = _query(environment, ContextQuery(message_id=history[9].id))
    assert {topic: value.seq for topic, value in _positions(both).items()} == {
        FIRST_TOPIC: 10,
        SECOND_TOPIC: 10,
    }
    first = _query(environment, ContextQuery(topic_id=FIRST_TOPIC, before_seq=21, limit=1))
    assert {topic: value.seq for topic, value in _positions(first).items()} == {
        FIRST_TOPIC: 20,
        SECOND_TOPIC: 10,
    }
    events = _facts(environment).events
    older = _query(environment, ContextQuery(message_id=history[9].id))
    again = _query(environment, ContextQuery(topic_id=FIRST_TOPIC, before_seq=21, limit=1))
    assert older.positions == again.positions == first.positions
    assert _facts(environment).events == events
    second = _query(environment, ContextQuery(topic_id=SECOND_TOPIC, after_seq=20))
    assert {topic: value.seq for topic, value in _positions(second).items()} == {
        FIRST_TOPIC: 20,
        SECOND_TOPIC: 30,
    }
    assert _facts(environment).events[len(events) :] == [(ROOM_ID, "position", "alpha")]
    assert (
        len({both.query_id, first.query_id, older.query_id, again.query_id, second.query_id}) == 5
    )
    before = _facts(environment)
    empty = _query(environment, ContextQuery(after_seq=30))
    assert empty.query_id is None and empty.messages == [] and empty.positions == second.positions
    assert _facts(environment) == before


def test_positions_survive_unsubscribe_resubscribe_and_reopening_without_rewriting_time(
    environment: ContextEnvironment,
) -> None:
    history = _history(environment, 12)
    latest = _query(environment, ContextQuery(topic_id=FIRST_TOPIC))
    timestamp = _positions(latest)[FIRST_TOPIC].updated_at
    _subscribe(environment, [SECOND_TOPIC])
    assert [position.topic_id for position in environment.context.positions(ROOM_ID, "alpha")] == [
        SECOND_TOPIC
    ]
    _subscribe(environment, [FIRST_TOPIC, SECOND_TOPIC])
    older = _query(environment, ContextQuery(message_id=history[0].id))
    assert _positions(older)[FIRST_TOPIC].seq == 12
    assert _positions(older)[FIRST_TOPIC].updated_at == timestamp
    reopened = Database(environment.database.path)
    try:
        context = SQLAlchemyMemberContext(reopened)
        assert context.positions(ROOM_ID, "alpha") == older.positions
        assert (
            context.query(ROOM_ID, "alpha", ContextQuery(message_id=history[0].id)).positions
            == older.positions
        )
    finally:
        reopened.close()


def test_eight_concurrent_queries_record_each_actual_result_and_keep_maximum_positions(
    environment: ContextEnvironment,
) -> None:
    history = _history(environment)
    sequences = [1, 50, 20, 65, 2, 60, 55, 40]
    barrier = Barrier(len(sequences))

    def query(sequence: int) -> ContextResult:
        barrier.wait(timeout=5)
        return _query(environment, ContextQuery(message_id=history[sequence - 1].id))

    with ThreadPoolExecutor(max_workers=8) as workers:
        results = list(workers.map(query, sequences))
    assert [result.messages[0].seq for result in results] == sequences
    assert len({result.query_id for result in results}) == len(sequences)
    for result in results:
        _assert_provided(environment, result)
    current = {
        position.topic_id: position for position in environment.context.positions(ROOM_ID, "alpha")
    }
    assert {topic: position.seq for topic, position in current.items()} == {
        FIRST_TOPIC: 65,
        SECOND_TOPIC: 60,
    }
    assert len(_facts(environment).queries) == len(_facts(environment).provided) == 8


@pytest.mark.parametrize("visibility", ["delivery", "subscription"])
def test_colliding_message_ids_in_other_rooms_cannot_grant_context_visibility(
    environment: ContextEnvironment, visibility: str
) -> None:
    _clone_other_resources(environment)
    _subscribe(environment, [] if visibility == "delivery" else [FIRST_TOPIC])
    RoomService(environment.rooms).update_member(
        "other", "alpha", UpdateMember(name="Alpha", topic_ids=[])
    )
    invisible = _publish(environment, sender_id="beta", targets=("gamma",))
    with environment.rooms.write_rooms() as repository:
        state = repository.resources("other")
        message = build_message(
            state,
            seq=1,
            content="other room",
            topic_ids=[FIRST_TOPIC] if visibility == "subscription" else [],
            mentioned_member_ids=["alpha"] if visibility == "delivery" else ["beta"],
            sender_id="user",
            sender_name="你",
            created_at=OBSERVED_AT,
        )
        message.id = invisible.id
        repository.insert_message("other", message)
    before = _facts(environment)
    with pytest.raises(RoomNotFoundError, match="查阅范围"):
        _query(environment, ContextQuery(message_id=invisible.id))
    assert _query(environment, ContextQuery()).messages == []
    assert _facts(environment) == before


def test_context_audit_and_positions_remain_scoped_to_room_with_identical_resource_ids(
    environment: ContextEnvironment,
) -> None:
    _clone_other_resources(environment)
    first = _publish(environment, topics=(FIRST_TOPIC,), content="first room")
    with environment.rooms.write_rooms() as repository:
        state = repository.resources("other")
        other = build_message(
            state,
            seq=1,
            content="other room",
            topic_ids=[SECOND_TOPIC],
            mentioned_member_ids=[],
            sender_id="user",
            sender_name="你",
            created_at=OBSERVED_AT,
        )
        other.id = first.id
        repository.insert_message("other", other)
    left = _query(environment, ContextQuery(message_id=first.id))
    right = environment.context.query("other", "alpha", ContextQuery(message_id=other.id))
    assert left.messages[0].content == "first room" and right.messages[0].content == "other room"
    assert {topic: position.seq for topic, position in _positions(left).items()} == {
        FIRST_TOPIC: 1,
        SECOND_TOPIC: 0,
    }
    assert {topic: position.seq for topic, position in _positions(right).items()} == {
        FIRST_TOPIC: 0,
        SECOND_TOPIC: 1,
    }
    _assert_provided(environment, left)
    _assert_provided(environment, right, "other")
    assert environment.context.positions(ROOM_ID, "beta")[0].seq == 0


@pytest.mark.parametrize("stage", ["query", "messages", "position", "event", "result"])
def test_failure_at_any_provision_stage_rolls_back_audit_positions_and_events(
    environment: ContextEnvironment,
    stage: str,
    monkeypatch: pytest.MonkeyPatch,
    checked_out: set[int],
) -> None:
    history = _history(environment, 10)
    before = _facts(environment)
    models = {
        "query": ContextQueryRecord,
        "messages": ContextMessageRecord,
        "position": TopicPositionRecord,
        "event": RoomEventRecord,
    }

    def fail_flush(session: Session, context: object, instances: object) -> None:
        if any(isinstance(record, models[stage]) for record in session.new):
            raise RuntimeError("provision failed")

    def fail_result(
        self: ResourceQueries, room_id: str, member_id: str | None = None
    ) -> list[TopicPosition]:
        raise RuntimeError("provision failed")

    if stage == "result":
        monkeypatch.setattr(ResourceQueries, "positions", fail_result)
    else:
        event.listen(Session, "before_flush", fail_flush)
    try:
        with pytest.raises(RuntimeError, match="provision failed"):
            _query(environment, ContextQuery(message_id=history[-1].id))
    finally:
        if stage != "result":
            event.remove(Session, "before_flush", fail_flush)
    assert not checked_out and _facts(environment) == before


def test_provided_message_constraint_failure_cannot_leave_a_query_or_position(
    environment: ContextEnvironment,
) -> None:
    history = _history(environment, 10)
    before = _facts(environment)

    def break_reference(session: Session, context: object, instances: object) -> None:
        for record in session.new:
            if isinstance(record, ContextMessageRecord):
                record.message_id = "missing"

    event.listen(Session, "before_flush", break_reference)
    try:
        with pytest.raises(IntegrityError):
            _query(environment, ContextQuery(message_id=history[-1].id))
    finally:
        event.remove(Session, "before_flush", break_reference)
    assert _facts(environment) == before


def test_borrowed_context_repository_shares_resource_transaction_and_cached_position_updates(
    environment: ContextEnvironment,
) -> None:
    history = _history(environment, 20)
    _query(environment, ContextQuery(message_id=history[9].id))
    before = _facts(environment)
    with pytest.raises(RuntimeError, match="abort owner"), environment.database.write() as session:
        resources = SQLAlchemyRoomRepository(session)
        state = resources.resources(ROOM_ID)
        original = deepcopy(state)
        state.room.name = "uncommitted"
        resources.save_resources(state, original)
        cached = session.get(TopicPositionRecord, (ROOM_ID, "alpha", FIRST_TOPIC))
        assert cached is not None and cached.seq == 10
        repository: ContextRepository = SQLAlchemyContextRepository(session)
        result = repository.query(ROOM_ID, "alpha", ContextQuery(message_id=history[-1].id))
        assert cached.seq == 20 and _positions(result)[FIRST_TOPIC].seq == 20
        assert environment.context.positions(ROOM_ID, "alpha")[0].seq == 10
        assert environment.rooms.queries.metadata(ROOM_ID).room.name == "Messages"
        raise RuntimeError("abort owner")
    assert _facts(environment) == before


def test_context_commit_failure_cannot_return_success_or_leave_provision_records(
    environment: ContextEnvironment, checked_out: set[int]
) -> None:
    _history(environment, 10)
    before = _facts(environment)

    def fail_commit(connection: Connection) -> None:
        raise RuntimeError("commit failed")

    event.listen(environment.database.engine, "commit", fail_commit)
    try:
        with pytest.raises(RuntimeError, match="commit failed"):
            _query(environment, ContextQuery())
    finally:
        event.remove(environment.database.engine, "commit", fail_commit)
    assert not checked_out and _facts(environment) == before


@pytest.mark.parametrize("limit", [1, 25])
def test_context_message_relations_are_loaded_in_batches_and_deliveries_are_not_materialized(
    environment: ContextEnvironment, limit: int
) -> None:
    _history(environment, 25)
    selected: list[str] = []

    def select_statement(
        connection: Connection,
        cursor: object,
        statement: str,
        parameters: object,
        context: ExecutionContext,
        executemany: bool,
    ) -> None:
        if statement.lstrip().upper().startswith("SELECT"):
            selected.append(statement)

    event.listen(environment.database.engine, "before_cursor_execute", select_statement)
    try:
        result = _query(environment, ContextQuery(topic_id=FIRST_TOPIC, limit=limit))
    finally:
        event.remove(environment.database.engine, "before_cursor_execute", select_statement)
    assert len(result.messages) == limit
    assert len(selected) == 8
    assert not any(statement.lstrip().startswith("SELECT deliveries.") for statement in selected)
