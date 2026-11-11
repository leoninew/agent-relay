from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from support.databases import MemoryDatabases
from support.session_fixtures import FakeSessionDriver
from support.sqlalchemy_message_fixtures import (
    FIRST_TOPIC,
    ROOM_ID,
    SECOND_TOPIC,
    MessageTestStore,
    seed_message_store,
)

from agent_relay.application.members.contracts import UpdateMember
from agent_relay.application.members.service import MemberService
from agent_relay.application.messages.contracts import CreateMessage
from agent_relay.application.messages.service import MessageService
from agent_relay.domain.rooms.errors import RoomConflictError, RoomNotFoundError
from agent_relay.domain.rooms.models import Message
from agent_relay.domain.rooms.rules import build_message
from agent_relay.infrastructure.persistence.repositories.messages import SQLAlchemyMessageRepository
from agent_relay.infrastructure.persistence.repositories.rooms import SQLAlchemyRoomRepository


@pytest.fixture
def store(tmp_path: Path, databases: MemoryDatabases) -> MessageTestStore:
    return seed_message_store(databases.create(tmp_path / "messages.sqlite3"))


def publish(store: MessageTestStore, content: str = "Message", **fields: object) -> Message:
    request = CreateMessage.model_validate(
        {"publication_id": uuid4().hex, "content": content, "topic_ids": [FIRST_TOPIC], **fields}
    )
    return MessageService(store).post_message(ROOM_ID, request)


def test_message_round_trip_preserves_routes_reply_and_events(store: MessageTestStore) -> None:
    parent = publish(store)
    cursor = store.queries.metadata(ROOM_ID).event_id
    message = publish(
        store,
        "Reply",
        topic_ids=[SECOND_TOPIC, FIRST_TOPIC],
        mentioned_member_ids=["gamma", "alpha"],
        reply_to_message_id=parent.id,
    )
    assert store.queries.message(ROOM_ID, message.id) == message
    assert MessageService(store).publication(ROOM_ID, message.publication_id or "") == message
    assert [
        (event.kind, event.entity_id) for event in store.queries.events(ROOM_ID, cursor).events
    ] == [
        ("message", message.id),
        *[("delivery", delivery.id) for delivery in message.deliveries],
    ]
    with pytest.raises(RoomNotFoundError):
        store.queries.message("other", message.id)


def test_replay_keeps_saved_targets_and_uses_current_sender_name(store: MessageTestStore) -> None:
    service = MessageService(store)
    request = CreateMessage(publication_id="replay", content="Saved", topic_ids=[FIRST_TOPIC])
    original = service.post_message(ROOM_ID, request, member_id="alpha")
    members = MemberService(store, FakeSessionDriver())
    members.update_member(ROOM_ID, "alpha", UpdateMember(name="Renamed", topic_ids=[SECOND_TOPIC]))
    members.update_member(ROOM_ID, "beta", UpdateMember(name="Beta", topic_ids=[SECOND_TOPIC]))
    replay = service.post_message(ROOM_ID, request, member_id="alpha")
    assert replay.id == original.id and replay.sender_name == "Renamed"
    assert replay.recipient_ids == original.recipient_ids
    assert replay.deliveries == original.deliveries
    assert store.queries.metadata(ROOM_ID).summary.total_messages == 1


def test_concurrent_publications_allocate_unique_sequences(store: MessageTestStore) -> None:
    def send(index: int) -> int:
        return publish(store, f"Message {index}").seq

    with ThreadPoolExecutor(max_workers=2) as workers:
        assert sorted(workers.map(send, range(4))) == [1, 2, 3, 4]
    assert store.queries.metadata(ROOM_ID).summary.total_messages == 4


def test_concurrent_replays_save_one_publication(store: MessageTestStore) -> None:
    def send(index: int) -> str:
        try:
            return publish(store, f"Content {index % 2}", publication_id="same").id
        except RoomConflictError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(send, range(4)))
    saved = store.queries.page(ROOM_ID).messages
    assert len(saved) == 1 and results.count(saved[0].id) == results.count("conflict") == 2


def test_filters_apply_before_keyset_pagination_and_keep_global_totals(
    store: MessageTestStore,
) -> None:
    first = publish(store, "Needle%_ first")
    publish(store, "Needle%_ other topic", topic_ids=[SECOND_TOPIC])
    third = publish(store, "Needle%_ cross", topic_ids=[FIRST_TOPIC, SECOND_TOPIC])
    publish(store, "Needle without special characters")
    page = store.queries.snapshot(
        ROOM_ID, FIRST_TOPIC, member_id="beta", keyword="Needle%_", limit=1
    )
    assert page.messages == [third] and page.has_more and page.next_before_seq == third.seq
    assert page.summary.total_messages == 4
    older = store.queries.page(
        ROOM_ID,
        topic_id=FIRST_TOPIC,
        member_id="beta",
        keyword="Needle%_",
        before_seq=page.next_before_seq,
        limit=1,
    )
    assert older.messages == [first] and not older.has_more and older.has_newer
    assert store.queries.page(ROOM_ID, keyword="needle%_").messages == []


def test_queue_clear_covers_the_scope_and_preserves_history(store: MessageTestStore) -> None:
    selected = [publish(store) for _ in range(3)]
    other = publish(store, topic_ids=[SECOND_TOPIC])
    page = store.queries.queue(ROOM_ID, topic_id=FIRST_TOPIC, limit=1)
    assert page.total_messages == 3 and page.has_more
    result = MessageService(store).clear_queue(ROOM_ID, topic_id=FIRST_TOPIC)
    assert result.removed_messages == 3
    assert store.queries.queue(ROOM_ID).messages == [other]
    for message in selected:
        saved = store.queries.message(ROOM_ID, message.id)
        assert saved.content == message.content
        assert all(delivery.deleted_at is not None for delivery in saved.deliveries)


def test_invalid_delivery_rolls_back_resources_message_and_events(store: MessageTestStore) -> None:
    before = store.queries.snapshot(ROOM_ID)
    with pytest.raises(IntegrityError), store.database.write() as session:
        resources = SQLAlchemyRoomRepository(session)
        state = resources.resources(ROOM_ID)
        original = deepcopy(state)
        state.room.name = "Uncommitted"
        resources.save_resources(state, original)
        message = build_message(
            state,
            content="Invalid delivery",
            topic_ids=[FIRST_TOPIC],
            mentioned_member_ids=[],
            sender_id="user",
            sender_name="你",
            created_at=datetime.now(UTC),
            seq=1,
        )
        message.deliveries[0].target_session_id = "missing"
        SQLAlchemyMessageRepository(session).insert_message(ROOM_ID, message)
    assert store.queries.snapshot(ROOM_ID) == before
