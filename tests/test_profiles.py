import os
from pathlib import Path
from shutil import copyfile

from pytest import MonkeyPatch

from agent_relay.config import load_settings

PROJECT_ROOT = Path(__file__).parents[1]


def prepare_config(root: Path) -> None:
    (root / "config").mkdir(parents=True)
    copyfile(PROJECT_ROOT / "config/config.yaml", root / "config/config.yaml")


def test_profile_switch_does_not_pollute_process_environment(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    dev_root = tmp_path / "dev"
    qa_root = tmp_path / "qa"
    prepare_config(dev_root)
    prepare_config(qa_root)
    (dev_root / ".env.dev").write_text("AGENT_RELAY_GREETING__PREFIX=你好\n", encoding="utf-8")
    (qa_root / ".env.qa").write_text("AGENT_RELAY_GREETING__PREFIX=QA\n", encoding="utf-8")
    monkeypatch.delenv("AGENT_RELAY_GREETING__PREFIX", raising=False)
    monkeypatch.setenv("AGENT_RELAY_PROFILE", "dev")

    dev = load_settings(dev_root)
    assert dev.profile == "dev"
    assert dev.greeting.prefix == "你好"
    assert "AGENT_RELAY_GREETING__PREFIX" not in os.environ

    monkeypatch.setenv("AGENT_RELAY_PROFILE", "qa")
    qa = load_settings(qa_root)
    assert qa.profile == "qa"
    assert qa.greeting.prefix == "QA"


def test_os_environment_overrides_profile(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    prepare_config(tmp_path)
    (tmp_path / ".env.qa").write_text("AGENT_RELAY_GREETING__PREFIX=QA\n", encoding="utf-8")
    monkeypatch.setenv("AGENT_RELAY_PROFILE", "qa")
    monkeypatch.setenv("AGENT_RELAY_GREETING__PREFIX", "Override")

    settings = load_settings(tmp_path)

    assert settings.profile == "qa"
    assert settings.greeting.prefix == "Override"


def test_dev_profile_enables_reload(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    prepare_config(tmp_path)
    (tmp_path / ".env.dev").write_text("AGENT_RELAY_SERVER__RELOAD=true\n", encoding="utf-8")
    monkeypatch.setenv("AGENT_RELAY_PROFILE", "dev")

    settings = load_settings(tmp_path)
    assert settings.server.reload is True


def test_prod_profile_uses_defaults_without_loading_other_dotenv_files(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    prepare_config(tmp_path)
    for name in (".env", ".env.dev"):
        (tmp_path / name).write_text("AGENT_RELAY_SERVER__RELOAD=true\n", encoding="utf-8")
    monkeypatch.delenv("AGENT_RELAY_PROFILE", raising=False)

    settings = load_settings(tmp_path)

    assert settings.profile == "prod"
    assert settings.server.reload is False
