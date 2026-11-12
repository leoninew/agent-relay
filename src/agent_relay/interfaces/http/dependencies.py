import logging
from typing import cast

from fastapi import Request
from starlette.requests import HTTPConnection

from agent_relay.interfaces.dto import HttpDependencies


def get_http_dependencies(connection: HTTPConnection) -> HttpDependencies:
    return cast(HttpDependencies, connection.app.state.http_dependencies)


def get_logger(request: Request) -> logging.Logger:
    return cast(logging.Logger, request.app.state.logger)
