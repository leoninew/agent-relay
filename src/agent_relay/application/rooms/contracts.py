from pydantic import ConfigDict, Field, field_validator

from agent_relay.application.messages.contracts import MessagePage
from agent_relay.application.rooms.views import TopicPosition
from agent_relay.domain.rooms.events import RoomChangeKind
from agent_relay.domain.rooms.models import Member, Room, RoomModel, Session, Topic


class RoomSummary(RoomModel):
    total_messages: int
    queued_count: int
    received_count: int = 0
    pending_count: int = 0
    submitting_count: int = 0
    rejected_count: int = 0
    unknown_count: int = 0


class RoomMetadata(RoomModel):
    room: Room
    topics: list[Topic]
    members: list[Member]
    sessions: list[Session]
    positions: list[TopicPosition]
    summary: RoomSummary
    event_id: int


class ChangedTopic(Topic):
    metadata: RoomMetadata


class RoomSnapshot(RoomMetadata, MessagePage):
    pass


class RoomEvent(RoomModel):
    event_id: int
    kind: RoomChangeKind
    entity_id: str
    message_id: str | None


class RoomEventPage(RoomModel):
    events: list[RoomEvent]
    next_event_id: int
    has_more: bool
    resync_required: bool


class CreateRoom(RoomModel):
    name: str = Field(min_length=1, max_length=80)
    project_path: str = Field(min_length=1, max_length=500)

    @field_validator("name", "project_path")
    @classmethod
    def strip_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Field cannot be blank")
        return value


class UpdateRoom(RoomModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def strip_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Field cannot be blank")
        return value


class CreateTopic(RoomModel):
    name: str = Field(min_length=1, max_length=40)
    description: str = Field(default="", max_length=300)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Topic name cannot be blank")
        return value
