from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import inspect, literal, select
from sqlalchemy.exc import IntegrityError
from support.databases import MemoryDatabases, assert_reader_is_blocked

from agent_relay.infrastructure.persistence.database import Database
from agent_relay.infrastructure.persistence.models import Base, RoomRecord, TopicRecord
from agent_relay.infrastructure.persistence.sqlite import time_at_or_before


@pytest.fixture
def database(tmp_path: Path, databases: MemoryDatabases) -> Database:
    return databases.create(tmp_path / "foundation.sqlite3")


def test_mapping_matches_the_migrated_schema(database: Database) -> None:
    schema = inspect(database.engine)
    assert set(schema.get_table_names()) - {"alembic_version"} == set(Base.metadata.tables)
    for name, mapped in Base.metadata.tables.items():
        assert {column["name"] for column in schema.get_columns(name)} == set(mapped.c.keys())
        assert schema.get_pk_constraint(name)["constrained_columns"] == [
            column.name for column in mapped.primary_key.columns
        ]
    with database.read() as session:
        assert all(
            row[2] == "" for row in session.connection().exec_driver_sql("PRAGMA database_list")
        )


@pytest.mark.parametrize("commit", [False, True])
def test_request_shares_one_lazy_session_and_finishes_all_writes(
    database: Database, commit: bool
) -> None:
    transaction = database.request_transaction()
    with database.read(transaction) as reader:
        assert transaction.session is None
        assert list(reader.scalars(select(RoomRecord.id))) == []
    with database.write(transaction) as writer:
        writer.add(RoomRecord(id="room", project_path="D:/room", name="Room", description=""))
        writer.flush()
    with database.write(transaction) as borrowed:
        assert borrowed is writer
        borrowed.add(TopicRecord(room_id="room", id="topic", name="Topic", description=""))
        borrowed.flush()
    assert_reader_is_blocked(database)
    transaction.finish(commit=commit)
    with database.read() as reader:
        assert list(reader.scalars(select(RoomRecord.id))) == (["room"] if commit else [])
        assert list(reader.scalars(select(TopicRecord.id))) == (["topic"] if commit else [])


def test_foreign_keys_apply_to_independent_connections(database: Database) -> None:
    with database.read() as occupied, pytest.raises(IntegrityError), database.write() as writer:
        assert occupied.connection() is not writer.connection()
        writer.add(TopicRecord(room_id="missing", id="topic", name="Topic", description=""))
        writer.flush()


def test_database_rejects_unmigrated_and_wrong_revision(
    tmp_path: Path, databases: MemoryDatabases
) -> None:
    path = tmp_path / "revision.sqlite3"
    with pytest.raises(RuntimeError, match="not migrated"):
        databases.open(path)
    databases.migrate(path)
    with databases.engine(path).begin() as connection:
        connection.exec_driver_sql("UPDATE alembic_version SET version_num = 'wrong'")
    with pytest.raises(RuntimeError, match="expected"):
        databases.open(path)


def test_sql_time_comparison_includes_equal_instants_across_timezones(database: Database) -> None:
    cutoff = datetime.fromisoformat("2026-11-11T12:00:30.123000+08:00")
    equivalent = cutoff.astimezone(UTC)
    with database.read() as session:
        assert session.scalar(select(time_at_or_before(literal(equivalent), cutoff))) is True
