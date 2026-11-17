import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import httpx2
import pytest
from fastapi import FastAPI

from conflua.application.dto.session_models import (
    SessionModelCatalog,
    SessionModelOption,
    UpdateSessionModel,
)
from conflua.application.members.sessions import SessionModelRejected, SessionUnavailableError
from conflua.domain.rooms.models import Member, Room, RoomState
from conflua.interfaces.http.exception_handlers import register_exception_handlers
from conflua.interfaces.http.rooms.routes import channel_router


@pytest.fixture
def model_api() -> tuple[FastAPI, MagicMock, Mock]:
    store = MagicMock()
    repository = store.for_channel.return_value.read.return_value.__enter__.return_value
    repository.resources.return_value = RoomState(
        room=Room(
            id="room",
            name="Room",
            project_path="D:/project",
            raw_project_path="D:/project",
            description="",
        ),
        channel_id="channel",
        working_path="D:/worktree",
        topics=[],
        sessions=[],
        members=[
            Member(
                id="member",
                session_id="thread",
                name="Worker",
                initials="W",
                activity="",
                presence="busy",
                topic_ids=[],
            )
        ],
    )
    driver = Mock()
    result = SessionModelCatalog(
        session_id="thread",
        provider="provider",
        current_model="gpt/model",
        models=[
            SessionModelOption(
                id="catalog-id",
                model="gpt/model",
                display_name="GPT display",
                description="Tip",
            )
        ],
    )
    driver.model_catalog.return_value = result
    driver.update_model.return_value = result
    app = FastAPI()
    app.include_router(channel_router, prefix="/api")
    app.state.http_dependencies = SimpleNamespace(room_store=store, session_driver=driver)
    app.state.logger = logging.getLogger(__name__)
    register_exception_handlers(app)
    return app, store, driver


def request(
    app: FastAPI, method: str = "GET", member: str = "member", body: object = None
) -> httpx2.Response:
    async def send() -> httpx2.Response:
        async with httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.request(
                method,
                f"/api/room/room/channel/channel/member/{member}/model",
                json=body,
                headers={"X-Request-Id": "req-model"},
            )

    return asyncio.run(send())


def test_model_api_uses_channel_scope_and_camel_case(
    model_api: tuple[FastAPI, MagicMock, Mock],
) -> None:
    app, store, driver = model_api
    response = request(app)
    assert response.status_code == 200
    assert response.json() == {
        "sessionId": "thread",
        "provider": "provider",
        "currentModel": "gpt/model",
        "models": [
            {
                "id": "catalog-id",
                "model": "gpt/model",
                "displayName": "GPT display",
                "description": "Tip",
            }
        ],
    }
    store.for_channel.assert_called_once_with("channel")
    driver.model_catalog.assert_called_once_with("thread")
    assert request(app, "PATCH", body={"sessionId": "thread", "model": "model"}).status_code == 200
    driver.update_model.assert_called_once_with(
        "thread", UpdateSessionModel(session_id="thread", model="model")
    )


@pytest.mark.parametrize("failure", ["missing", "rejected", "unknown", "validation", "rebound"])
def test_model_api_errors_follow_safe_contract(
    model_api: tuple[FastAPI, MagicMock, Mock], failure: str
) -> None:
    app, _, driver = model_api
    if failure == "rejected":
        driver.update_model.side_effect = SessionModelRejected(
            "模型切换请求未被接受", code="session_model_update_rejected"
        )
    elif failure == "unknown":
        driver.update_model.side_effect = SessionUnavailableError(
            "private diagnostic", code="session_model_update_unknown"
        )
    body: dict[str, str] = {
        "sessionId": "other" if failure == "rebound" else "thread",
        "model": "model",
    }
    if failure == "validation":
        body["unexpected"] = "private"
    response = request(app, "PATCH", "absent" if failure == "missing" else "member", body)
    assert (
        response.status_code
        == {"missing": 404, "rejected": 409, "unknown": 503, "validation": 422, "rebound": 409}[
            failure
        ]
    )
    result = response.json()
    assert result["requestId"] == response.headers["X-Request-Id"] == "req-model"
    assert "private" not in result["error"]
    assert (
        result["code"]
        == {
            "missing": "member_not_found",
            "rejected": "session_model_update_rejected",
            "unknown": "session_model_update_unknown",
            "validation": "validation_error",
            "rebound": "session_binding_changed",
        }[failure]
    )
