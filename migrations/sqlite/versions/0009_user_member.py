"""Represent the room user as a member without a Codex session."""

from pathlib import Path

from agent_relay.migration_sql import execute_sql_file

revision = "user_member"
down_revision = "member_api"
branch_labels = None
depends_on = None


def upgrade() -> None:
    execute_sql_file(
        Path(__file__).resolve().parents[1] / "sql/0009_user_member/01_user_member.up.sql"
    )


def downgrade() -> None:
    raise NotImplementedError("Database migration downgrades are not supported")
