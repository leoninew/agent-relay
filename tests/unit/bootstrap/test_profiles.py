import os
from pathlib import Path
from shutil import copyfile

from pytest import MonkeyPatch

from conflua.bootstrap.config import load_settings

PROJECT_ROOT = Path(__file__).parents[3]


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
    (dev_root / ".env.dev").write_text("CONFLUA_SERVER__PORT=19080\n", encoding="utf-8")
    (qa_root / ".env.qa").write_text("CONFLUA_SERVER__PORT=19081\n", encoding="utf-8")
    monkeypatch.delenv("CONFLUA_SERVER__PORT", raising=False)
    monkeypatch.setenv("CONFLUA_PROFILE", "dev")

    dev = load_settings(dev_root)
    assert dev.profile == "dev"
    assert dev.server.port == 19080
    assert "CONFLUA_SERVER__PORT" not in os.environ

    monkeypatch.setenv("CONFLUA_PROFILE", "qa")
    qa = load_settings(qa_root)
    assert qa.profile == "qa"
    assert qa.server.port == 19081


def test_os_environment_overrides_profile(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    prepare_config(tmp_path)
    (tmp_path / ".env.qa").write_text(
        "CONFLUA_SERVER__HOST=localhost\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CONFLUA_PROFILE", "qa")
    monkeypatch.setenv("CONFLUA_SERVER__HOST", "127.0.0.2")
    monkeypatch.setenv("CONFLUA_SERVER__RELOAD_PATHS", '["src/**/*.py", ".env.qa"]')

    settings = load_settings(tmp_path)

    assert settings.profile == "qa"
    assert settings.server.host == "127.0.0.2"
    assert settings.server.reload_paths == ["src/**/*.py", ".env.qa"]


def test_dev_profile_enables_reload(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    prepare_config(tmp_path)
    (tmp_path / ".env.dev").write_text(
        'CONFLUA_SERVER__RELOAD=true\nCONFLUA_SERVER__RELOAD_PATHS=["src/**/*.py", ".env.dev"]\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("CONFLUA_PROFILE", "dev")

    settings = load_settings(tmp_path)
    assert settings.server.reload is True
    assert settings.server.reload_paths == ["src/**/*.py", ".env.dev"]


def test_prod_profile_uses_defaults_without_loading_other_dotenv_files(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    prepare_config(tmp_path)
    for name in (".env", ".env.dev"):
        (tmp_path / name).write_text("CONFLUA_SERVER__RELOAD=true\n", encoding="utf-8")
    monkeypatch.delenv("CONFLUA_PROFILE", raising=False)

    settings = load_settings(tmp_path)

    assert settings.profile == "prod"
    assert settings.server.reload is False
