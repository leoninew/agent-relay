from __future__ import annotations

import sys
from collections.abc import Callable
from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from pytest import MonkeyPatch

from agent_relay.bootstrap import desktop
from agent_relay.bootstrap.config import load_settings
from agent_relay.bootstrap.desktop import LocalApiServer, run_desktop
from agent_relay.bootstrap.settings import Settings


def create_test_app(*, settings: Settings, static_directory: Path) -> FastAPI:
    return FastAPI()


class FakeEvent:
    def __init__(self) -> None:
        self.handler: Callable[[], bool] | None = None

    def __iadd__(self, handler: Callable[[], bool]) -> FakeEvent:
        self.handler = handler
        return self

    def fire(self) -> bool:
        assert self.handler is not None
        return self.handler()


class FakeWindow:
    def __init__(self) -> None:
        self.events = type("Events", (), {"closing": FakeEvent()})()
        self.confirmations = [False, True]
        self.dialogs: list[tuple[str, str]] = []

    def create_confirmation_dialog(self, title: str, message: str) -> bool:
        self.dialogs.append((title, message))
        return self.confirmations.pop(0)


class FakeWebView:
    def __init__(self) -> None:
        self.window = FakeWindow()
        self.window_options: dict[str, object] = {}
        self.start_options: dict[str, object] = {}

    def create_window(self, **kwargs: object) -> FakeWindow:
        self.window_options = kwargs
        return self.window

    def start(self, **kwargs: object) -> None:
        self.start_options = kwargs
        assert self.window.events.closing.fire() is False
        assert self.window.events.closing.fire() is True
        assert self.window.events.closing.fire() is True


def test_local_api_server_prebinds_before_building_and_stops(monkeypatch: MonkeyPatch) -> None:
    listener = Mock()
    listener.getsockname.return_value = ("127.0.0.1", 19080)
    uvicorn_server = Mock(started=True)
    thread = Mock()
    monkeypatch.setattr("agent_relay.bootstrap.desktop.socket.socket", lambda *_: listener)
    monkeypatch.setattr("agent_relay.bootstrap.desktop.uvicorn.Server", lambda _: uvicorn_server)
    monkeypatch.setattr("agent_relay.bootstrap.desktop.threading.Thread", lambda **_: thread)
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
    monkeypatch.setattr("agent_relay.bootstrap.desktop.socket.socket", lambda *_: listener)
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
    monkeypatch.setattr("agent_relay.bootstrap.desktop.socket.socket", lambda *_: listener)
    settings = load_settings().model_copy(
        update={"server": load_settings().server.model_copy(update={"port": 0})}
    )

    def fail_app(**_kwargs: object) -> FastAPI:
        raise RuntimeError("invalid app configuration")

    server = LocalApiServer(settings, Path("static"), app_factory=fail_app)
    with pytest.raises(RuntimeError, match="invalid app configuration"):
        server.start()

    listener.close.assert_called_once()


@pytest.mark.parametrize("fail_notification", [False, True])
def test_run_desktop_persists_webview_and_confirms_close(
    tmp_path: Path, monkeypatch: MonkeyPatch, fail_notification: bool
) -> None:
    static_directory = tmp_path / "web" / "dist"
    static_directory.mkdir(parents=True)
    (static_directory / "index.html").write_text("ready", encoding="utf-8")
    base = load_settings()
    settings = base.model_copy(
        update={
            "server": base.server.model_copy(update={"port": 0}),
            "static": base.static.model_copy(update={"directory": static_directory}),
        }
    )
    webview = FakeWebView()
    callback_calls = 0
    notifications = Mock()
    if fail_notification:
        notifications.side_effect = RuntimeError("notification unavailable")

    def app_with_database(**kwargs: object) -> FastAPI:
        app = FastAPI()
        app.state.database = Mock()
        return app

    original_start = webview.start

    def start(**kwargs: object) -> None:
        assert webview.window.events.closing.fire() is False
        notifications.assert_not_called()
        webview.window.confirmations = [False, True]
        original_start(**kwargs)

    def on_confirmed_close() -> None:
        nonlocal callback_calls
        callback_calls += 1

    monkeypatch.setattr("agent_relay.bootstrap.desktop.configure_logging", lambda *_: None)
    monkeypatch.setattr("agent_relay.bootstrap.desktop._publish_exit_notifications", notifications)
    monkeypatch.setattr(webview, "start", start)
    api_server = Mock()
    api_server.__enter__ = Mock(return_value=api_server)
    api_server.__exit__ = Mock(return_value=False)
    api_server.url = "http://127.0.0.1:19080"
    api_server.app = app_with_database()
    monkeypatch.setattr("agent_relay.bootstrap.desktop.LocalApiServer", lambda *_, **__: api_server)

    run_desktop(
        settings=settings,
        user_root=tmp_path / "user data",
        resources=tmp_path / "resources",
        webview_api=webview,
        app_factory=app_with_database,
        on_confirmed_close=on_confirmed_close,
    )

    assert str(webview.window_options["url"]).endswith("/static/")
    assert webview.start_options["gui"] == "edgechromium"
    assert webview.start_options["private_mode"] is False
    assert Path(str(webview.start_options["storage_path"])) == tmp_path / "user data" / "webview"
    assert Path(str(webview.start_options["icon"])) == (
        tmp_path / "resources" / "assets" / "agent-relay.ico"
    )
    assert callback_calls == 1
    notifications.assert_called_once()


