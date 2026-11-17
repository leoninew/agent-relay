import asyncio
import logging
from unittest.mock import Mock

import httpx2
import pytest
from fastapi import FastAPI

from conflua.application.dto.messages import MessageUpdatesQuery
from conflua.application.dto.rooms import RoomActivity, RoomSummary
from conflua.application.images.message_text import ImageMessageText
from conflua.application.rooms.ports import RoomQueries
from conflua.interfaces.http.exception_handlers import register_exception_handlers
from conflua.interfaces.http.message_output import get_message_output
from conflua.interfaces.http.rooms.dependencies import get_room_queries
from conflua.interfaces.http.rooms.routes import channel_router


@pytest.fixture
def updates_api() -> tuple[FastAPI, Mock]:
    queries = Mock(spec=RoomQueries)
    queries.message_updates.return_value = []
    queries.activity.return_value = RoomActivity(
        positions=[],
        summary=RoomSummary(total_messages=5, queued_count=2),
        event_id=11,
    )
    app = FastAPI()
    app.include_router(channel_router, prefix="/api")
    app.dependency_overrides[get_room_queries] = lambda: queries
    app.dependency_overrides[get_message_output] = lambda: ImageMessageText(None, "channel")
    app.state.logger = logging.getLogger(__name__)
    register_exception_handlers(app)
    return app, queries


def request(app: FastAPI, path: str, body: object = None) -> httpx2.Response:
    async def send() -> httpx2.Response:
        async with httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            return await client.request(
                "POST" if body is not None else "GET",
                "/api/room/room/channel/channel/" + path,
                json=body,
            )

    return asyncio.run(send())


def test_batch_updates_passes_filters_and_retention_with_camel_case(
    updates_api: tuple[FastAPI, Mock],
) -> None:
    app, queries = updates_api
    payload = {
        "messageIds": ["new", "detail"],
        "retainedIds": ["detail"],
        "topicId": "topic",
        "memberId": "member",
        "keyword": "needle",
    }
    response = request(app, "message/updates", payload)
    assert response.status_code == 200 and response.json() == []
    queries.message_updates.assert_called_once_with(
        "room", MessageUpdatesQuery.model_validate(payload)
    )
    queries.metadata.assert_not_called()


def test_oversized_batch_is_rejected_before_query(updates_api: tuple[FastAPI, Mock]) -> None:
    app, queries = updates_api
    response = request(app, "message/updates", {"messageIds": ["message"] * 201})
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    queries.message_updates.assert_not_called()


def test_activity_response_excludes_full_resources(updates_api: tuple[FastAPI, Mock]) -> None:
    app, queries = updates_api
    response = request(app, "activity")
    assert response.status_code == 200
    assert set(response.json()) == {"positions", "summary", "eventId"}
    queries.activity.assert_called_once_with("room")
    queries.metadata.assert_not_called()
