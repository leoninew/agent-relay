import json

import pytest
from starlette.requests import Request

from agent_relay.interfaces.http.errors import error_json_response


@pytest.mark.parametrize(
    ("status_code", "code", "headers"),
    [
        (401, "unauthorized", {}),
        (403, "forbidden", {}),
        (409, "conflict", {}),
        (500, "internal_error", {}),
        (503, "service_unavailable", {"Retry-After": "30"}),
        (504, "gateway_timeout", {}),
    ],
)
def test_error_response_keeps_status_headers_and_safe_summary(
    status_code: int, code: str, headers: dict[str, str]
) -> None:
    request = Request({"type": "http", "headers": [(b"x-request-id", b"req_error")]})
    detail = "private upstream diagnostic" if status_code >= 500 else "Request rejected"
    response = error_json_response(request, status_code, detail, headers=headers)

    assert response.status_code == status_code
    for name, value in headers.items():
        assert response.headers[name] == value
    payload = json.loads(bytes(response.body))
    assert payload["code"] == request.state.error_kind == code
    assert payload["requestId"] == response.headers["X-Request-Id"] == "req_error"
    assert "private upstream diagnostic" not in payload["error"]
    if status_code < 500:
        assert payload["error"] == "Request rejected"
