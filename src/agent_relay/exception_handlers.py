from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from agent_relay.dependencies import application_settings, get_logger
from agent_relay.errors import error_json_response
from agent_relay.middleware import log_request_failure
from agent_relay.room_service import RoomConflictError, RoomInputError, RoomNotFoundError


def register_exception_handlers(app: FastAPI) -> None:
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
        get_logger(request), exc, application_settings(request.app).logging.request.failed, request
    )
    return response
