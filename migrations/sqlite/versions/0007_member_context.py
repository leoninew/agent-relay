"""Record explicitly provided context and per-topic positions."""

from pathlib import Path

from agent_relay.migration_sql import execute_sql_file

revision = "member_context"
down_revision = "room_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    execute_sql_file(
        Path(__file__).resolve().parents[1] / "sql/0007_member_context/01_member_context.up.sql"
    )


def downgrade() -> None:
    raise NotImplementedError("Database migration downgrades are not supported")
