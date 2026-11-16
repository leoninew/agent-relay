from pathlib import Path
from unittest.mock import Mock

from pytest import MonkeyPatch

from conflua.infrastructure.persistence.dependencies import create_database
from conflua.infrastructure.persistence.migrations import run_migrations


def test_create_database_initializes_schema(tmp_path: Path) -> None:
    path = tmp_path / "conflua.db"
    database = create_database(path)
    try:
        assert path.is_file()
    finally:
        database.close()


def test_migrations_use_explicit_resources_not_current_directory(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    database_path = tmp_path / "user data" / "conflua.sqlite3"
    resources = Path(__file__).parents[4]
    monkeypatch.chdir(tmp_path)
    upgrade = Mock()
    monkeypatch.setattr("conflua.infrastructure.persistence.migrations.command.upgrade", upgrade)

    run_migrations(database_path, resources=resources)

    configuration, revision = upgrade.call_args.args
    assert revision == "head"
    assert configuration.config_file_name == str(resources / "alembic.ini")
    assert configuration.get_main_option("script_location") == str(resources / "migrations/sqlite")
    assert (
        configuration.get_main_option("sqlalchemy.url") == f"sqlite:///{database_path.as_posix()}"
    )
    assert not database_path.exists()
