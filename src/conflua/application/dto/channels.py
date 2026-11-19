from typing import Annotated

from pydantic import AfterValidator, ConfigDict, Field

from conflua.application.dto.messages import MessagePage
from conflua.application.dto.rooms import RoomMetadata
from conflua.domain.identifiers import TSID_BODY, require_tsid
from conflua.domain.rooms.models import Channel, RoomModel


def _strip_channel_name(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Channel name cannot be blank")
    return value


ChannelName = Annotated[
    str, Field(min_length=1, max_length=40), AfterValidator(_strip_channel_name)
]
ChannelId = Annotated[
    str, Field(min_length=13, max_length=13, pattern=f"^{TSID_BODY}$"), AfterValidator(require_tsid)
]


class UpdateChannel(RoomModel):
    model_config = ConfigDict(extra="forbid")

    name: ChannelName
    description: str = Field(default="", max_length=300)


class ArchiveChannel(RoomModel):
    model_config = ConfigDict(extra="forbid")

    name: ChannelName


class CreateChannel(UpdateChannel):
    channel_id: ChannelId
    use_worktree: bool = False


class IssuedChannelId(RoomModel):
    channel_id: ChannelId


class ChannelSnapshot(RoomMetadata, MessagePage):
    channel_id: str
    working_path: str


__all__ = ["ArchiveChannel", "Channel", "ChannelSnapshot", "CreateChannel", "UpdateChannel"]
