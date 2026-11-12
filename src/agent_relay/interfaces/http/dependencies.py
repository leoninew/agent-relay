import logging
from typing import cast

from fastapi import FastAPI, Request

from agent_relay.bootstrap.settings import Settings


def application_settings(app: FastAPI) -> Settings:
    return cast(Settings, app.state.settings)


def get_logger(request: Request) -> logging.Logger:
    return cast(logging.Logger, request.app.state.logger)
