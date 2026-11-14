from pathlib import Path

from alembic import context, op

from agent_relay.infrastructure.persistence.migration_sql import execute_sql_file

revision = "channel_description_20261114"
down_revision = "channels_20261113"
branch_labels = None
depends_on = None


def upgrade() -> None:
    directory = Path(__file__).parents[1] / "sql/0006_channel_description"
    execute_sql_file(directory / "00_schema.up.sql")
    if (
        not context.is_offline_mode()
        and op.get_bind().exec_driver_sql("PRAGMA foreign_key_check").fetchone() is not None
    ):
        raise RuntimeError("Channel description migration left invalid foreign keys")
    op.execute("PRAGMA defer_foreign_keys=OFF")


def downgrade() -> None:
    raise RuntimeError("Restore a stopped-service backup to downgrade the channel schema")
