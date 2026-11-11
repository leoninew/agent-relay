from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from support.context_fixtures import ContextWorkflow
from support.databases import MemoryDatabases
from support.session_fixtures import FakeSessionDriver
from support.sqlalchemy_message_fixtures import (
    FIRST_TOPIC,
    ROOM_ID,
    SECOND_TOPIC,
    MessageTestStore,
    seed_message_store,
)

from agent_relay.application.context.contracts import ContextQuery
from agent_relay.application.members.contracts import UpdateMember
from agent_relay.application.members.service import MemberService
from agent_relay.application.messages.contracts import CreateMessage
from agent_relay.application.messages.service import MessageService
from agent_relay.application.rooms.service import RoomService
from agent_relay.domain.rooms.errors import RoomNotFoundError
from agent_relay.domain.rooms.models import Message
from agent_relay.infrastructure.persistence.models import ContextMessageRecord, ContextQueryRecord


@pytest.fixture
def store(tmp_path: Path, databases: MemoryDatabases) -> MessageTestStore:
    return seed_message_store(databases.create(tmp_path / "context.sqlite3"))


@pytest.fixture
def context(store: MessageTestStore) -> ContextWorkflow:
    return ContextWorkflow(store.database)


def subscribe(store: MessageTestStore, topics: list[str]) -> None:
    MemberService(store, FakeSessionDriver()).update_member(
        ROOM_ID, "alpha", UpdateMember(name="Alpha", topic_ids=topics)
    )


def publish(
    store: MessageTestStore, *, topics: list[str], targets: list[str], sender: str = "user"
) -> Message:
    return MessageService(store).post_message(
        ROOM_ID,
        CreateMessage(
            publication_id=uuid4().hex,
            content="Context",
            topic_ids=topics,
            mentioned_member_ids=targets,
        ),
        member_id=sender,
    )


def test_visibility_uses_own_publications_deliveries_and_current_subscriptions(
    store: MessageTestStore, context: ContextWorkflow
) -> None:
    subscribe(store, [])
    own = publish(store, topics=[], targets=["beta"], sender="alpha")
    direct = publish(store, topics=[], targets=["alpha"], sender="beta")
    subscribed = publish(store, topics=[FIRST_TOPIC], targets=[])
    hidden = publish(store, topics=[SECOND_TOPIC], targets=[])
    subscribe(store, [FIRST_TOPIC])
    result = context.provide(ROOM_ID, "alpha", ContextQuery())
    assert [message.id for message in result.messages] == [own.id, direct.id, subscribed.id]
    with pytest.raises(RoomNotFoundError, match="查阅范围"):
        context.provide(ROOM_ID, "alpha", ContextQuery(message_id=hidden.id))


def test_saved_human_recipient_does_not_grant_delivery_visibility(
    store: MessageTestStore, context: ContextWorkflow
) -> None:
    message = publish(store, topics=[], targets=["user"], sender="beta")
    assert store.queries.message(ROOM_ID, message.id).recipient_ids == ["user"]
    assert context.provide(ROOM_ID, "user", ContextQuery()).messages == []


@pytest.mark.parametrize("forward", [False, True])
def test_pagination_records_only_returned_messages_and_not_the_lookahead(
    store: MessageTestStore, context: ContextWorkflow, forward: bool
) -> None:
    history = [publish(store, topics=[FIRST_TOPIC], targets=[]) for _ in range(6)]
    request = ContextQuery(limit=2, after_seq=0) if forward else ContextQuery(limit=2)
    result = context.provide(ROOM_ID, "alpha", request)
    expected = history[:2] if forward else history[-2:]
    assert [message.id for message in result.messages] == [message.id for message in expected]
    assert result.has_more
    assert (result.next_after_seq if forward else result.next_before_seq) == (
        expected[-1].seq if forward else expected[0].seq
    )
    with store.database.read() as session:
        assert list(
            session.scalars(
                select(ContextMessageRecord.message_id)
                .where(ContextMessageRecord.query_id == result.query_id)
                .order_by(ContextMessageRecord.position)
            )
        ) == [message.id for message in expected]
    positions = {position.topic_id: position.seq for position in result.positions}
    assert positions[FIRST_TOPIC] == expected[-1].seq
    assert positions[SECOND_TOPIC] == 0


def test_deleted_topic_removes_subscription_visibility_but_keeps_direct_history(
    store: MessageTestStore, context: ContextWorkflow
) -> None:
    subscribe(store, [])
    subscribed = publish(store, topics=[FIRST_TOPIC], targets=[])
    direct = publish(store, topics=[FIRST_TOPIC], targets=["alpha"], sender="beta")
    subscribe(store, [FIRST_TOPIC])
    assert len(context.provide(ROOM_ID, "alpha", ContextQuery()).messages) == 2
    RoomService(store).delete_topic(ROOM_ID, FIRST_TOPIC)
    result = context.provide(ROOM_ID, "alpha", ContextQuery())
    assert [message.id for message in result.messages] == [direct.id]
    with pytest.raises(RoomNotFoundError):
        context.provide(ROOM_ID, "alpha", ContextQuery(message_id=subscribed.id))


def test_concurrent_provisions_and_older_reads_keep_the_maximum_position(
    store: MessageTestStore, context: ContextWorkflow
) -> None:
    history = [publish(store, topics=[FIRST_TOPIC], targets=[]) for _ in range(6)]

    def provide(message_id: str) -> None:
        context.provide(ROOM_ID, "alpha", ContextQuery(message_id=message_id))

    with ThreadPoolExecutor(max_workers=2) as workers:
        list(workers.map(provide, [history[-1].id, history[1].id]))
    provide(history[0].id)
    positions = {
        position.topic_id: position.seq for position in context.positions(ROOM_ID, "alpha")
    }
    assert positions[FIRST_TOPIC] == 6


def test_provision_audit_positions_and_events_roll_back_with_the_owner(
    store: MessageTestStore,
) -> None:
    message = publish(store, topics=[FIRST_TOPIC], targets=[])
    before = store.queries.metadata(ROOM_ID)
    with pytest.raises(RuntimeError, match="abort"), store.database.write() as session:
        result = ContextWorkflow(session).provide(
            ROOM_ID, "alpha", ContextQuery(message_id=message.id)
        )
        assert result.query_id is not None
        raise RuntimeError("abort")
    assert store.queries.metadata(ROOM_ID) == before
    with store.database.read() as session:
        assert session.scalar(select(func.count()).select_from(ContextQueryRecord)) == 0
        assert session.scalar(select(func.count()).select_from(ContextMessageRecord)) == 0
