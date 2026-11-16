from collections.abc import Iterator
from pathlib import Path

import pytest

from conflua.bootstrap.config import load_settings


@pytest.fixture(autouse=True)
def isolate_settings_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    monkeypatch.setenv("CONFLUA_DATABASE__PATH", str(tmp_path / "application.sqlite3"))
    load_settings.cache_clear()
    yield
    load_settings.cache_clear()
