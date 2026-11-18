import asyncio
import logging
from unittest.mock import Mock

import httpx2
import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from conflua.application.dto.channels import Channel, CreateChannel, UpdateChannel
from conflua.interfaces.http.channels.dependencies import get_channel_service
from conflua.interfaces.http.channels.routes import create_channel, router, update_channel
from conflua.interfaces.http.exception_handlers import register_exception_handlers


def test_channel_routes_delegate_to_creation_service() -> None:
    service = Mock()
    request = CreateChannel(name="API", description="Backend work")
    assert create_channel("room-1", request, service) is service.create.return_value
    service.create.assert_called_once_with("room-1", request)


@pytest.mark.parametrize(
    ("body", "name", "status"),
    [
        (None, None, 200),
        ({"name": " Finished API "}, "Finished API", 200),
        ({"name": "  "}, None, 422),
        ({"name": "x" * 41}, None, 422),
    ],
)
def test_channel_archive_accepts_an_optional_validated_name(
    body: dict[str, str] | None, name: str | None, status: int
) -> None:
    service = Mock()
    service.archive.return_value = Channel(
        id="channel-api",
        room_id="room",
        name=name or "API",
        working_path="/project",
        is_default=False,
        status="archived",
    )
    app = FastAPI()
    app.state.logger = logging.getLogger(__name__)
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_channel_service] = lambda: service
    register_exception_handlers(app)

    async def post() -> httpx2.Response:
        async with httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.post("/api/room/room/channel/channel-api/archive", json=body)

    response = asyncio.run(post())

    assert response.status_code == status
    if status == 200:
        assert response.json()["name"] == (name or "API")
        assert response.json()["status"] == "archived"
        service.archive.assert_called_once_with("room", "channel-api", name=name)
    else:
        assert response.json()["code"] == "validation_error"
        service.archive.assert_not_called()


def test_worktree_request_never_accepts_a_base_override() -> None:
    request = CreateChannel.model_validate({"name": " API ", "useWorktree": True})
    assert request.name == "API" and request.use_worktree
    with pytest.raises(ValidationError):
        CreateChannel.model_validate({"name": "API", "baseCommit": "abc"})


def test_channel_creation_defaults_to_existing_directory() -> None:
    assert CreateChannel(name="API").use_worktree is False
    assert CreateChannel(name="API").description == ""
    with pytest.raises(ValidationError):
        CreateChannel(name=" ")


def test_channel_update_accepts_metadata_only() -> None:
    request = UpdateChannel(name=" API ", description="Backend")
    service = Mock()
    assert update_channel("room", "channel", request, service) is service.update.return_value
    service.update.assert_called_once_with("room", "channel", request)
    assert request.name == "API"
    for payload in ({"name": " "}, {"name": "API", "useWorktree": True}):
        with pytest.raises(ValidationError):
            UpdateChannel.model_validate(payload)


@pytest.mark.parametrize("channel_id", ["../outside", "D:/outside", "nested/channel"])
def test_channel_id_cannot_escape_the_managed_directory(channel_id: str) -> None:
    with pytest.raises(ValidationError):
        CreateChannel(name="API", channel_id=channel_id, use_worktree=True)