def test_run_desktop_reads_current_preferences_for_exit(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    static_directory = tmp_path / "web" / "dist"
    static_directory.mkdir(parents=True)
    (static_directory / "index.html").write_text("ready", encoding="utf-8")
    user_root = tmp_path / "user data"
    user_root.mkdir()
    preferences_path = user_root / "preferences.json"
    preferences_path.write_text('{"language":"en"}', encoding="utf-8")
    base = load_settings()
    settings = base.model_copy(
        update={
            "server": base.server.model_copy(update={"port": 0}),
            "static": base.static.model_copy(update={"directory": static_directory}),
        }
    )
    webview = FakeWebView()
    notifications = Mock()
    injected: dict[str, object] = {}

    def start(**kwargs: object) -> None:
        assert webview.window.events.closing.fire() is False
        preferences_path.write_text('{"language":"zh-CN"}', encoding="utf-8")
        assert webview.window.events.closing.fire() is True
        webview.start_options = kwargs

    class ApiServer:
        url = "http://127.0.0.1:19080"
        app = None

        def __init__(self, *args: object, **kwargs: object) -> None:
            injected.update(kwargs)

        def __enter__(self) -> ApiServer:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    monkeypatch.setattr("agent_relay.bootstrap.desktop.configure_logging", lambda *_: None)
    monkeypatch.setattr("agent_relay.bootstrap.desktop._publish_exit_notifications", notifications)
    monkeypatch.setattr(webview, "start", start)
    monkeypatch.setattr("agent_relay.bootstrap.desktop.LocalApiServer", ApiServer)

    run_desktop(
        settings=settings,
        user_root=user_root,
        resources=tmp_path / "resources",
        webview_api=webview,
    )

    assert webview.window.dialogs == [
        ("Exit Agent Relay", "Close the management app?"),
        ("退出 Agent Relay", "确定要关闭管理端吗？"),
    ]
    assert injected["preferences_service"] is not None


def test_exit_notification_uses_current_language(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    static_directory = tmp_path / "web" / "dist"
    static_directory.mkdir(parents=True)
    (static_directory / "index.html").write_text("ready", encoding="utf-8")
    user_root = tmp_path / "user data"
    user_root.mkdir()
    (user_root / "preferences.json").write_text('{"language":"en"}', encoding="utf-8")
    base = load_settings()
    settings = base.model_copy(
        update={
            "server": base.server.model_copy(update={"port": 0}),
            "static": base.static.model_copy(update={"directory": static_directory}),
        }
    )
    webview = FakeWebView()
    notifications = Mock()

    original_start = webview.start

    def start(**kwargs: object) -> None:
        assert webview.window.events.closing.fire() is False
        webview.window.confirmations = [False, True]
        original_start(**kwargs)

    def app_with_database(**kwargs: object) -> FastAPI:
        app = FastAPI()
        app.state.database = Mock()
        return app

    monkeypatch.setattr("agent_relay.bootstrap.desktop.configure_logging", lambda *_: None)
    monkeypatch.setattr("agent_relay.bootstrap.desktop._publish_exit_notifications", notifications)
    monkeypatch.setattr(webview, "start", start)
    api_server = Mock()
    api_server.__enter__ = Mock(return_value=api_server)
    api_server.__exit__ = Mock(return_value=False)
    api_server.url = "http://127.0.0.1:19080"
    api_server.app = app_with_database()
    monkeypatch.setattr("agent_relay.bootstrap.desktop.LocalApiServer", lambda *_, **__: api_server)

    run_desktop(
        settings=settings,
        user_root=user_root,
        resources=tmp_path / "resources",
        webview_api=webview,
        app_factory=app_with_database,
    )

    notifications.assert_called_once()
    assert notifications.call_args.args[3] == "The management app is offline."


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
    monkeypatch.setattr("agent_relay.bootstrap.desktop.time.sleep", sleep)
    monkeypatch.setattr(
        "agent_relay.bootstrap.desktop.time.monotonic",
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
    import_module("agent_relay.desktop")
    import_module("agent_relay.server")

    assert "webview" not in sys.modules


def test_desktop_language_falls_back_to_config(monkeypatch: MonkeyPatch) -> None:
    settings = load_settings().model_copy(
        update={"preferences": load_settings().preferences.model_copy(update={"language": "zh-CN"})}
    )
    preferences = Mock()
    preferences.get.side_effect = OSError("unreadable")
    assert desktop._desktop_language(preferences, settings) == "zh-CN"
