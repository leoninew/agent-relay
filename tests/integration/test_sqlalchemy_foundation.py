import asyncio
import re
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from threading import Barrier
from typing import cast

import pytest
from sqlalchemy import CheckConstraint, UniqueConstraint, event, func, inspect, select
from sqlalchemy.engine import Connection, ExecutionContext
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import QueuePool
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from agent_relay.infrastructure.persistence.database import Database
from agent_relay.infrastructure.persistence.mappers import delivery_from_model, delivery_to_model
from agent_relay.infrastructure.persistence.migrations import run_migrations
from agent_relay.infrastructure.persistence.models import (
    Base,
    DeliveryRecord,
    MemberRecord,
    MessageRecord,
    RoomEventRecord,
    RoomRecord,
    SessionRecord,
    TopicRecord,
)
from agent_relay.infrastructure.persistence.sqlite import (
    create_sqlite_engine,
    insertion_order,
    time_at_or_before,
)
from agent_relay.infrastructure.persistence.transaction import SQLAlchemyTransaction
from agent_relay.interfaces.http.middleware import RequestTransactionMiddleware

pytestmark = pytest.mark.integration


@pytest.fixture
def database(tmp_path: Path) -> Iterator[Database]:
    path = tmp_path / "foundation.sqlite3"
    run_migrations(path)
    database = Database(path)
    try:
        yield database
    finally:
        database.close()


def _checked_out(database: Database) -> int:
    assert isinstance(database.engine.pool, QueuePool)
    return database.engine.pool.checkedout()


def _insert_room(session: Session, room_id: str = "room") -> None:
    session.add(RoomRecord(id=room_id, project_path=f"D:/{room_id}", name=room_id, description=""))
    session.flush()


def _insert_event(session: Session, room_id: str = "room") -> None:
    session.add(RoomEventRecord(room_id=room_id, kind="room", entity_id=room_id))
    session.flush()


def _rooms(database: Database) -> list[str]:
    with database.read() as session:
        return list(session.scalars(select(RoomRecord.id).order_by(insertion_order("rooms"))))


def _seed_messages(database: Database) -> None:
    with database.write() as session:
        _insert_room(session)
        session.add(
            MemberRecord(
                room_id="room",
                id="user",
                name="你",
                kind="human",
                session_id=None,
                initials="你",
                presence="available",
                activity="",
                activity_source="unknown",
            )
        )
        session.add(
            SessionRecord(
                room_id="room",
                id="session",
                name="Session",
                provider="codex",
                project_path="D:/room",
                presence="available",
            )
        )
        session.flush()
        session.add(
            MemberRecord(
                room_id="room",
                id="agent",
                name="Agent",
                kind="agent",
                session_id="session",
                initials="A",
                presence="available",
                activity="",
                activity_source="unknown",
            )
        )
        session.flush()


def test_mapping_matches_the_migrated_schema(database: Database) -> None:
    schema = inspect(database.engine)
    assert set(schema.get_table_names()) - {"alembic_version"} == set(Base.metadata.tables)
    assert len(Base.metadata.tables) == 14
    for name, mapped in Base.metadata.tables.items():
        columns = schema.get_columns(name)
        assert {column["name"] for column in columns} == set(mapped.c.keys())
        for column in columns:
            assert str(column["type"]) == str(mapped.c[column["name"]].type)
        assert schema.get_pk_constraint(name)["constrained_columns"] == [
            column.name for column in mapped.primary_key.columns
        ]
        actual_foreign_keys = {
            (
                tuple(key["constrained_columns"]),
                key["referred_table"],
                tuple(key["referred_columns"]),
            )
            for key in schema.get_foreign_keys(name)
        }
        mapped_foreign_keys = {
            (
                tuple(key.column_keys),
                key.referred_table.name,
                tuple(element.column.name for element in key.elements),
            )
            for key in mapped.foreign_key_constraints
        }
        assert actual_foreign_keys == mapped_foreign_keys
        assert {
            tuple(constraint["column_names"]) for constraint in schema.get_unique_constraints(name)
        } == {
            tuple(column.name for column in constraint.columns)
            for constraint in mapped.constraints
            if isinstance(constraint, UniqueConstraint)
        }
        assert {
            _normalize_sql(constraint["sqltext"])
            for constraint in schema.get_check_constraints(name)
        } == {
            _normalize_sql(str(constraint.sqltext))
            for constraint in mapped.constraints
            if isinstance(constraint, CheckConstraint)
        }
        for index in schema.get_indexes(name):
            mapped_index = next(item for item in mapped.indexes if item.name == index["name"])
            assert _normalize_sql(str(index["dialect_options"].get("sqlite_where"))) == (
                _normalize_sql(str(mapped_index.dialect_options["sqlite"]["where"])).replace(
                    f"{name}.", ""
                )
            )
        actual_indexes = {
            index["name"]: (tuple(index["column_names"]), bool(index["unique"]))
            for index in schema.get_indexes(name)
        }
        assert actual_indexes == {
            index.name: (tuple(column.name for column in index.columns), index.unique)
            for index in mapped.indexes
        }


