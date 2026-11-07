"""Remove the unused role field from persisted member records."""

from pathlib import Path

from agent_relay.migration_sql import execute_sql_file

revision = "remove_member_role"
down_revision = "room_resources"
branch_labels = None
depends_on = None


def upgrade() -> None:
    execute_sql_file(
        Path(__file__).resolve().parents[1]
        / "sql/0002_remove_member_role/01_remove_member_role.up.sql"
    )


def downgrade() -> None:
    raise NotImplementedError("Database migration downgrades are not supported")
