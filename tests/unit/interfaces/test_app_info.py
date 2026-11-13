import tomllib
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from unittest.mock import Mock

import pytest

from agent_relay.interfaces.http.app_info import get_app_info


def test_app_info_uses_distribution_version(monkeypatch: pytest.MonkeyPatch) -> None:
    lookup = Mock(return_value="1.2.3")
    monkeypatch.setattr("agent_relay.interfaces.http.app_info.version", lookup)
    assert get_app_info().model_dump() == {"version": "1.2.3"}
    lookup.assert_called_once_with("agent-relay")


def test_app_info_handles_missing_distribution(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "agent_relay.interfaces.http.app_info.version", Mock(side_effect=PackageNotFoundError)
    )
    assert get_app_info().model_dump() == {"version": None}


def test_installed_version_matches_project() -> None:
    project = tomllib.loads(
        (Path(__file__).resolve().parents[3] / "pyproject.toml").read_text(encoding="utf-8")
    )
    assert get_app_info().version == project["project"]["version"]
