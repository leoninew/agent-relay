"""Bind member publication credentials to persisted membership."""

from pathlib import Path

from agent_relay.migration_sql import execute_sql_file

revision = "member_publish"
down_revision = "queue_delivery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    execute_sql_file(
        Path(__file__).resolve().parents[1] / "sql/0005_member_publish/01_member_publish.up.sql"
    )


def downgrade() -> None:
    raise NotImplementedError("Database migration downgrades are not supported")
