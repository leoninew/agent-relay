import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from starlette.concurrency import run_in_threadpool

from agent_relay.application.delivery.ports import QueueDriver
from agent_relay.application.members.sessions import SessionDriver
from agent_relay.bootstrap.config import Settings, load_settings
from agent_relay.infrastructure.codex.dependencies import create_queue_driver, create_session_driver
from agent_relay.infrastructure.dispatch.dependencies import (
    create_delivery_runner,
    create_presence_runner,
)
from agent_relay.infrastructure.persistence.dependencies import create_database
from agent_relay.infrastructure.persistence.store import SQLiteRoomStore
from agent_relay.interfaces.http.exception_handlers import (
    register_exception_handlers,
    unexpected_exception_handler,
)
from agent_relay.interfaces.http.middleware import (
    RequestLoggingMiddleware,
    RequestTransactionMiddleware,
)
from agent_relay.interfaces.http.routes import api_router
from agent_relay.interfaces.http.static_files import mount_static_files


def create_app(
    logger: logging.Logger,
    *,
    settings: Settings | None = None,
    static_directory: Path | None = None,
    store: SQLiteRoomStore | None = None,
    session_driver: SessionDriver | None = None,
    queue_driver: QueueDriver | None = None,
) -> FastAPI:
    configured = settings if settings is not None else load_settings()
    database = (
        store
        if store is not None
        else create_database(
            configured.database.path, migrate_on_startup=configured.database.migrate_on_startup
        )
    )
    codex = configured.codex
    sessions = (
        session_driver
        if session_driver is not None
        else create_session_driver(codex.command, codex.rpc_timeout)
    )
    queue = (
        queue_driver
        if queue_driver is not None
        else create_queue_driver(codex.command, codex.rpc_timeout)
    )
    delivery_runner = create_delivery_runner(database, queue, logger, codex.queue_concurrency)
    presence_runner = create_presence_runner(database, sessions, logger)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        delivery_runner.start()
        try:
            presence_runner.start()
            try:
                yield
            finally:
                await run_in_threadpool(presence_runner.close)
        finally:
            await run_in_threadpool(delivery_runner.close)

    app = FastAPI(title="Agent Relay", lifespan=lifespan)
    app.state.logger = logger
    app.state.settings = configured
    app.state.database = database
    app.state.session_driver = sessions
    app.state.delivery_runner = delivery_runner
    app.state.presence_runner = presence_runner
    app.add_middleware(
        RequestTransactionMiddleware, transaction_factory=database.request_transaction
    )
    app.add_middleware(RequestLoggingMiddleware, exception_handler=unexpected_exception_handler)
    register_exception_handlers(app)
    app.include_router(api_router)
    mount_static_files(app, directory=static_directory)
    return app


def build_app(
    *,
    settings: Settings | None = None,
    static_directory: Path | None = None,
    store: SQLiteRoomStore | None = None,
    session_driver: SessionDriver | None = None,
    queue_driver: QueueDriver | None = None,
) -> FastAPI:
    return create_app(
        logging.getLogger("agent_relay.http"),
        settings=settings,
        static_directory=static_directory,
        store=store,
        session_driver=session_driver,
        queue_driver=queue_driver,
    )
