"""Scope active session bindings to each channel."""

from pathlib import Path

from conflua.infrastructure.persistence.migration_sql import execute_sql_file

revision = "member_channels_20261117"
down_revision = "delivery_retry_20261116"
branch_labels = None
depends_on = None


def upgrade() -> None:
    execute_sql_file(
        Path(__file__).resolve().parents[1] / "sql/0003_member_channels/01_index.up.sql"
    )


def downgrade() -> None:
    raise NotImplementedError("Database migration downgrades are not supported")
