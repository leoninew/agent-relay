from collections.abc import Mapping
from http import HTTPStatus
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse

REQUEST_ID_HEADER = "X-Request-Id"
INTERNAL_ERROR_CODE = "internal_error"


def ensure_request_id(request: Request) -> str:
    current = getattr(request.state, "request_id", None)
    if isinstance(current, str) and current:
        return current

    header_value = request.headers.get(REQUEST_ID_HEADER, "").strip()
    request_id = header_value if header_value else f"req_{uuid4().hex}"
    request.state.request_id = request_id
    return request_id


def error_json_response(
    request: Request,
    status_code: int,
    detail: object = None,
    *,
    code: str | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    request_id = ensure_request_id(request)
    try:
        status = HTTPStatus(status_code)
        default_code = INTERNAL_ERROR_CODE if status_code == 500 else status.name.lower()
        message = status.phrase
    except ValueError:
        default_code = INTERNAL_ERROR_CODE if status_code >= 500 else "request_failed"
        message = (
            HTTPStatus.INTERNAL_SERVER_ERROR.phrase if status_code >= 500 else "Request failed"
        )
    if status_code < 500 and isinstance(detail, str) and detail.strip():
        message = detail
    error_code = code or default_code
    request.state.error_kind = error_code
    response = JSONResponse(
        status_code=status_code,
        content={"code": error_code, "error": message, "requestId": request_id},
    )
    if headers:
        for name, value in headers.items():
            response.headers[name] = value
    response.headers[REQUEST_ID_HEADER] = request_id

    return response
