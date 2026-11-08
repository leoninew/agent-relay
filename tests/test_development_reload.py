from pathlib import Path
from unittest.mock import Mock

import pytest
from uvicorn import Config

from agent_relay.development_reload import DevelopmentReload


def reloader(root: Path, pattern: str) -> DevelopmentReload:
    return DevelopmentReload(
        Config("agent_relay.server:create_server_app", log_config=None, reload_delay=0),
        target=Mock(),
        sockets=[],
        paths=[str(root / pattern)],
    )


@pytest.mark.parametrize(
    ("relative", "pattern"),
    [
        ("src/agent_relay/server.py", "src/agent_relay/**/*.py"),
        ("src/agent_relay/routers/room.py", "src/agent_relay/**/*.py"),
        ("config/config.yaml", "config/*.yaml"),
        (".env.qa", ".env.qa"),
        ("src/agent_relay/logging.yaml", "src/agent_relay"),
    ],
)
def test_reloads_when_a_configured_file_is_saved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, relative: str, pattern: str
) -> None:
    path = tmp_path / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("original", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    reload = reloader(Path("."), pattern)

    path.write_text("updated contents", encoding="utf-8")

    assert reload.should_restart() == [path]


@pytest.mark.parametrize("relative", [".env.qa", "config/config.yaml"])
def test_reloads_after_atomic_save(tmp_path: Path, relative: str) -> None:
    path = tmp_path / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("original", encoding="utf-8")
    reload = reloader(tmp_path, relative)
    replacement = path.with_name("replacement.tmp")
    replacement.write_text("replaced", encoding="utf-8")

    replacement.replace(path)

    assert reload.should_restart() == [path]


def test_reloads_after_source_is_added_and_deleted(tmp_path: Path) -> None:
    reload = reloader(tmp_path, "src/agent_relay/**/*.py")
    path = tmp_path / "src/agent_relay/routers/room.py"
    path.parent.mkdir(parents=True)

    path.write_text("new source", encoding="utf-8")
    assert reload.should_restart() == [path]

    path.unlink()
    assert reload.should_restart() == [path]
