"""${message}"""

from pathlib import Path

from agent_relay.migration_sql import execute_sql_file

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    execute_sql_file(Path(__file__).resolve().parents[1] / "sql/${up_revision}/01_change.up.sql")


def downgrade() -> None:
    raise NotImplementedError("Database migration downgrades are not supported")
