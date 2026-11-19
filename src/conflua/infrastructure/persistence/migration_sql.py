"""Execute the explicitly listed SQL statements in an Alembic revision."""

from pathlib import Path

import sqlparse
from alembic import op


def execute_sql_file(path: Path) -> None:
    for statement in sqlparse.split(path.read_text(encoding="utf-8"), strip_semicolon=True):
        op.execute(statement)
