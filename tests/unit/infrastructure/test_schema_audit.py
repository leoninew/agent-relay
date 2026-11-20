from datetime import UTC, datetime, timedelta, timezone

from sqlalchemy.dialects.sqlite import dialect

from conflua.infrastructure.persistence.models import Base, ChannelRecord
from conflua.infrastructure.persistence.repositories.channels import channel_from_record
from conflua.infrastructure.persistence.types import ISODateTime


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
