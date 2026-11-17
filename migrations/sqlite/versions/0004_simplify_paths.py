"""Keep raw and normalized room paths and independent worktree paths."""

from pathlib import Path

from conflua.infrastructure.persistence.migration_sql import execute_sql_file

revision = "simplify_paths_20261117"
down_revision = "member_channels_20261117"
branch_labels = None
depends_on = None


def upgrade() -> None:
    execute_sql_file(
        Path(__file__).resolve().parents[1] / "sql/0004_simplify_paths/01_schema.up.sql"
    )


def downgrade() -> None:
    raise NotImplementedError("Database migration downgrades are not supported")
