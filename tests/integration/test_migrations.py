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
        connection.execute(
            "INSERT INTO rooms(id, project_path, name, description) "
            "VALUES ('room', '/project', 'Project', '')"
        )
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


def test_queue_marker_upgrade_preserves_existing_baseline_data(tmp_path: Path) -> None:
    path = tmp_path / "baseline.sqlite3"
    schema = Path("migrations/sqlite/sql/0001_baseline/01_schema.up.sql").read_text()
    with closing(sqlite3.connect(path)) as connection:
        connection.executescript(schema)
        connection.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        connection.execute("INSERT INTO alembic_version VALUES ('baseline_20261110')")
        connection.execute(
            "INSERT INTO rooms(id, project_path, name, description) "
            "VALUES ('room', '/project', 'Project', '')"
        )
        connection.commit()
    run_migrations(path)
    SQLiteRoomStore(path)
    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute("SELECT id FROM rooms").fetchall() == [("room",)]
        assert "deleted_at" in {
            column[1] for column in connection.execute("PRAGMA table_info(deliveries)")
        }
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
