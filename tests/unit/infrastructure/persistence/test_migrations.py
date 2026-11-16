import sqlite3
from pathlib import Path
from unittest.mock import Mock

from alembic import command
from pytest import MonkeyPatch

from conflua.infrastructure.persistence.dependencies import create_database
from conflua.infrastructure.persistence.migrations import _configuration, run_migrations


def test_create_database_initializes_schema(tmp_path: Path) -> None:
    path = tmp_path / "conflua.db"
    database = create_database(path)
    try:
        assert path.is_file()
    finally:
        database.close()


def test_migrations_use_explicit_resources_not_current_directory(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    database_path = tmp_path / "user data" / "conflua.sqlite3"
    resources = Path(__file__).parents[4]
    monkeypatch.chdir(tmp_path)
    upgrade = Mock()
    monkeypatch.setattr("conflua.infrastructure.persistence.migrations.command.upgrade", upgrade)

    run_migrations(database_path, resources=resources)

    configuration, revision = upgrade.call_args.args
    assert revision == "head"
    assert configuration.config_file_name == str(resources / "alembic.ini")
    assert configuration.get_main_option("script_location") == str(resources / "migrations/sqlite")
    assert (
        configuration.get_main_option("sqlalchemy.url") == f"sqlite:///{database_path.as_posix()}"
    )
    assert not database_path.exists()


def test_retry_migration_preserves_legacy_unknown_and_defaults(tmp_path: Path) -> None:
    path = tmp_path / "legacy.db"
    command.upgrade(_configuration(path), "channel_description_20261114")
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript("""
            INSERT INTO rooms(id,project_path,name,description) VALUES('r','p','room','');
            INSERT INTO channels(room_id,id,name,working_path,is_default,workspace_kind)
                VALUES('r','channel-default','default','p',1,'existing');
            INSERT INTO sessions(room_id,id,name,provider,project_path,presence)
                VALUES('r','s','session','codex','p','available');
            INSERT INTO members(room_id,id,name,session_id,kind,initials,presence,
                activity,activity_source)
                VALUES('r','agent','agent','s','agent','A','available','','');
            INSERT INTO messages(room_id,id,seq,publisher_id,content,created_at)
                VALUES('r','m',1,'agent','original','2026-11-16T00:00:00+00:00');
            INSERT INTO deliveries(room_id,id,message_id,target_member_id,target_session_id,
                client_message_id,status,updated_at)
                VALUES('r','d','m','agent','s','client','unknown','2026-11-16T00:00:00+00:00');
        """)
    run_migrations(path)
    run_migrations(path)
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT client_message_id,status,attempt_count,next_attempt_at FROM deliveries"
        ).fetchall() == [("client", "unknown", 0, None)]
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
