"""Remove member publish credentials now that local routes identify members by path."""

from pathlib import Path

from agent_relay.migration_sql import execute_sql_file

revision = "member_api"
down_revision = "member_context"
branch_labels = None
depends_on = None


def upgrade() -> None:
    execute_sql_file(
        Path(__file__).resolve().parents[1] / "sql/0008_member_api/01_member_api.up.sql"
    )


def downgrade() -> None:
    raise NotImplementedError("Database migration downgrades are not supported")
