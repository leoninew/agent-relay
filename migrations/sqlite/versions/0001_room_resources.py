"""Create room, topic, session, member and message resources."""

from pathlib import Path

from agent_relay.migration_sql import execute_sql_file

revision = "room_resources"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    execute_sql_file(
        Path(__file__).resolve().parents[1] / "sql/0001_room_resources/01_rooms.up.sql"
    )


def downgrade() -> None:
    raise NotImplementedError("Database migration downgrades are not supported")
