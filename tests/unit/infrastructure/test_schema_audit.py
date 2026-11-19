import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.sqlite import dialect

from conflua.infrastructure.persistence.models import Base, ChannelRecord
from conflua.infrastructure.persistence.repositories.channels import channel_from_record
from conflua.infrastructure.persistence.types import ISODateTime


def test_database_enforces_identity_and_scope_not_message_payload(tmp_path: Path) -> None:
    path = tmp_path / "scope.db"
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    try:
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()
    with closing(sqlite3.connect(path)) as db:
        db.executescript("""
            PRAGMA foreign_keys = ON;
            INSERT INTO rooms(id, workspace_path, raw_workspace_path, name, description)
              VALUES ('r', '/r', '/r', 'R', '');
            INSERT INTO channels(id, room_id, name, is_default, workspace_kind) VALUES
              ('first', 'r', 'First', 1, 'existing'), ('other', 'r', 'Other', 0, 'existing');
            INSERT INTO members(id, room_id, channel_id, name, kind, initials, presence,
                                activity, activity_source)
              VALUES ('human', 'r', 'first', '你', 'human', '', 'available', '', '');
        """)
        insert = """INSERT INTO messages(id, room_id, channel_id, seq, publication_id,
                                         publisher_id, content, capabilities)
                    VALUES (?, 'r', ?, ?, ?, 'human', 'text', '{}')"""
        db.execute(insert, ("msg", "first", 1, "publication"))
        with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
            db.execute(insert, ("msg", "first", 2, "different"))
        with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
            db.execute(insert, ("another", "first", 2, "publication"))
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            db.execute(insert, ("another", "other", 2, "different"))


def test_orm_audit_contract_covers_every_business_table() -> None:
    assert len(Base.metadata.tables) == 16
    for table in Base.metadata.tables.values():
        created_at = table.c.created_at
        updated_at = table.c.updated_at
        assert not created_at.nullable
        assert created_at.server_default is not None
        assert created_at.onupdate is None
        assert updated_at.nullable
        assert updated_at.onupdate is not None


def test_persisted_time_retains_instant_and_uses_utc() -> None:
    timestamp = datetime(2026, 11, 19, 15, 10, 5, 123456, tzinfo=timezone(timedelta(hours=8)))
    sqlite = dialect()
    column_type = ISODateTime()

    stored = column_type.process_bind_param(timestamp, sqlite)
    restored = column_type.process_result_value(stored, sqlite)

    assert stored == "2026-11-19T07:10:05.123456+00:00"
    assert restored == timestamp
    assert restored is not None and restored.tzinfo == UTC


def test_channel_mapping_retains_archive_and_worktree_metadata() -> None:
    timestamp = datetime(2026, 11, 19, tzinfo=UTC)
    record = ChannelRecord(
        id="0000000000123",
        room_id="0000000000124",
        name="Archived work",
        description="History is still available",
        worktree_path="/worktree",
        is_default=False,
        status="archived",
        workspace_kind="worktree",
        created_at=timestamp,
        archived_at=timestamp,
        is_deleted=False,
    )

    channel = channel_from_record(record, "/workspace")

    assert channel.status == "archived"
    assert channel.archived_at == timestamp
    assert channel.working_path == "/worktree"
