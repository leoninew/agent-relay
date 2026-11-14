from pathlib import Path

from alembic import context, op

from agent_relay.infrastructure.persistence.migration_sql import execute_sql_file

revision = "channels_20261113"
down_revision = "message_deleted_20261112"
branch_labels = None
depends_on = None


def upgrade() -> None:
    directory = Path(__file__).parents[1] / "sql/0005_channels"
    for filename in ("00_prepare.up.sql", "01_schema.up.sql", "02_data.up.sql"):
        execute_sql_file(directory / filename)
    if (
        not context.is_offline_mode()
        and op.get_bind().exec_driver_sql("PRAGMA foreign_key_check").fetchone() is not None
    ):
        raise RuntimeError("Channel migration left invalid foreign keys")


def downgrade() -> None:
    raise RuntimeError("Restore a stopped-service backup to downgrade the channel schema")