def test_sessions_are_lazy_short_and_share_only_after_the_first_write(database: Database) -> None:
    transaction = database.request_transaction()
    assert transaction.session is None
    assert _checked_out(database) == 0
    with database.read(transaction) as first_read:
        assert transaction.session is None
        assert first_read.scalar(select(func.count()).select_from(RoomRecord)) == 0
    assert _checked_out(database) == 0
    with database.write(transaction) as writer:
        _insert_room(writer)
    assert transaction.session is writer
    assert _rooms(database) == []
    with database.read(transaction) as borrowed:
        assert borrowed is writer
        assert borrowed.get(RoomRecord, "room") is not None
    with database.write(transaction) as second_writer:
        assert second_writer is writer
        _insert_event(second_writer)
    transaction.finish(commit=True)
    transaction.finish(commit=False)
    assert transaction.session is None
    assert _checked_out(database) == 0
    assert _rooms(database) == ["room"]
    with pytest.raises(RuntimeError, match="finished"), database.read(transaction):
        pass
    with pytest.raises(RuntimeError, match="finished"), database.write(transaction):
        pass


def test_sqlite_begins_the_write_lock_before_the_first_statement(database: Database) -> None:
    statements: list[str] = []

    def record_statement(
        connection: Connection,
        cursor: object,
        statement: str,
        parameters: object,
        context: ExecutionContext,
        executemany: bool,
    ) -> None:
        statements.append(statement)

    event.listen(database.engine, "before_cursor_execute", record_statement)
    with database.read() as reader:
        reader.scalar(select(func.count()).select_from(RoomRecord))
    assert statements[0] == "BEGIN"
    statements.clear()
    with database.write() as writer:
        assert statements == ["BEGIN IMMEDIATE"]
        _insert_room(writer)
    assert _checked_out(database) == 0


def test_background_failure_rolls_back_data_and_events(database: Database) -> None:
    with pytest.raises(RuntimeError, match="stop"), database.write() as session:
        _insert_room(session)
        _insert_event(session)
        raise RuntimeError("stop")
    assert _rooms(database) == []
    with database.read() as session:
        assert session.scalar(select(func.count()).select_from(RoomEventRecord)) == 0
    assert _checked_out(database) == 0


@pytest.mark.parametrize("status", [201, 400, 500])
def test_http_finishes_shared_writes_before_starting_response(
    database: Database, status: int
) -> None:
    sent: list[Message] = []

    async def application(scope: Scope, receive: Receive, send: Send) -> None:
        transaction = cast(SQLAlchemyTransaction, scope["state"]["database_transaction"])
        with database.write(transaction) as session:
            _insert_room(session)
        with database.write(transaction) as session:
            _insert_event(session)
        assert _rooms(database) == []
        await send({"type": "http.response.start", "status": status, "headers": []})
        await send({"type": "http.response.body", "body": b"done"})

    async def send(message: Message) -> None:
        if message["type"] == "http.response.start":
            assert _rooms(database) == (["room"] if status < 400 else [])
        sent.append(message)

    asyncio.run(_invoke(database, application, send))
    assert len(sent) == 2
    with database.read() as session:
        assert session.scalar(select(func.count()).select_from(RoomEventRecord)) == int(
            status < 400
        )
    assert _checked_out(database) == 0


async def _invoke(database: Database, application: ASGIApp, send: Send) -> None:
    async def receive() -> Message:
        return {"type": "http.disconnect"}

    middleware = RequestTransactionMiddleware(
        application,
        transaction_factory=database.request_transaction,
    )
    await middleware({"type": "http", "path": "/", "method": "POST"}, receive, send)


@pytest.mark.parametrize("failure", [RuntimeError, asyncio.CancelledError])
def test_http_exception_and_cancellation_release_the_session(
    database: Database,
    failure: type[BaseException],
) -> None:
    async def application(scope: Scope, receive: Receive, send: Send) -> None:
        with database.write(scope["state"]["database_transaction"]) as session:
            _insert_room(session)
            _insert_event(session)
        raise failure("abort")

    async def send(message: Message) -> None:
        pytest.fail("Response must not start")

    with pytest.raises(failure, match="abort"):
        asyncio.run(_invoke(database, application, send))
    assert _rooms(database) == []
    assert _checked_out(database) == 0


