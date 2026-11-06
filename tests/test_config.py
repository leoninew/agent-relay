from pathlib import Path
from shutil import copyfile

from pytest import MonkeyPatch

from agent_relay.config import load_settings

CONFIG_FILE = Path(__file__).parents[1] / "config" / "config.yaml"


def test_settings_loads_dotenv_with_environment_override(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    env_file = tmp_path / ".env.prod"
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    copyfile(CONFIG_FILE, config_dir / "config.yaml")
    env_file.write_text(
        "AGENT_RELAY_GREETING__PREFIX=Bonjour\nAGENT_RELAY_STATIC__DIRECTORY=./assets\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AGENT_RELAY_GREETING__PREFIX", "Hi")
    monkeypatch.setenv("AGENT_RELAY_PROFILE", "prod")

    settings = load_settings(tmp_path)

    assert settings.greeting.prefix == "Hi"
    assert settings.static.directory == Path("assets")


def test_load_settings_caches_one_settings_instance(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_RELAY_GREETING__PREFIX", "Hi")
    initial_settings = load_settings()
    monkeypatch.setenv("AGENT_RELAY_GREETING__PREFIX", "Bonjour")

    assert load_settings() is initial_settings
    assert initial_settings.greeting.prefix == "Hi"
