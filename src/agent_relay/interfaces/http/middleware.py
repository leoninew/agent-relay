import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import Request
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from agent_relay.interfaces.http.dependencies import application_settings, get_logger
from agent_relay.interfaces.http.errors import (
    INTERNAL_ERROR_CODE,
    REQUEST_ID_HEADER,
    ensure_request_id,
)
from agent_relay.interfaces.http.transactions import RequestTransaction


class RequestTransactionMiddleware:
    """Own the request's writes and finish them before sending its response."""

    def __init__(
        self, app: ASGIApp, *, transaction_factory: Callable[[], RequestTransaction]
    ) -> None:
        self.app = app
        self.transaction_factory = transaction_factory

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        transaction = self.transaction_factory()
        scope.setdefault("state", {})["database_transaction"] = transaction

        async def send_response(message: Message) -> None:
            if message["type"] == "http.response.start":
                await run_in_threadpool(transaction.finish, commit=message["status"] < 400)
            await send(message)

        try:
            await self.app(scope, receive, send_response)
        finally:
            await run_in_threadpool(transaction.finish, commit=False)


class RequestLoggingMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        exception_handler: Callable[[Request, Exception], Awaitable[Response]],
    ) -> None:
        self.app = app
        self.exception_handler = exception_handler

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        request.state.started_at = time.perf_counter()
        request_id = ensure_request_id(request)
        path = request.url.path
        logger = get_logger(request)
        settings = application_settings(request.app)
        logger.info(settings.logging.request.begin, request_id, request.method, path)
        limit = settings.logging.body.limit
        log_request_body = limit > 0 and is_json_content_type(
            request.headers.get("content-type", "")
        )
        request_body = bytearray()
        response_body = bytearray()
        response_started = False
        log_response_body = False
        status_code = 500

        async def receive_request() -> Message:
            message = await receive()
            if message["type"] == "http.request" and log_request_body:
                request_body.extend(message.get("body", b"")[: max(0, limit - len(request_body))])
                if not message.get("more_body", False) and request_body:
                    logger.info(
                        settings.logging.request.body,
                        request_id,
                        request_body.decode("utf-8", errors="replace"),
                    )
            return message

        async def send_response(message: Message) -> None:
            nonlocal response_started, status_code, log_response_body
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers[REQUEST_ID_HEADER] = request_id
                status_code = message["status"]
                log_response_body = limit > 0 and is_json_content_type(
                    headers.get("content-type", "")
                )
                response_started = True
            elif message["type"] == "http.response.body" and log_response_body:
                response_body.extend(message.get("body", b"")[: max(0, limit - len(response_body))])
            await send(message)

        try:
            await self.app(scope, receive_request, send_response)
        except Exception as exc:
            if response_started:
                request.state.error_kind = INTERNAL_ERROR_CODE
                log_request_failure(
                    logger,
                    exc,
                    settings.logging.request.failed,
                    request,
                    status_code=status_code,
                )
                raise
            response = await self.exception_handler(request, exc)
            await response(scope, receive_request, send_response)

        log_level = log_request_completion(
            logger, settings.logging.request.end, request, status_code
        )
        if response_body:
            logger.log(
                log_level,
                settings.logging.response.body,
                request_id,
                response_body.decode("utf-8", errors="replace"),
            )


def is_json_content_type(content_type: str) -> bool:
    media_type = content_type.split(";", maxsplit=1)[0].strip().lower()
    return media_type == "application/json" or media_type.endswith("+json")


def request_log_fields(request: Request, status_code: int) -> dict[str, object]:
    return {
        "request_id": ensure_request_id(request),
        "method": request.method,
        "path": request.url.path,
        "status": status_code,
        "duration_ms": int((time.perf_counter() - request.state.started_at) * 1000),
        "error_kind": getattr(request.state, "error_kind", None),
    }


def log_request_completion(
    logger: logging.Logger, message: str, request: Request, status_code: int
) -> int:
    log_level = logging.INFO
    if status_code >= 500:
        log_level = logging.ERROR
    elif status_code >= 400:
        log_level = logging.WARNING
    fields = request_log_fields(request, status_code)
    logger.log(
        log_level,
        message,
        fields["request_id"],
        fields["method"],
        fields["path"],
        fields["status"],
        fields["duration_ms"],
        extra=fields,
    )
    return log_level


def log_request_failure(
    logger: logging.Logger,
    exc: Exception,
    message: str,
    request: Request,
    *,
    status_code: int = 500,
) -> None:
    fields = request_log_fields(request, status_code)
    logger.error(
        message,
        fields["request_id"],
        fields["method"],
        fields["path"],
        fields["status"],
        fields["duration_ms"],
        exc_info=(type(exc), exc, exc.__traceback__),
        extra=fields,
    )
