from pydantic import ConfigDict, Field, field_validator

from agent_relay.application.dto.messages import MessagePage
from agent_relay.application.dto.rooms import RoomMetadata
from agent_relay.domain.rooms.models import Channel, RoomModel


class UpdateChannel(RoomModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=40)
    description: str = Field(default="", max_length=300)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Channel name cannot be blank")
        return value


class CreateChannel(UpdateChannel):
    channel_id: str | None = Field(
        default=None, min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$"
    )
    use_worktree: bool = False


class ChannelSnapshot(RoomMetadata, MessagePage):
    channel_id: str
    working_path: str


__all__ = ["Channel", "ChannelSnapshot", "CreateChannel", "UpdateChannel"]
