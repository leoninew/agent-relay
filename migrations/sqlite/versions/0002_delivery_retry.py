"""Persist delivery retry scheduling."""

from pathlib import Path

from conflua.infrastructure.persistence.migration_sql import execute_sql_file

revision = "delivery_retry_20261116"
down_revision = "channel_description_20261114"
branch_labels = None
depends_on = None


def upgrade() -> None:
    execute_sql_file(
        Path(__file__).resolve().parents[1] / "sql/0002_delivery_retry/01_retry.up.sql"
    )


def downgrade() -> None:
    raise NotImplementedError("Database migration downgrades are not supported")
