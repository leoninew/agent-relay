from collections.abc import Iterator
from pathlib import Path

import pytest
from support.databases import MemoryDatabases

from agent_relay.bootstrap import http
from agent_relay.bootstrap.config import load_settings
from agent_relay.infrastructure.persistence.database import Database


@pytest.fixture(autouse=True)
def isolate_settings_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    monkeypatch.setenv("AGENT_RELAY_DATABASE__PATH", str(tmp_path / "application.sqlite3"))
    load_settings.cache_clear()
    yield
    load_settings.cache_clear()


@pytest.fixture
def databases(tmp_path: Path) -> Iterator[MemoryDatabases]:
    databases = MemoryDatabases()
    try:
        yield databases
    finally:
        databases.close()
        assert not list(tmp_path.rglob("*.sqlite3")), "Database tests must use SQLite memory mode"


@pytest.fixture(autouse=True)
def memory_database_runtime(databases: MemoryDatabases, monkeypatch: pytest.MonkeyPatch) -> None:
    def create_database(path: Path, *, migrate_on_startup: bool = False) -> Database:
        if migrate_on_startup:
            databases.migrate(path)
        return databases.open(path)

    monkeypatch.setattr(http, "create_database", create_database)


@pytest.fixture
def migrated_database(databases: MemoryDatabases) -> None:
    """Explicit schema setup for API integration tests."""
    databases.migrate(load_settings().database.path)
    load_settings.cache_clear()
