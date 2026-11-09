import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from alembic.util.exc import CommandError

from agent_relay.infrastructure.persistence.migrations import MIGRATION_HEAD, run_migrations
from agent_relay.infrastructure.persistence.store import SQLiteRoomStore


def test_baseline_initializes_database_and_is_repeatable(tmp_path: Path) -> None:
    path = tmp_path / "rooms.sqlite3"
    run_migrations(path)
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("INSERT INTO rooms VALUES ('room', '/project', '{}')")
        connection.commit()

    run_migrations(path)
    SQLiteRoomStore(path)
    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchall() == [
            (MIGRATION_HEAD,)
        ]
        assert connection.execute("SELECT id FROM rooms").fetchall() == [("room",)]
        assert connection.execute("SELECT kind, entity_id FROM room_events").fetchall() == []
        assert (
            connection.execute("SELECT name FROM sqlite_master WHERE type = 'trigger'").fetchall()
            == []
        )
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_legacy_revision_is_rejected_without_changing_data(tmp_path: Path) -> None:
    path = tmp_path / "legacy.sqlite3"
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        connection.execute("INSERT INTO alembic_version VALUES ('user_member')")
        connection.execute("CREATE TABLE existing_data (value TEXT)")
        connection.execute("INSERT INTO existing_data VALUES ('keep')")
        connection.commit()

    with pytest.raises(CommandError, match="user_member"):
        run_migrations(path)
    with pytest.raises(RuntimeError, match="rebuild an incompatible development database"):
        SQLiteRoomStore(path)
    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute("SELECT value FROM existing_data").fetchall() == [("keep",)]
        assert connection.execute("SELECT version_num FROM alembic_version").fetchall() == [
            ("user_member",)
        ]
