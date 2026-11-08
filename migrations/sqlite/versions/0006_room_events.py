"""Record resource and delivery events in their original transaction."""

from pathlib import Path

from agent_relay.migration_sql import execute_sql_file

revision = "room_events"
down_revision = "member_publish"
branch_labels = None
depends_on = None


def upgrade() -> None:
    execute_sql_file(
        Path(__file__).resolve().parents[1] / "sql/0006_room_events/01_room_events.up.sql"
    )


def downgrade() -> None:
    raise NotImplementedError("Database migration downgrades are not supported")
