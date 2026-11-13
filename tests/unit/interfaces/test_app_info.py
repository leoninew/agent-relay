import tomllib
from pathlib import Path

import pytest

from agent_relay.interfaces.http.app_info import get_app_info


def test_app_info_uses_runtime_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("agent_relay.interfaces.http.app_info.__version__", "1.2.3")
    assert get_app_info().model_dump() == {"version": "1.2.3"}


def test_runtime_version_matches_project() -> None:
    project = tomllib.loads(
        (Path(__file__).resolve().parents[3] / "pyproject.toml").read_text(encoding="utf-8")
    )
    assert get_app_info().version == project["project"]["version"]
