"""Store capability references with each message."""

from pathlib import Path

from agent_relay.infrastructure.persistence.migration_sql import execute_sql_file

revision = "capabilities_json_20261111"
down_revision = "queue_deleted_20261110"
branch_labels = None
depends_on = None


def upgrade() -> None:
    execute_sql_file(
        Path(__file__).resolve().parents[1] / "sql/0002_capabilities_json/01_schema.up.sql"
    )


def downgrade() -> None:
    raise NotImplementedError("Database migration downgrades are not supported")
