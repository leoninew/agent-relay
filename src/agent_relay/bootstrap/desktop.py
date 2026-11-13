from __future__ import annotations

import importlib
import logging
import socket
import sys
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import uvicorn
from fastapi import FastAPI

from agent_relay.application.desktop.queries import DesktopExitNotificationReader
from agent_relay.application.desktop.service import DesktopExitNotificationService
from agent_relay.application.dto.preferences import ResolvedLanguage
from agent_relay.application.messages.service import MessageService
from agent_relay.application.preferences.service import PreferencesService
from agent_relay.bootstrap.desktop_messages import native_message
from agent_relay.bootstrap.http import build_app
from agent_relay.bootstrap.logging import configure_logging
from agent_relay.bootstrap.paths import load_app_settings, resource_root, user_data_root
from agent_relay.bootstrap.preferences import create_preferences_service
from agent_relay.bootstrap.settings import Settings
from agent_relay.infrastructure.persistence.database import Database
from agent_relay.infrastructure.persistence.dependencies import create_room_store
from agent_relay.infrastructure.preferences.system_language import detect_system_language

logger = logging.getLogger("agent_relay.desktop")
AppFactory = Callable[..., FastAPI]
STARTUP_TIMEOUT_SECONDS = 15
EXIT_NOTIFICATION_SUBMISSION_TIMEOUT_SECONDS = 5


class LocalApiServer:
    def __init__(
        self,
        settings: Settings,
        static_directory: Path,
        *,
        app_factory: AppFactory = build_app,
        preferences_service: PreferencesService | None = None,
    ) -> None:
        self.settings = settings
        self.static_directory = static_directory
        self.app_factory = app_factory
        self.url = ""
        self._listener: socket.socket | None = None
        self._app: FastAPI | None = None
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None
        self._error: BaseException | None = None
        self.preferences_service = preferences_service

    @property
    def app(self) -> FastAPI | None:
        return self._app

    def start(self) -> str:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listener = listener
        try:
            try:
                listener.bind(("127.0.0.1", self.settings.server.port))
            except OSError as exc:
                raise RuntimeError(
                    f"Could not bind the local API to port {self.settings.server.port}: {exc}"
                ) from exc
            listener.listen(socket.SOMAXCONN)
            listener.setblocking(False)
            port = int(listener.getsockname()[1])
            self.url = f"http://127.0.0.1:{port}"

            self._app = self.app_factory(
                settings=self.settings,
                static_directory=self.static_directory,
                **(
                    {"preferences_service": self.preferences_service}
                    if self.preferences_service is not None
                    else {}
                ),
            )
            self._server = uvicorn.Server(
                uvicorn.Config(
                    self._app,
                    host="127.0.0.1",
                    port=port,
                    loop="asyncio:SelectorEventLoop",
                    log_config=None,
                    access_log=False,
                    reload=False,
                )
            )
            self._thread = threading.Thread(
                target=self._serve,
                name="agent-relay-api",
                daemon=True,
            )
            self._thread.start()
            deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
            while time.monotonic() < deadline:
                if self._error is not None:
                    raise RuntimeError("FastAPI failed to start") from self._error
                if self._server.started:
                    return self.url
                if not self._thread.is_alive():
                    raise RuntimeError("FastAPI stopped before becoming ready") from self._error
                time.sleep(0.05)
            raise TimeoutError(
                f"FastAPI did not become ready within {STARTUP_TIMEOUT_SECONDS} seconds"
            )
        except BaseException:
            try:
                self.stop()
            except Exception:
                logger.exception("Failed to clean up the local API after startup failure")
            self._close_database_if_unstarted()
            raise

    def _serve(self) -> None:
        assert self._server is not None
        assert self._listener is not None
        try:
            self._server.run(sockets=[self._listener])
        except BaseException as exc:
            self._error = exc

    def _close_database_if_unstarted(self) -> None:
        if self._server is not None and self._server.started:
            return
        database = getattr(self._app.state, "database", None) if self._app is not None else None
        close = getattr(database, "close", None)
        if callable(close):
            close()

    def stop(self) -> None:
        server = self._server
        thread = self._thread
        if server is not None:
            server.should_exit = True
        if thread is not None and thread.ident is not None:
            thread.join()
        if self._listener is not None:
            self._listener.close()
            self._listener = None

    def __enter__(self) -> LocalApiServer:
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()


