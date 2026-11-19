"""Create the site-wide member role catalog."""

from pathlib import Path

from conflua.infrastructure.persistence.migration_sql import execute_sql_file

revision = "member_roles_20261118"
down_revision = "workspace_paths_20261117"
branch_labels = None
depends_on = None


def upgrade() -> None:
    sql_directory = Path(__file__).resolve().parents[1] / "sql/0007_member_roles"
    execute_sql_file(sql_directory / "01_schema.up.sql")
    execute_sql_file(sql_directory / "02_seed.up.sql")


def downgrade() -> None:
    raise NotImplementedError("Database migration downgrades are not supported")
