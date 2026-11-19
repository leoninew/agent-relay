"""Create the current SQLite schema."""

from pathlib import Path

from conflua.infrastructure.persistence.migration_sql import execute_sql_file

revision = "schema_governance_20261119"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    sql_directory = Path(__file__).resolve().parents[1] / "sql/0001_baseline"
    execute_sql_file(sql_directory / "01_schema.up.sql")
    execute_sql_file(sql_directory / "02_seed.up.sql")


def downgrade() -> None:
    raise NotImplementedError("Database migration downgrades are not supported")
