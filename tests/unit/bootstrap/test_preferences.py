import ctypes
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from agent_relay.application.preferences.ports import PreferenceReadError, PreferenceWriteError
from agent_relay.application.preferences.service import PreferencesService
from agent_relay.infrastructure.preferences.store import FilePreferencesStore
from agent_relay.infrastructure.preferences.system_language import detect_system_language


@pytest.mark.parametrize("locale", ["zh-CN", "zh-TW", "zh-HK", "zh_Hans_CN", "zh_CN.UTF-8"])
def test_chinese_locales(locale: str) -> None:
    assert detect_system_language(platform="linux", environ={"LANG": locale}) == "zh-CN"


@pytest.mark.parametrize("locale", ["en-US", "ja_JP", "C", "POSIX", "unknown"])
def test_other_locales(locale: str) -> None:
    assert detect_system_language(platform="linux", environ={"LANG": locale}) == "en"


def test_locale_priority() -> None:
    assert (
        detect_system_language(
            platform="linux", environ={"LC_ALL": "en_US.UTF-8", "LANG": "zh_CN.UTF-8"}
        )
        == "en"
    )
    assert detect_system_language(platform="linux", environ={}) == "en"


def test_windows_uses_user_ui_language(monkeypatch: pytest.MonkeyPatch) -> None:
    ui_language = Mock(return_value=0x0404)
    monkeypatch.setattr(
        ctypes,
        "windll",
        SimpleNamespace(kernel32=SimpleNamespace(GetUserDefaultUILanguage=ui_language)),
        raising=False,
    )
    assert detect_system_language(platform="win32", environ={"LANG": "en_US"}) == "zh-CN"
    ui_language.side_effect = OSError("failed")
    assert detect_system_language(platform="win32") == "en"


def test_persistence_and_system_override(tmp_path: Path) -> None:
    path = tmp_path / "preferences.json"
    service = PreferencesService("en", FilePreferencesStore(path), "zh-CN")
    assert service.get().language == "en"
    assert not path.exists()
    assert service.update("system").resolved_language == "zh-CN"
    assert json.loads(path.read_text(encoding="utf-8")) == {"language": "system"}
    rebuilt = PreferencesService("en", FilePreferencesStore(path), "zh-CN")
    assert rebuilt.get().language == "system"
    assert rebuilt.get().resolved_language == "zh-CN"


@pytest.mark.parametrize("raw", ["{", '{"language":"fr"}', '{"language":"en","extra":1}', "[]"])
def test_invalid_file_is_not_overwritten(tmp_path: Path, raw: str) -> None:
    path = tmp_path / "preferences.json"
    path.write_text(raw, encoding="utf-8")
    assert FilePreferencesStore(path).load() is None
    assert path.read_text(encoding="utf-8") == raw


def test_read_failure_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object, **kwargs: object) -> str:
        raise PermissionError("private path")

    monkeypatch.setattr(Path, "read_text", fail)
    with pytest.raises(PreferenceReadError):
        FilePreferencesStore(tmp_path / "preferences.json").load()


def test_replace_failure_preserves_original(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "preferences.json"
    path.write_text('{"language":"en"}', encoding="utf-8")
    monkeypatch.setattr(
        "agent_relay.infrastructure.preferences.store.os.replace", Mock(side_effect=OSError)
    )
    with pytest.raises(PreferenceWriteError):
        FilePreferencesStore(path).save("zh-CN")
    assert json.loads(path.read_text(encoding="utf-8")) == {"language": "en"}
    assert list(tmp_path.iterdir()) == [path]
