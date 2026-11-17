import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import httpx2
import pytest
from fastapi import FastAPI

from conflua.application.dto.members import MemberInterruptResult
from conflua.application.members.sessions import (
    SessionInterruptRejected,
    SessionUnavailableError,
)
from conflua.domain.rooms.models import Member, Room, RoomState
from conflua.interfaces.http.exception_handlers import register_exception_handlers
from conflua.interfaces.http.rooms.routes import channel_router


@pytest.fixture
def interrupt_api() -> tuple[FastAPI, MagicMock, Mock]:
    store = MagicMock()
    scoped = store.for_channel.return_value
    scoped.read.return_value.__enter__.return_value.resources.return_value = RoomState(
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
    driver.interrupt.return_value = MemberInterruptResult(status="interrupted", turn_id="turn")
    app = FastAPI()
    app.include_router(channel_router, prefix="/api")
    app.state.http_dependencies = SimpleNamespace(room_store=store, session_driver=driver)
    app.state.logger = logging.getLogger(__name__)
    register_exception_handlers(app)
    return app, store, driver


def request(
    app: FastAPI, member_id: str = "member", request_id: str = "req-interrupt"
) -> httpx2.Response:
    async def post() -> httpx2.Response:
        async with httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.post(
                f"/api/room/room/channel/channel/member/{member_id}/interrupt",
                headers={"X-Request-Id": request_id},
            )

    return asyncio.run(post())


def test_http_interrupt_uses_channel_scoped_binding_and_returns_final_result(
    interrupt_api: tuple[FastAPI, MagicMock, Mock],
) -> None:
    app, store, driver = interrupt_api
    response = request(app)
    assert response.status_code == 200
    assert response.json() == {"status": "interrupted", "turnId": "turn"}
    store.for_channel.assert_called_once_with("channel")
    driver.interrupt.assert_called_once_with("thread")


@pytest.mark.parametrize("failure", ["missing", "unsupported", "unknown"])
def test_http_interrupt_errors_keep_safe_contract_and_request_id(
    interrupt_api: tuple[FastAPI, MagicMock, Mock], failure: str
) -> None:
    app, _, driver = interrupt_api
    if failure == "unsupported":
        driver.interrupt.side_effect = SessionInterruptRejected(
            "当前会话不支持打断", code="session_interrupt_unsupported"
        )
    elif failure == "unknown":
        driver.interrupt.side_effect = SessionUnavailableError(
            "private upstream diagnostic", code="session_interrupt_unknown"
        )
    response = request(app, "absent" if failure == "missing" else "member", request_id="")
    assert response.status_code == {"missing": 404, "unsupported": 409, "unknown": 503}[failure]
    body = response.json()
    assert (
        body["code"]
        == {
            "missing": "member_not_found",
            "unsupported": "session_interrupt_unsupported",
            "unknown": "session_interrupt_unknown",
        }[failure]
    )
    assert body["requestId"] == response.headers["X-Request-Id"]
    assert body["requestId"]
    assert "private" not in body["error"]
