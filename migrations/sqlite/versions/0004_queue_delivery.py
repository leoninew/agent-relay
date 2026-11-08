"""Persist publication identity, frozen sessions and real queue results."""

from pathlib import Path

from agent_relay.migration_sql import execute_sql_file

revision = "queue_delivery"
down_revision = "sidebar_node_actions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    execute_sql_file(
        Path(__file__).resolve().parents[1] / "sql/0004_queue_delivery/01_delivery.up.sql"
    )


def downgrade() -> None:
    raise NotImplementedError("Database migration downgrades are not supported")
