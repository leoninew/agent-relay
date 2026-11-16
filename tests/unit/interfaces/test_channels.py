from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from conflua.application.dto.channels import CreateChannel, UpdateChannel
from conflua.interfaces.http.channels.routes import create_channel, update_channel


def test_channel_routes_delegate_to_creation_service() -> None:
    service = Mock()
    request = CreateChannel(name="API", description="Backend work")
    assert create_channel("room-1", request, service) is service.create.return_value
    service.create.assert_called_once_with("room-1", request)


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