def test_commit_failure_rolls_back_and_cannot_emit_success(database: Database) -> None:
    def fail_commit(session: Session) -> None:
        raise RuntimeError("commit failed")

    async def application(scope: Scope, receive: Receive, send: Send) -> None:
        with database.write(scope["state"]["database_transaction"]) as session:
            _insert_room(session)
            _insert_event(session)
            event.listen(session, "before_commit", fail_commit)
        await send({"type": "http.response.start", "status": 201, "headers": []})

    async def send(message: Message) -> None:
        pytest.fail("Commit failure must prevent the success response")

    with pytest.raises(RuntimeError, match="commit failed"):
        asyncio.run(_invoke(database, application, send))
    assert _rooms(database) == []
    assert _checked_out(database) == 0


def test_websocket_wait_does_not_create_a_request_transaction(database: Database) -> None:
    factories: list[bool] = []

    def transaction_factory() -> SQLAlchemyTransaction:
        factories.append(True)
        return database.request_transaction()

    async def application(scope: Scope, receive: Receive, send: Send) -> None:
        assert "database_transaction" not in scope.get("state", {})
        assert _checked_out(database) == 0

    async def receive() -> Message:
        return {"type": "websocket.disconnect", "code": 1000}

    async def send(message: Message) -> None:
        pass

    middleware = RequestTransactionMiddleware(application, transaction_factory=transaction_factory)
    asyncio.run(middleware({"type": "websocket"}, receive, send))
    assert factories == []


def test_request_session_can_be_finished_in_a_different_worker(database: Database) -> None:
    transaction = database.request_transaction()

    def write() -> None:
        with database.write(transaction) as session:
            _insert_room(session)
            _insert_event(session)

    with ThreadPoolExecutor(max_workers=1) as first_worker:
        first_worker.submit(write).result(timeout=5)
        with ThreadPoolExecutor(max_workers=1) as second_worker:
            second_worker.submit(transaction.finish, commit=True).result(timeout=5)
    assert _rooms(database) == ["room"]
    assert _checked_out(database) == 0


def test_independent_parallel_writers_serialize_sequence_checks(database: Database) -> None:
    _seed_messages(database)
    barrier = Barrier(2)
    sessions: list[Session] = []

    def publish() -> int:
        barrier.wait(timeout=5)
        with database.write() as session:
            sessions.append(session)
            maximum = (
                session.scalar(
                    select(func.max(MessageRecord.seq)).where(
                        MessageRecord.room_id == "room",
                    )
                )
                or 0
            )
            sequence = maximum + 1
            session.add(
                MessageRecord(
                    room_id="room",
                    id=f"message-{sequence}",
                    seq=sequence,
                    publisher_id="user",
                    content="message",
                    created_at=datetime.fromisoformat("2026-11-11T12:00:00+08:00"),
                )
            )
            session.flush()
            return sequence

    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [workers.submit(publish) for attempt in range(2)]
        assert sorted(future.result(timeout=10) for future in futures) == [1, 2]
    assert sessions[0] is not sessions[1]
    assert _checked_out(database) == 0


def test_foreign_keys_apply_to_every_new_connection(database: Database) -> None:
    with database.read() as occupied, pytest.raises(IntegrityError), database.write() as writer:
        assert occupied is not writer
        writer.add(TopicRecord(room_id="missing", id="topic", name="Topic", description=""))
        writer.flush()
    assert _checked_out(database) == 0


