import sqlite3
from contextlib import closing
from pathlib import Path

import pytest


@pytest.mark.integration
def test_migration_sql_executes(tmp_path: Path) -> None:
    sql_root = Path(__file__).resolve().parents[2] / "migrations/sqlite/sql"
    sql_files = sorted(sql_root.rglob("*.up.sql"))
    assert sql_files

    with closing(sqlite3.connect(tmp_path / "migrations.sqlite3")) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        for sql_file in sql_files:
            connection.executescript(sql_file.read_text(encoding="utf-8"))
        assert connection.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