def run_desktop(
    *,
    on_confirmed_close: Callable[[], None] | None = None,
    settings: Settings | None = None,
    resources: Path | None = None,
    user_root: Path | None = None,
    webview_api: Any | None = None,
    app_factory: AppFactory = build_app,
) -> None:
    active_user_root = (user_root or user_data_root()).resolve()
    active_resources = (resources or resource_root()).resolve()
    configure_logging(active_user_root)
    configured = settings or load_app_settings(
        user_root=active_user_root,
        resources=active_resources,
    )
    static_directory = configured.static.directory
    if not (static_directory / "index.html").is_file():
        raise FileNotFoundError(f"Built web app not found: {static_directory / 'index.html'}")

    if webview_api is None:
        try:
            webview_api = importlib.import_module("webview")
        except ImportError as exc:
            raise RuntimeError("Install the desktop extra to run the WebView application") from exc

    storage_path = active_user_root / "webview"
    storage_path.mkdir(parents=True, exist_ok=True)
    preferences = create_preferences_service(configured, user_root=active_user_root)
    logger.info("Starting the desktop application")
    started_at = datetime.now(UTC)
    run_id = uuid4().hex
    with LocalApiServer(
        configured,
        static_directory,
        app_factory=app_factory,
        preferences_service=preferences,
    ) as api_server:
        window = webview_api.create_window(
            title="Agent Relay",
            url=f"{api_server.url}/static/",
            width=1200,
            height=800,
            min_size=(900, 600),
            resizable=True,
        )
        if window is None:
            raise RuntimeError("PyWebView did not create the desktop window")

        close_confirmed = False

        def on_closing() -> bool:
            nonlocal close_confirmed
            if close_confirmed:
                return True
            language = _desktop_language(preferences, configured)
            if not window.create_confirmation_dialog(
                native_message(language, "exitTitle"),
                native_message(language, "exitBody"),
            ):
                return False
            close_confirmed = True
            if api_server.app is not None:
                database = getattr(api_server.app.state, "database", None)
                if database is not None:
                    try:
                        _publish_exit_notifications(
                            database,
                            started_at,
                            run_id,
                            native_message(language, "offline"),
                        )
                    except Exception:
                        logger.exception("Unable to finish desktop exit notifications")
            if on_confirmed_close is not None:
                try:
                    on_confirmed_close()
                except Exception:
                    logger.exception("Desktop close callback failed; continuing shutdown")
            return True

        window.events.closing += on_closing
        webview_api.start(
            gui="edgechromium",
            debug=False,
            private_mode=False,
            storage_path=str(storage_path),
            icon=str(active_resources / "assets" / "agent-relay.ico"),
        )
    logger.info("Desktop window closed")


def _desktop_language(preferences: PreferencesService, settings: Settings) -> ResolvedLanguage:
    try:
        return preferences.get().resolved_language
    except Exception:
        logger.warning("Unable to read the current desktop language", exc_info=True)
        return _configured_language(settings)


def _configured_language(settings: Settings) -> ResolvedLanguage:
    configured = settings.preferences.language
    if configured == "system":
        return detect_system_language()
    return configured


def _publish_exit_notifications(
    database: Database,
    started_at: datetime,
    run_id: str,
    content: str,
) -> None:
    store = create_room_store(database)
    notifications = DesktopExitNotificationService(
        DesktopExitNotificationReader(store),
        MessageService(store),
        logger,
    ).publish(started_at=started_at, run_id=run_id, content=content)
    remaining = list(notifications)
    queries = store.queries
    deadline = time.monotonic() + EXIT_NOTIFICATION_SUBMISSION_TIMEOUT_SECONDS
    while remaining:
        for room_id, notification in remaining[:]:
            try:
                saved = queries.message(room_id, notification.id)
            except Exception:
                logger.exception(
                    "Unable to observe desktop exit notification room=%s message=%s",
                    room_id,
                    notification.id,
                )
                remaining.remove((room_id, notification))
                continue
            if all(delivery.status != "pending" for delivery in saved.deliveries):
                remaining.remove((room_id, notification))
        if not remaining:
            return
        if time.monotonic() >= deadline:
            logger.warning(
                "Desktop exit notifications remain unclaimed: %s",
                [(room_id, message.id) for room_id, message in remaining],
            )
            return
        time.sleep(0.05)


def _startup_language(active_user_root: Path) -> ResolvedLanguage:
    try:
        settings = load_app_settings(user_root=active_user_root)
        return (
            create_preferences_service(settings, user_root=active_user_root).get().resolved_language
        )
    except Exception:
        logger.warning("Unable to read preferences for the startup error", exc_info=True)
        return detect_system_language()


def _show_startup_error(
    message: str,
    language: ResolvedLanguage,
    *,
    active_user_root: Path | None = None,
) -> None:
    log_path = (active_user_root or user_data_root()) / "logs" / "agent-relay.log"
    text = (
        f"{native_message(language, 'startupFailed')}\n\n{message}"
        f"\n\n{native_message(language, 'logFile')}: {log_path}"
    )
    if sys.stderr is not None:
        print(text, file=sys.stderr)
        return
    if sys.platform == "win32":
        import ctypes

        windll = getattr(ctypes, "windll", None)
        if windll is not None:
            windll.user32.MessageBoxW(None, text, "Agent Relay", 0x10)


def main() -> None:
    active_user_root = user_data_root()
    try:
        run_desktop()
    except Exception as exc:
        logger.exception("Desktop application startup failed")
        language = _startup_language(active_user_root)
        _show_startup_error(
            str(exc),
            language,
            active_user_root=active_user_root,
        )
        raise SystemExit(1) from None
