"""Retain deleted nodes while releasing their active names and session bindings."""

from pathlib import Path

from agent_relay.migration_sql import execute_sql_file

revision = "sidebar_node_actions"
down_revision = "remove_member_role"
branch_labels = None
depends_on = None


def upgrade() -> None:
    execute_sql_file(
        Path(__file__).resolve().parents[1] / "sql/0003_sidebar_node_actions/01_nodes.up.sql"
    )


def downgrade() -> None:
    raise NotImplementedError("Database migration downgrades are not supported")
