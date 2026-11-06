from collections.abc import Iterator

import pytest

from agent_relay.config import load_settings


@pytest.fixture(autouse=True)
def isolate_settings_cache() -> Iterator[None]:
    load_settings.cache_clear()
    yield
    load_settings.cache_clear()
