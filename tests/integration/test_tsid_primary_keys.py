import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import IntegrityError
from tsidpy import TSID, tsid

from conflua.application.dto.members import CreateMember, SessionInfo
from conflua.application.dto.messages import CreateMessage
from conflua.application.dto.rooms import CreateRoom
from conflua.application.members.service import MemberService
from conflua.application.members.sessions import SessionDriver
from conflua.application.messages.service import MessageService
from conflua.application.rooms.service import RoomService
from conflua.domain.identifiers import TsidSource, is_tsid, new_tsid
from conflua.domain.rooms import rules
from conflua.infrastructure.persistence.database import Database
from conflua.infrastructure.persistence.room_store import SQLAlchemyRoomStore

pytestmark = pytest.mark.integration


def test_threaded_tsid_batch_as_sqlite_primary_and_foreign_keys() -> None:
    workers = 4
    start = Barrier(workers)

    def issue_batch() -> list[str]:
        start.wait(timeout=10)
        return [new_tsid() for _ in range(1024)]

    with ThreadPoolExecutor(max_workers=workers) as pool:
        batches = [pool.submit(issue_batch) for _ in range(workers)]
        ids = [identifier for batch in batches for identifier in batch.result()]
    assert all(is_tsid(identifier) for identifier in ids)

    with closing(sqlite3.connect(":memory:")) as db:
        db.executescript("""
            PRAGMA foreign_keys = ON;
            CREATE TEMP TABLE tsid_keys (id TEXT NOT NULL PRIMARY KEY);
            CREATE TEMP TABLE tsid_links (
                id TEXT NOT NULL PRIMARY KEY REFERENCES tsid_keys(id)
            );
        """)
        rows = [(identifier,) for identifier in ids]
        db.executemany("INSERT INTO tsid_keys VALUES (?)", rows)
        db.executemany("INSERT INTO tsid_links VALUES (?)", rows)
        stored = db.execute("SELECT id, typeof(id) FROM tsid_links ORDER BY id").fetchall()
        assert stored == [(identifier, "text") for identifier in sorted(ids, key=_tsid_number)]

        with pytest.raises(sqlite3.IntegrityError) as duplicate:
            db.execute("INSERT INTO tsid_keys VALUES (?)", rows[0])
        assert duplicate.value.sqlite_errorcode == sqlite3.SQLITE_CONSTRAINT_PRIMARYKEY

        with pytest.raises(sqlite3.IntegrityError) as missing_parent:
            db.execute("INSERT INTO tsid_links VALUES (?)", (new_tsid(),))
        assert missing_parent.value.sqlite_errorcode == sqlite3.SQLITE_CONSTRAINT_FOREIGNKEY


def _tsid_number(value: str) -> int:
    return TSID.from_string(value).number


def test_independent_generators_need_distinct_nodes(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = SimpleNamespace(seconds=1_800_000_000.0)
    monkeypatch.setattr(tsid, "time", SimpleNamespace(time=lambda: clock.seconds))

    def issue_at_frozen_time(source: TsidSource) -> list[str]:
        # Two counter cycles guarantee a shared full millisecond for same-node sources.
        return [source.next() for _ in range(2 * 4096)]

    source = TsidSource(node=0)
    first = issue_at_frozen_time(source)
    same_node = issue_at_frozen_time(TsidSource(node=0))
    other_node = issue_at_frozen_time(TsidSource(node=1))
    for batch in (first, same_node, other_node):
        assert batch == sorted(set(batch))
    assert len(set(first).intersection(same_node)) >= 4096
    assert set(first).isdisjoint(other_node)

    clock.seconds -= 3600
    assert source.next() > first[-1]


@pytest.mark.parametrize("collision_table", ["messages", "deliveries"])
def test_publication_rolls_back_on_tsid_primary_key_collision(
    database: Database,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    collision_table: str,
) -> None:
    store = SQLAlchemyRoomStore(database)
    room = RoomService(store).create_room(CreateRoom(name="TSID", workspace_path=str(tmp_path)))
    topic = store.queries.metadata(room.id).topics[0]
    driver = Mock(spec=SessionDriver)
    driver.inspect.return_value = SessionInfo(
        id="test-session", provider="codex", name="Test agent", status="idle"
    )
    MemberService(store, driver).add(
        room.id, CreateMember(name="Test agent", session_id="test-session", topic_ids=[topic.id])
    )

    service = MessageService(store)
    initial = CreateMessage(publication_id="first", content="First", topic_ids=[topic.id])
    first = service.post_message(room.id, initial)
    (delivery,) = first.deliveries
    assert is_tsid(first.id) and is_tsid(delivery.id)
    assert service.post_message(room.id, initial).id == first.id
    before = store.queries.events(room.id, 0)

    followup = CreateMessage(
        publication_id="second",
        content="Second",
        topic_ids=[topic.id],
        reply_to_message_id=first.id,
    )
    issued = [first.id, new_tsid()] if collision_table == "messages" else [new_tsid(), delivery.id]
    with monkeypatch.context() as patch:
        patch.setattr(rules, "new_tsid", Mock(side_effect=issued))
        with pytest.raises(IntegrityError) as collision:
            service.post_message(room.id, followup)
    cause = collision.value.orig
    assert isinstance(cause, sqlite3.IntegrityError)
    assert cause.sqlite_errorcode == sqlite3.SQLITE_CONSTRAINT_PRIMARYKEY
    assert f"{collision_table}.id" in str(cause)

    (saved,) = store.queries.page(room.id).messages
    assert saved.id == first.id and saved.content == initial.content
    assert [item.id for item in saved.deliveries] == [delivery.id]
    assert store.queries.events(room.id, 0) == before

    # Put the next message before the first in TSID order, but after it in business order.
    with monkeypatch.context() as patch:
        patch.setattr(rules, "new_tsid", Mock(side_effect=["0000000000000", new_tsid()]))
        second = service.post_message(room.id, followup)
    assert second.id < first.id and second.seq == first.seq + 1
    assert [item.id for item in store.queries.page(room.id).messages] == [first.id, second.id]
    earlier = store.queries.page(room.id, before_seq=second.seq, limit=1)
    assert [item.id for item in earlier.messages] == [first.id]
