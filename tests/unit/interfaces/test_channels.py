import asyncio
import logging
from unittest.mock import Mock

import httpx2
import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from conflua.application.dto.channels import Channel, CreateChannel, IssuedChannelId, UpdateChannel
from conflua.interfaces.http.channels.dependencies import get_channel_service
from conflua.interfaces.http.channels.routes import (
    create_channel,
    get_channel,
    issue_channel_id,
    router,
    update_channel,
)
from conflua.interfaces.http.exception_handlers import register_exception_handlers

ROOM_ID = "0000000000123"
CHANNEL_ID = "0000000000124"


def test_channel_routes_delegate_to_creation_service() -> None:
    service = Mock()
    request = CreateChannel(name="API", description="Backend work", channel_id=CHANNEL_ID)
    assert create_channel(ROOM_ID, request, service) is service.create.return_value
    service.create.assert_called_once_with(ROOM_ID, request)


def test_channel_routes_issue_and_recover_the_same_id() -> None:
    service = Mock()
    service.issue_id.return_value = IssuedChannelId(channel_id=CHANNEL_ID)
    issued = issue_channel_id(ROOM_ID, service)
    assert issued.model_dump(by_alias=True) == {"channelId": CHANNEL_ID}
    service.issue_id.assert_called_once_with(ROOM_ID)
    assert get_channel(ROOM_ID, issued.channel_id, service) is service.channel.return_value
    service.channel.assert_called_once_with(ROOM_ID, CHANNEL_ID)


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
        id=CHANNEL_ID,
        room_id=ROOM_ID,
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
            return await client.post(f"/api/room/{ROOM_ID}/channel/{CHANNEL_ID}/archive", json=body)

    response = asyncio.run(post())

    assert response.status_code == status
    if status == 200:
        assert response.json()["name"] == (name or "API")
        assert response.json()["status"] == "archived"
        service.archive.assert_called_once_with(ROOM_ID, CHANNEL_ID, name=name)
    else:
        assert response.json()["code"] == "validation_error"
        service.archive.assert_not_called()


def test_worktree_request_never_accepts_a_base_override() -> None:
    request = CreateChannel.model_validate(
        {"name": " API ", "channelId": CHANNEL_ID, "useWorktree": True}
    )
    assert request.name == "API" and request.use_worktree
    with pytest.raises(ValidationError):
        CreateChannel.model_validate({"name": "API", "channelId": CHANNEL_ID, "baseCommit": "abc"})


def test_channel_creation_defaults_to_existing_directory() -> None:
    assert CreateChannel(name="API", channel_id=CHANNEL_ID).use_worktree is False
    assert CreateChannel(name="API", channel_id=CHANNEL_ID).description == ""


def test_channel_create_requires_a_valid_name_and_issued_id() -> None:
    with pytest.raises(ValidationError):
        CreateChannel.model_validate({"name": "API"})
    with pytest.raises(ValidationError):
        CreateChannel(name=" ", channel_id=CHANNEL_ID)


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
