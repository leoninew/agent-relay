import asyncio
import json
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pydantic import ValidationError
from starlette.requests import Request
from starlette.types import Message, Receive, Scope, Send

from agent_relay.application.dto.preferences import Preferences, UpdatePreferences
from agent_relay.application.preferences.ports import PreferenceReadError, PreferenceWriteError
from agent_relay.bootstrap.config import load_settings
from agent_relay.bootstrap.http import create_app
from agent_relay.interfaces.http.exception_handlers import preferences_exception_handler
from agent_relay.interfaces.http.middleware import RequestTransactionMiddleware
from agent_relay.interfaces.http.preferences.dependencies import get_preferences
from agent_relay.interfaces.http.preferences.routes import get_preferences as get_route
from agent_relay.interfaces.http.preferences.routes import update_preferences


def test_routes_use_injected_service() -> None:
    expected = Preferences(language="system", resolvedLanguage="zh-CN")
    service = Mock()
    service.get.return_value = expected
    service.update.return_value = expected
    request = Request(
        {"type": "http", "app": SimpleNamespace(state=SimpleNamespace(preferences=service))}
    )
    assert get_preferences(request) is service
    assert get_route(service) == expected
    assert update_preferences(UpdatePreferences(language="system"), service) == expected
    service.update.assert_called_once_with("system")
    assert expected.model_dump(by_alias=True) == {"language": "system", "resolvedLanguage": "zh-CN"}


def test_app_preserves_injected_service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service = Mock()
    monkeypatch.setattr("agent_relay.bootstrap.http.create_delivery_runner", Mock())
    monkeypatch.setattr("agent_relay.bootstrap.http.create_presence_runner", Mock())
    monkeypatch.setattr("agent_relay.bootstrap.http.create_http_dependencies", Mock())
    app = create_app(
        logging.getLogger(__name__),
        settings=load_settings(),
        static_directory=tmp_path,
        database=Mock(),
        session_driver=Mock(),
        queue_driver=Mock(),
        capability_driver=Mock(),
        preferences_service=service,
    )
    assert app.state.preferences is service


@pytest.mark.parametrize("value", [{}, {"language": "fr"}, {"language": "en", "extra": True}])
def test_update_rejects_invalid_request(value: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        UpdatePreferences.model_validate(value)


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (PreferenceReadError("secret path"), "preferences_read_failed"),
        (PreferenceWriteError("secret path"), "preferences_save_failed"),
    ],
)
def test_failure_contract(error: Exception, code: str) -> None:
    request = Request(
        {
            "type": "http",
            "headers": [(b"x-request-id", b"req_preferences")],
            "app": SimpleNamespace(state=SimpleNamespace(logger=Mock())),
        }
    )
    assert isinstance(error, (PreferenceReadError, PreferenceWriteError))
    response = asyncio.run(preferences_exception_handler(request, error))
    body = json.loads(bytes(response.body))
    assert response.status_code == 503
    assert body == {"code": code, "error": "Service Unavailable", "requestId": "req_preferences"}
    assert response.headers["X-Request-Id"] == "req_preferences"
    assert "secret path" not in str(body)


@pytest.mark.parametrize("path", ["/api/preferences", "/api/app"])
def test_preferences_skip_database_transaction(path: str) -> None:
    factory = Mock(side_effect=AssertionError("transaction created"))

    async def application(scope: Scope, receive: Receive, send: Send) -> None:
        await send({"type": "http.response.start", "status": 200, "headers": []})

    async def receive() -> Message:
        return {"type": "http.request"}

    async def send(message: Message) -> None:
        assert message["status"] == 200

    middleware = RequestTransactionMiddleware(application, transaction_factory=factory)
    asyncio.run(middleware({"type": "http", "path": path}, receive, send))
    factory.assert_not_called()
