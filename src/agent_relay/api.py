import logging
from pathlib import Path

from fastapi import FastAPI

from agent_relay.config import Settings, load_settings
from agent_relay.exception_handlers import register_exception_handlers, unexpected_exception_handler
from agent_relay.middleware import RequestLoggingMiddleware
from agent_relay.routers import api_router
from agent_relay.static_files import mount_static_files


def create_app(
    logger: logging.Logger,
    *,
    settings: Settings | None = None,
    static_directory: Path | None = None,
) -> FastAPI:
    app = FastAPI(title="Agent Relay")
    configure_application_state(app, logger, settings)
    app.add_middleware(RequestLoggingMiddleware, exception_handler=unexpected_exception_handler)
    register_exception_handlers(app)
    app.include_router(api_router)
    mount_static_files(app, directory=static_directory)
    return app


def configure_application_state(
    app: FastAPI,
    logger: logging.Logger,
    settings: Settings | None,
) -> None:
    app.state.logger = logger
    app.state.settings = settings if settings is not None else load_settings()


def build_app(
    *,
    settings: Settings | None = None,
    static_directory: Path | None = None,
) -> FastAPI:
    return create_app(
        logging.getLogger("agent_relay.http"),
        settings=settings,
        static_directory=static_directory,
    )