@pytest.mark.parametrize(
    "historical_time",
    [
        "2026-11-11T12:34:56.123456+08:00",
        "2026-11-11T04:34:56.000001+00:00",
        "2026-11-10T21:34:56.120000-07:00",
        "2026-11-11T04:34:56Z",
    ],
)
def test_current_head_historical_time_and_receipt_formats_round_trip(
    database: Database,
    historical_time: str,
) -> None:
    _seed_messages(database)
    with database.write() as session:
        connection = session.connection()
        connection.exec_driver_sql(
            "INSERT INTO messages(room_id,id,seq,publisher_id,content,created_at) "
            "VALUES ('room','message',1,'user','历史消息',?)",
            (historical_time,),
        )
        connection.exec_driver_sql(
            "INSERT INTO deliveries(room_id,id,message_id,target_member_id,target_session_id,"
            "client_message_id,status,updated_at,queued_at,queued_submission_id,receipt_metadata) "
            "VALUES ('room','delivery','message','agent','session','client','queued',?,?,"
            "'queued',?)",
            (historical_time, historical_time, '{"accepted":true,"详情":{"次数":1}}'),
        )
    with database.read() as session:
        record = session.get(DeliveryRecord, ("room", "delivery"))
        message = session.get(MessageRecord, ("room", "message"))
        assert record is not None and message is not None
        delivery = delivery_from_model(record)
        expected = datetime.fromisoformat(historical_time)
        assert message.created_at.isoformat() == expected.isoformat()
        assert delivery.updated_at.isoformat() == expected.isoformat()
        assert delivery.queued_at is not None
        assert delivery.queued_at.isoformat() == expected.isoformat()
        assert delivery.received_at is None
        assert delivery.deleted_at is None
        assert delivery.receipt == {
            "id": "queued",
            "clientUserMessageId": "client",
            "accepted": True,
            "详情": {"次数": 1},
        }
    delivery.updated_at += timedelta(microseconds=1)
    with database.write() as session:
        session.merge(delivery_to_model("room", "message", delivery))
    with database.read() as session:
        row = (
            session.connection()
            .exec_driver_sql(
                "SELECT updated_at, received_at, receipt_metadata FROM deliveries",
            )
            .one()
        )
        assert row[0] == delivery.updated_at.isoformat()
        assert row[1] is None
        assert '"id"' not in row[2] and '"clientUserMessageId"' not in row[2]
        record = session.get(DeliveryRecord, ("room", "delivery"))
        assert record is not None
        assert delivery_from_model(record) == delivery


def test_database_rejects_missing_unmigrated_and_wrong_revision(tmp_path: Path) -> None:
    missing = tmp_path / "missing.sqlite3"
    with pytest.raises(RuntimeError, match="missing"):
        Database(missing)
    assert not missing.exists()
    engine = create_sqlite_engine(missing)
    with engine.connect():
        pass
    engine.dispose()
    with pytest.raises(RuntimeError, match="not migrated"):
        Database(missing)
    run_migrations(missing)
    engine = create_sqlite_engine(missing)
    with engine.begin() as connection:
        connection.exec_driver_sql("UPDATE alembic_version SET version_num = 'wrong'")
    engine.dispose()
    with pytest.raises(RuntimeError, match="expected"):
        Database(missing)


def _normalize_sql(expression: str) -> str:
    return re.sub(r"[\s()]", "", expression)


def test_failed_begin_releases_its_session_and_can_be_retried(database: Database) -> None:
    attempts: list[bool] = []

    def fail_first_begin(
        connection: Connection,
        cursor: object,
        statement: str,
        parameters: object,
        context: ExecutionContext,
        executemany: bool,
    ) -> None:
        if statement == "BEGIN IMMEDIATE" and not attempts:
            attempts.append(True)
            raise RuntimeError("begin failed")

    event.listen(database.engine, "before_cursor_execute", fail_first_begin)
    transaction = database.request_transaction()
    with pytest.raises(RuntimeError, match="begin failed"), database.write(transaction):
        pass
    assert transaction.session is None
    assert _checked_out(database) == 0
    with database.write(transaction) as session:
        _insert_room(session)
    transaction.finish(commit=True)
    assert _rooms(database) == ["room"]
    assert _checked_out(database) == 0


@pytest.mark.parametrize(
    ("observed_at", "eligible"),
    [
        ("2026-11-11T12:00:29.123000+08:00", True),
        ("2026-11-11T12:00:30.123000+08:00", True),
        ("2026-11-11T12:00:31.123000+08:00", False),
        ("2026-11-11T04:00:30.123000+00:00", True),
        ("2026-11-10T21:00:30.123000-07:00", True),
        ("2026-11-11T04:00:29.123000+00:00", True),
        ("2026-11-11T04:00:31.123000+00:00", False),
        (None, None),
    ],
)
def test_observation_checkpoint_includes_equal_instants_across_timezones(
    database: Database,
    observed_at: str | None,
    eligible: bool | None,
) -> None:
    cutoff = datetime.fromisoformat("2026-11-11T12:00:30.123000+08:00")
    with database.write() as session:
        _insert_room(session)
        session.add(
            SessionRecord(
                room_id="room",
                id="session",
                name="Session",
                provider="codex",
                project_path="D:/room",
                presence="available",
                observed_at=datetime.fromisoformat(observed_at)
                if observed_at is not None
                else None,
            )
        )
    with database.read() as session:
        result = session.scalar(select(time_at_or_before(SessionRecord.observed_at, cutoff)))
    assert result is eligible
