from pathlib import Path
from unittest.mock import Mock

from pytest import MonkeyPatch

from agent_relay.infrastructure.persistence.migrations import run_migrations


def test_migrations_use_explicit_resources_not_current_directory(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    database_path = tmp_path / "user data" / "relay.sqlite3"
    resources = Path(__file__).parents[4]
    monkeypatch.chdir(tmp_path)
    upgrade = Mock()
    monkeypatch.setattr(
        "agent_relay.infrastructure.persistence.migrations.command.upgrade", upgrade
    )

    run_migrations(database_path, resources=resources)

    configuration, revision = upgrade.call_args.args
    assert revision == "head"
    assert configuration.config_file_name == str(resources / "alembic.ini")
    assert configuration.get_main_option("script_location") == str(resources / "migrations/sqlite")
    assert (
        configuration.get_main_option("sqlalchemy.url") == f"sqlite:///{database_path.as_posix()}"
    )
    assert not database_path.exists()
