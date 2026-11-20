import sys
from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from pytest import MonkeyPatch

from conflua.bootstrap import desktop
from conflua.bootstrap.config import load_settings
from conflua.bootstrap.desktop import LocalApiServer
from conflua.bootstrap.settings import Settings


def create_test_app(*, settings: Settings, static_directory: Path) -> FastAPI:
    return FastAPI()


def test_local_api_server_prebinds_before_building_and_stops(monkeypatch: MonkeyPatch) -> None:
    listener = Mock()
    listener.getsockname.return_value = ("127.0.0.1", 19080)
    uvicorn_server = Mock(started=True)
    thread = Mock()
    monkeypatch.setattr("conflua.bootstrap.desktop.socket.socket", lambda *_: listener)
    monkeypatch.setattr("conflua.bootstrap.desktop.uvicorn.Server", lambda _: uvicorn_server)
    monkeypatch.setattr("conflua.bootstrap.desktop.threading.Thread", lambda **_: thread)
    settings = load_settings()

    def app_factory(**kwargs: object) -> FastAPI:
        listener.bind.assert_called_once_with(("127.0.0.1", 0))
        return FastAPI()

    server = LocalApiServer(
        settings.model_copy(update={"server": settings.server.model_copy(update={"port": 0})}),
        Path("static"),
        app_factory=app_factory,
    )

    with server:
        assert server.url == "http://127.0.0.1:19080"
        thread.start.assert_called_once()

    assert uvicorn_server.should_exit is True
    thread.join.assert_called_once_with()
    listener.close.assert_called_once()


def test_local_api_server_reports_port_conflict(monkeypatch: MonkeyPatch) -> None:
    listener = Mock()
    listener.bind.side_effect = OSError("address in use")
    monkeypatch.setattr("conflua.bootstrap.desktop.socket.socket", lambda *_: listener)
    settings = load_settings().model_copy(
        update={"server": load_settings().server.model_copy(update={"port": 0})}
    )
    conflicting = LocalApiServer(
        settings,
        Path("static"),
        app_factory=create_test_app,
    )
    with pytest.raises(RuntimeError, match="address in use"):
        conflicting.start()
    listener.close.assert_called_once()


def test_local_api_server_releases_listener_when_app_creation_fails(
    monkeypatch: MonkeyPatch,
) -> None:
    listener = Mock()
    listener.getsockname.return_value = ("127.0.0.1", 19080)
    monkeypatch.setattr("conflua.bootstrap.desktop.socket.socket", lambda *_: listener)
    settings = load_settings().model_copy(
        update={"server": load_settings().server.model_copy(update={"port": 0})}
    )

    def fail_app(**_kwargs: object) -> FastAPI:
        raise RuntimeError("invalid app configuration")

    server = LocalApiServer(settings, Path("static"), app_factory=fail_app)
    with pytest.raises(RuntimeError, match="invalid app configuration"):
        server.start()

    listener.close.assert_called_once()


@pytest.mark.parametrize("scenario", ["claimed", "unclaimed", "empty", "read-error"])
def test_exit_notifications_bound_wait_without_waiting_for_receipts(
    monkeypatch: MonkeyPatch, scenario: str
) -> None:
    notification = Mock(id="offline-message")
    notifications = Mock()
    notifications.publish.return_value = [] if scenario == "empty" else [("room-one", notification)]
    queries = Mock()
    if scenario == "read-error":
        queries.message.side_effect = RuntimeError("database read failed")
    else:
        queries.message.side_effect = [
            Mock(deliveries=[Mock(status="pending")]),
            Mock(deliveries=[Mock(status="submitting")]),
        ]
    sleep = Mock()
    logger = Mock()
    monkeypatch.setattr(desktop, "DesktopExitNotificationService", lambda *_: notifications)
    monkeypatch.setattr(desktop, "DesktopExitNotificationReader", lambda _: Mock())
    monkeypatch.setattr(desktop, "create_room_store", lambda _: Mock(queries=queries))
    monkeypatch.setattr("conflua.bootstrap.desktop.time.sleep", sleep)
    monkeypatch.setattr(
        "conflua.bootstrap.desktop.time.monotonic",
        Mock(side_effect=[0, 6 if scenario == "unclaimed" else 0.1]),
    )
    monkeypatch.setattr(desktop, "logger", logger)
    started_at = datetime(2026, 11, 12, tzinfo=UTC)

    desktop._publish_exit_notifications(Mock(), started_at, "run-one", "offline")

    notifications.publish.assert_called_once_with(
        started_at=started_at, run_id="run-one", content="offline"
    )
    assert queries.message.call_count == (
        0 if scenario == "empty" else 2 if scenario == "claimed" else 1
    )
    assert sleep.call_count == (1 if scenario == "claimed" else 0)
    assert logger.warning.call_count == (1 if scenario == "unclaimed" else 0)
    assert logger.exception.call_count == (1 if scenario == "read-error" else 0)


def test_desktop_modules_do_not_import_pywebview_until_startup() -> None:
    import_module("conflua.desktop")
    import_module("conflua.server")

    assert "webview" not in sys.modules


def test_desktop_language_falls_back_to_config(monkeypatch: MonkeyPatch) -> None:
    settings = load_settings().model_copy(
        update={"preferences": load_settings().preferences.model_copy(update={"language": "zh-CN"})}
    )
    preferences = Mock()
    preferences.get.side_effect = OSError("unreadable")
    assert desktop._desktop_language(preferences, settings) == "zh-CN"
