import logging
import os
import subprocess
import sys
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from agent_relay.application.greeting import GreetingService
from agent_relay.bootstrap.config import load_settings
from agent_relay.bootstrap.http import create_app
from agent_relay.interfaces.http.dependencies import get_greeting_service

pytestmark = pytest.mark.usefixtures("migrated_database")


@contextmanager
def api_client(test_app: FastAPI | None = None) -> Iterator[TestClient]:
    target_app = (
        test_app if test_app is not None else create_app(logging.getLogger("tests.agent_relay"))
    )
    with TestClient(target_app) as client:
        yield client


def test_importing_application_modules_does_not_require_runtime_config(tmp_path: Path) -> None:
    subprocess.run(
        [sys.executable, "-c", "import agent_relay.bootstrap.http; import agent_relay.server"],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).parents[2] / "src")},
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_greet_returns_unwrapped_success_response() -> None:
    with api_client() as client:
        response = client.get("/api/greet?name=Ada")

    assert response.status_code == 200
    assert response.json() == {"text": "Hello, Ada!"}


def test_static_files_serve_spa_routes_and_assets(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    static_dir = tmp_path / "static"
    assets_dir = static_dir / "assets"
    assets_dir.mkdir(parents=True)
    (static_dir / "index.html").write_text('<div id="app"></div>', encoding="utf-8")
    (assets_dir / "app.js").write_text("console.log('ready')", encoding="utf-8")
    base_settings = load_settings(Path(__file__).parents[2])
    test_settings = base_settings.model_copy(
        update={"static": base_settings.static.model_copy(update={"directory": Path("./static")})}
    )
    test_app = create_app(logging.getLogger("tests.agent_relay.static"), settings=test_settings)

    with api_client(test_app) as client:
        index_response = client.get("/static/")
        route_response = client.get("/static/notifications")
        asset_response = client.get("/static/assets/app.js")
        missing_asset_response = client.get("/static/assets/missing.js")

    assert index_response.status_code == 200
    assert index_response.text == '<div id="app"></div>'
    assert route_response.status_code == 200
    assert route_response.text == '<div id="app"></div>'
    assert asset_response.status_code == 200
    assert asset_response.text == "console.log('ready')"
    assert missing_asset_response.status_code == 404


@pytest.mark.parametrize("body_log_limit", ["-1", "invalid"])
def test_load_settings_rejects_invalid_body_log_limit(
    monkeypatch: MonkeyPatch,
    body_log_limit: str,
) -> None:
    monkeypatch.setenv("AGENT_RELAY_LOGGING__BODY__LIMIT", body_log_limit)

    with pytest.raises(ValueError, match="logging.body.limit"):
        load_settings()


def test_load_settings_allows_zero_body_log_limit(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_RELAY_LOGGING__BODY__LIMIT", "0")

    assert load_settings().logging.body.limit == 0


def test_greet_uses_application_settings_without_reloading_config(monkeypatch: MonkeyPatch) -> None:
    base_settings = load_settings()
    test_settings = base_settings.model_copy(
        update={"greeting": base_settings.greeting.model_copy(update={"prefix": "Hi"})}
    )
    test_app = create_app(logging.getLogger("tests.agent_relay.settings"), settings=test_settings)
    monkeypatch.setenv("AGENT_RELAY_GREETING__PREFIX", "Bonjour")

    with api_client(test_app) as client:
        response = client.get("/api/greet?name=Ada")

    assert response.json() == {"text": "Hi, Ada!"}


def test_greet_uses_fastapi_dependency_override() -> None:
    test_app = create_app(logging.getLogger("tests.agent_relay.dependencies"))
    test_app.dependency_overrides[get_greeting_service] = lambda: GreetingService("Welcome")

    with api_client(test_app) as client:
        response = client.get("/api/greet?name=Ada")

    assert response.status_code == 200
    assert response.json() == {"text": "Welcome, Ada!"}


def test_greet_propagates_request_id_header() -> None:
    with api_client() as client:
        response = client.get("/api/greet?name=Ada", headers={"X-Request-Id": "req_success"})

    assert response.status_code == 200
    assert response.headers["X-Request-Id"] == "req_success"


def test_greet_logs_request_lifecycle_without_query_string(caplog: Any) -> None:
    test_logger = logging.getLogger("tests.agent_relay.http")
    test_app = create_app(test_logger)
    with caplog.at_level(logging.INFO, logger=test_logger.name), api_client(test_app) as client:
        response = client.get("/api/greet?name=Ada", headers={"X-Request-Id": "req_log"})

    assert response.status_code == 200
    started_record = only_record_with_message(caplog.records, "Request begin")
    assert "request_id=req_log" in started_record.getMessage()
    assert "method=GET path=/api/greet" in started_record.getMessage()

    completed_record = only_record_with_message(caplog.records, "Request end")
    assert log_value(completed_record, "request_id") == "req_log"

    assert log_value(completed_record, "method") == "GET"
    assert log_value(completed_record, "path") == "/api/greet"
    assert log_value(completed_record, "status") == 200
    assert isinstance(log_value(completed_record, "duration_ms"), int)
    assert "method=GET path=/api/greet status=200" in completed_record.getMessage()

    response_record = only_record_with_message(caplog.records, "Response body")
    assert "request_id=req_log" in response_record.getMessage()
    assert '"text":"Hello, Ada!"' in response_record.getMessage()


def test_greet_maps_blank_name_to_validation_error() -> None:
    with api_client() as client:
        response = client.get("/api/greet?name=   ", headers={"X-Request-Id": "req_blank"})

    body = response.json()
    assert response.status_code == 422
    assert body == {
        "code": "validation_error",
        "error": "Validation error",
        "requestId": "req_blank",
    }
    assert response.headers["X-Request-Id"] == body["requestId"]


def test_greet_logs_validation_status(caplog: Any) -> None:
    test_logger = logging.getLogger("tests.agent_relay.http.validation")
    test_app = create_app(test_logger)
    with caplog.at_level(logging.INFO, logger=test_logger.name), api_client(test_app) as client:
        response = client.get("/api/greet?name=   ", headers={"X-Request-Id": "req_blank_log"})

    assert response.status_code == 422
    record = only_record_with_message(caplog.records, "Request end")
    assert record.levelno == logging.WARNING
    assert log_value(record, "request_id") == "req_blank_log"
    assert log_value(record, "status") == 422

    assert record.getMessage().startswith("Request end request_id=req_blank_log")


def test_greet_maps_missing_name_to_validation_error() -> None:
    with api_client() as client:
        response = client.get("/api/greet", headers={"X-Request-Id": "req_validation"})

    body = response.json()
    assert response.status_code == 422
    assert body == {
        "code": "validation_error",
        "error": "Validation error",
        "requestId": "req_validation",
    }


def test_http_exception_uses_status_mapping_and_string_detail() -> None:
    test_app = create_app(logging.getLogger("tests.agent_relay.http_exception"))

    @test_app.get("/api/diagnostics/not-found")
    def diagnostic_not_found() -> None:
        raise HTTPException(status_code=404, detail="Greeting not found")

    with api_client(test_app) as client:
        response = client.get(
            "/api/diagnostics/not-found",
            headers={"X-Request-Id": "req_not_found"},
        )

    assert response.status_code == 404
    assert response.json() == {
        "code": "not_found",
        "error": "Greeting not found",
        "requestId": "req_not_found",
    }
    assert response.headers["X-Request-Id"] == "req_not_found"


def test_method_not_allowed_preserves_allow_header_and_status_mapping() -> None:
    with api_client() as client:
        response = client.post("/api/greet", headers={"X-Request-Id": "req_method"})

    assert response.status_code == 405
    assert response.json() == {
        "code": "method_not_allowed",
        "error": "Method Not Allowed",
        "requestId": "req_method",
    }
    assert response.headers["allow"] == "GET"
    assert response.headers["X-Request-Id"] == "req_method"


def test_request_logging_logs_and_truncates_json_bodies(caplog: Any) -> None:
    test_logger = logging.getLogger("tests.agent_relay.http.body")
    base_settings = load_settings()
    test_settings = base_settings.model_copy(
        update={
            "logging": base_settings.logging.model_copy(
                update={"body": base_settings.logging.body.model_copy(update={"limit": 12})}
            )
        }
    )
    test_app = create_app(test_logger, settings=test_settings)

    @test_app.post("/api/diagnostics/echo")
    def echo(payload: dict[str, str]) -> dict[str, dict[str, str]]:
        return {"received": payload}

    with caplog.at_level(logging.INFO, logger=test_logger.name), api_client(test_app) as client:
        response = client.post(
            "/api/diagnostics/echo",
            headers={"X-Request-Id": "req_body"},
            json={"name": "demo"},
        )

    assert response.status_code == 200
    assert response.json() == {"received": {"name": "demo"}}
    request_record = only_record_with_message(caplog.records, "Request body")
    response_record = only_record_with_message(caplog.records, "Response body")
    assert request_record.levelno == logging.INFO
    assert request_record.getMessage() == 'Request body request_id=req_body body={"name":"dem'
    assert response_record.levelno == logging.INFO
    assert response_record.getMessage() == 'Response body request_id=req_body body={"received":'

    messages = [record.getMessage() for record in caplog.records]
    request_end_message = next(
        message for message in messages if message.startswith("Request end ")
    )
    assert messages.index(request_record.getMessage()) < messages.index(request_end_message)
    assert messages.index(request_end_message) < messages.index(response_record.getMessage())


def test_request_logging_skips_json_bodies_when_limit_is_zero(caplog: Any) -> None:
    test_logger = logging.getLogger("tests.agent_relay.http.body_disabled")
    base_settings = load_settings()
    test_settings = base_settings.model_copy(
        update={
            "logging": base_settings.logging.model_copy(
                update={"body": base_settings.logging.body.model_copy(update={"limit": 0})}
            )
        }
    )
    test_app = create_app(test_logger, settings=test_settings)

    @test_app.post("/api/diagnostics/echo")
    def echo(payload: dict[str, str]) -> dict[str, dict[str, str]]:
        return {"received": payload}

    with caplog.at_level(logging.INFO, logger=test_logger.name), api_client(test_app) as client:
        response = client.post("/api/diagnostics/echo", json={"name": "demo"})

    assert response.status_code == 200
    assert not [
        record
        for record in caplog.records
        if record.getMessage().startswith(("Request body", "Response body"))
    ]


def test_diagnostic_exception_maps_to_internal_error() -> None:
    with api_client() as client:
        response = client.get(
            "/api/diagnostics/exception",
            headers={"X-Request-Id": "req_exception"},
        )

    body = response.json()
    assert response.status_code == 500
    assert body == {
        "code": "internal_error",
        "error": "Internal Server Error",
        "requestId": "req_exception",
    }


def test_diagnostic_exception_logs_internal_error_without_response_leak(caplog: Any) -> None:
    test_logger = logging.getLogger("tests.agent_relay.http.exception")
    test_app = create_app(test_logger)
    with caplog.at_level(logging.INFO, logger=test_logger.name), api_client(test_app) as client:
        response = client.get(
            "/api/diagnostics/exception",
            headers={"X-Request-Id": "req_exception_log"},
        )

    assert response.status_code == 500
    record = only_record_with_message(caplog.records, "Request failed")
    assert log_value(record, "request_id") == "req_exception_log"

    assert log_value(record, "status") == 500

    assert "request_id=req_exception_log" in record.getMessage()
    assert "method=GET path=/api/diagnostics/exception status=500" in record.getMessage()
    assert "duration_ms=" in record.getMessage()

    assert record.exc_info is not None
    assert len([entry for entry in caplog.records if entry.exc_info is not None]) == 1
    assert "diagnostic endpoint intentionally throws" in caplog.text
    assert "diagnostic endpoint intentionally throws" not in response.text
    completion_record = only_record_with_message(caplog.records, "Request end")
    assert completion_record.levelno == logging.ERROR
    assert log_value(completion_record, "status") == 500


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
def test_http_errors_keep_status_headers_and_safe_summary(
    status_code: int, code: str, headers: dict[str, str]
) -> None:
    test_app = create_app(logging.getLogger("tests.agent_relay.http_server_error"))

    @test_app.get("/api/test-error")
    def fail() -> None:
        detail = "private upstream diagnostic" if status_code >= 500 else "Request rejected"
        raise HTTPException(status_code, detail=detail, headers=headers)

    with api_client(test_app) as client:
        response = client.get("/api/test-error", headers={"X-Request-Id": "req_server_error"})

    assert response.status_code == status_code
    for name, value in headers.items():
        assert response.headers[name] == value
    assert response.json()["code"] == code
    assert response.json()["requestId"] == "req_server_error"
    assert "private upstream diagnostic" not in response.text
    if status_code < 500:
        assert response.json()["error"] == "Request rejected"


def only_record_with_message(
    records: Sequence[logging.LogRecord],
    message: str,
) -> logging.LogRecord:
    matches = [record for record in records if record.getMessage().startswith(message)]
    assert len(matches) == 1
    return matches[0]


def log_value(record: logging.LogRecord, key: str) -> object:
    return getattr(record, key)
