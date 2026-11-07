from collections.abc import Iterator
from pathlib import Path

import pytest

from agent_relay.config import load_settings
from agent_relay.migrations import run_migrations


@pytest.fixture(autouse=True)
def isolate_settings_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    monkeypatch.setenv("AGENT_RELAY_DATABASE__PATH", str(tmp_path / "application.sqlite3"))
    load_settings.cache_clear()
    yield
    load_settings.cache_clear()


@pytest.fixture
def migrated_database() -> None:
    """Explicit schema setup for API integration tests."""
    run_migrations(load_settings().database.path)
    load_settings.cache_clear()
