"""Create the current SQLite schema."""

from pathlib import Path

from agent_relay.infrastructure.persistence.migration_sql import execute_sql_file

revision = "baseline_20261109"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    execute_sql_file(Path(__file__).resolve().parents[1] / "sql/0001_baseline/01_schema.up.sql")


def downgrade() -> None:
    raise NotImplementedError("Database migration downgrades are not supported")
