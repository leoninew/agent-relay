from pathlib import Path

from agent_relay.infrastructure.persistence.migration_sql import execute_sql_file

revision = "message_deleted_20261112"
down_revision = "delivery_steer_20261112"
branch_labels = None
depends_on = None


def upgrade() -> None:
    execute_sql_file(
        Path(__file__).resolve().parents[1] / "sql/0004_message_soft_delete/01_schema.up.sql"
    )


def downgrade() -> None:
    raise NotImplementedError("Database migration downgrades are not supported")
