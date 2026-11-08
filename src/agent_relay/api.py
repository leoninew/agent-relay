import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from agent_relay.config import Settings, load_settings
from agent_relay.delivery_service import DeliveryService, QueueDriver
from agent_relay.drivers.codex import CodexDriver
from agent_relay.exception_handlers import register_exception_handlers, unexpected_exception_handler
from agent_relay.member_sessions import MemberSessions, SessionDriver
from agent_relay.middleware import RequestLoggingMiddleware, RequestTransactionMiddleware
from agent_relay.migrations import run_migrations
from agent_relay.room_service import RoomService
from agent_relay.room_store import SQLiteRoomStore
from agent_relay.routers import api_router
from agent_relay.static_files import mount_static_files


def create_app(
    logger: logging.Logger,
    *,
    settings: Settings | None = None,
    static_directory: Path | None = None,
    room_service: RoomService | None = None,
    session_driver: SessionDriver | None = None,
    queue_driver: QueueDriver | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.delivery_service.start()
        try:
            yield
        finally:
            from starlette.concurrency import run_in_threadpool

            await run_in_threadpool(app.state.delivery_service.close)

    app = FastAPI(title="Agent Relay", lifespan=lifespan)
    configure_application_state(app, logger, settings, room_service, session_driver, queue_driver)
    app.add_middleware(RequestTransactionMiddleware, store=app.state.room_service.store)
    app.add_middleware(RequestLoggingMiddleware, exception_handler=unexpected_exception_handler)
    register_exception_handlers(app)
    app.include_router(api_router)
    mount_static_files(app, directory=static_directory)
    return app


def configure_application_state(
    app: FastAPI,
    logger: logging.Logger,
    settings: Settings | None,
    room_service: RoomService | None,
    session_driver: SessionDriver | None,
    queue_driver: QueueDriver | None,
) -> None:
    app.state.logger = logger
    app.state.settings = settings if settings is not None else load_settings()
    if room_service is None and app.state.settings.database.migrate_on_startup:
        run_migrations(app.state.settings.database.path)
    store = (
        room_service.store
        if room_service is not None
        else SQLiteRoomStore(app.state.settings.database.path)
    )
    app.state.room_service = room_service if room_service is not None else RoomService(store)
    codex = app.state.settings.codex
    driver = (
        session_driver
        if session_driver is not None
        else CodexDriver(codex.command, codex.rpc_timeout)
    )
    app.state.member_sessions = MemberSessions(store, driver)
    app.state.delivery_service = DeliveryService(
        store,
        queue_driver if queue_driver is not None else CodexDriver(codex.command, codex.rpc_timeout),
        logger,
        codex.queue_concurrency,
        str(app.state.settings.server.public_url),
    )


def build_app(
    *,
    settings: Settings | None = None,
    static_directory: Path | None = None,
    room_service: RoomService | None = None,
    session_driver: SessionDriver | None = None,
    queue_driver: QueueDriver | None = None,
) -> FastAPI:
    return create_app(
        logging.getLogger("agent_relay.http"),
        settings=settings,
        static_directory=static_directory,
        room_service=room_service,
        session_driver=session_driver,
        queue_driver=queue_driver,
    )
