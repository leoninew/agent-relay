from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from agent_relay.application.capabilities.ports import CapabilityUnavailableError
from agent_relay.application.members.sessions import SessionUnavailableError
from agent_relay.domain.rooms.errors import (
    RoomConflictError,
    RoomInputError,
    RoomNotFoundError,
)
from agent_relay.interfaces.http.dependencies import get_http_dependencies, get_logger
from agent_relay.interfaces.http.errors import error_json_response
from agent_relay.interfaces.http.middleware import log_request_failure


def register_exception_handlers(app: FastAPI) -> None:
    app.exception_handler(SessionUnavailableError)(session_unavailable_handler)
    app.exception_handler(CapabilityUnavailableError)(session_unavailable_handler)
    app.exception_handler(StarletteHTTPException)(http_exception_handler)
    app.exception_handler(RequestValidationError)(request_validation_exception_handler)
    for error_type in (RoomNotFoundError, RoomConflictError, RoomInputError):
        app.exception_handler(error_type)(room_exception_handler)


async def room_exception_handler(
    request: Request,
    exc: RoomNotFoundError | RoomConflictError | RoomInputError,
) -> JSONResponse:
    if isinstance(exc, RoomNotFoundError):
        status_code = 404
    elif isinstance(exc, RoomConflictError):
        status_code = 409
    else:
        status_code = 422
    return error_json_response(request, status_code, str(exc))


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    return error_json_response(
        request,
        exc.status_code,
        exc.detail,
        headers=exc.headers,
    )


async def request_validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return error_json_response(request, 422, "Validation error", code="validation_error")


async def unexpected_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    response = error_json_response(request, 500)
    log_request_failure(
        get_logger(request), exc, get_http_dependencies(request).logging.request_failed, request
    )
    return response


async def session_unavailable_handler(
    request: Request, exc: SessionUnavailableError | CapabilityUnavailableError
) -> JSONResponse:
    response = error_json_response(request, 503)
    get_logger(request).error(
        "Codex metadata unavailable request_id=%s", response.headers["X-Request-Id"], exc_info=exc
    )
    return response
