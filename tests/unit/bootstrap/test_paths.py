from pathlib import Path
from shutil import copyfile
from types import SimpleNamespace

import pytest
from pytest import MonkeyPatch

from agent_relay.bootstrap import paths

APP_CONFIG = Path(__file__).parents[3] / "config" / "app.yaml"


def test_app_settings_use_user_override_and_separate_path_roots(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    resources = tmp_path / "resources"
    config = resources / "config" / "app.yaml"
    config.parent.mkdir(parents=True)
    copyfile(APP_CONFIG, config)
    user_root = tmp_path / "user data"
    user_root.mkdir()
    (user_root / ".env").write_text(
        "AGENT_RELAY_SERVER__PORT=19080\n"
        "AGENT_RELAY_DATABASE__PATH=./store/custom.sqlite3\n"
        "AGENT_RELAY_STATIC__DIRECTORY=./web-assets\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AGENT_RELAY_PROFILE", "dev")
    monkeypatch.setenv("AGENT_RELAY_SERVER__HOST", "localhost")
    monkeypatch.delenv("AGENT_RELAY_DATABASE__PATH", raising=False)
    monkeypatch.setenv("AGENT_RELAY_URL", "http://configured-relay")
    monkeypatch.setenv("AGENT_RELAY_HTTP_TIMEOUT", "3.5")
    monkeypatch.setenv("AGENT_RELAY_SESSION_ID", "session-from-cli")
    settings = paths.load_app_settings(user_root=user_root, resources=resources)

    assert settings.profile == "app"
    assert settings.server.host == "localhost"
    assert settings.server.port == 19080
    assert settings.database.migrate_on_startup is True
    assert settings.database.path == (user_root / "store/custom.sqlite3").resolve()
    assert settings.static.directory == (resources / "web-assets").resolve()


def test_app_settings_reject_unknown_service_environment_variables(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    resources = tmp_path / "resources"
    config = resources / "config" / "app.yaml"
    config.parent.mkdir(parents=True)
    copyfile(APP_CONFIG, config)
    monkeypatch.setenv("AGENT_RELAY_SERVER__PORRT", "9081")

    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        paths.load_app_settings(user_root=tmp_path / "user", resources=resources)


def test_frozen_resources_are_resolved_from_extraction_root(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "agent_relay.resources.sys",
        SimpleNamespace(frozen=True, _MEIPASS=str(tmp_path)),
    )

    assert paths.resource_root() == (tmp_path / "resources").resolve()
