from __future__ import annotations

from typing import Self

from pydantic import ConfigDict, Field, field_validator, model_validator

from agent_relay.domain.rooms.events import RoomChangeKind
from agent_relay.domain.rooms.models import (
    Member,
    Message,
    Room,
    RoomModel,
    Session,
    Topic,
    TopicPosition,
)


class SessionCandidate(Session):
    archived: bool
    member_id: str | None = None
    usable: bool
    unavailable_reason: str | None


class RoomSummary(RoomModel):
    total_messages: int
    queued_count: int
    received_count: int = 0
    pending_count: int = 0
    submitting_count: int = 0
    rejected_count: int = 0
    unknown_count: int = 0


class MessagePage(RoomModel):
    messages: list[Message]
    has_more: bool
    next_before_seq: int | None
    has_newer: bool


class MessageQueuePage(RoomModel):
    messages: list[Message]
    total_messages: int
    has_more: bool
    next_before_seq: int | None


class ClearedMessageQueue(RoomModel):
    removed_messages: int


class RoomMetadata(RoomModel):
    room: Room
    topics: list[Topic]
    members: list[Member]
    sessions: list[Session]
    positions: list[TopicPosition]
    summary: RoomSummary
    event_id: int


class ChangedMember(Member):
    metadata: RoomMetadata


class CreatedMember(ChangedMember):
    session: Session


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


class CreateMessage(RoomModel):
    model_config = ConfigDict(extra="forbid")

    publication_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    content: str = Field(min_length=1, max_length=6000)
    topic_ids: list[str] = Field(default_factory=list)
    mentioned_member_ids: list[str] = Field(default_factory=list)
    reply_to_message_id: str | None = None

    @field_validator("content")
    @classmethod
    def strip_content(cls, content: str) -> str:
        content = content.strip()
        if not content:
            raise ValueError("Message content cannot be blank")
        return content

    @model_validator(mode="after")
    def require_targets(self) -> Self:
        if not self.topic_ids and not self.mentioned_member_ids:
            raise ValueError("Message requires a topic or a directly mentioned member")
        return self


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


class UpdateMember(RoomModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    topic_ids: list[str]

    @field_validator("name")
    @classmethod
    def strip_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Field cannot be blank")
        return value


class CreateMember(UpdateMember):
    model_config = ConfigDict(extra="forbid")
    session_id: str = Field(min_length=1, max_length=128)

    @field_validator("session_id")
    @classmethod
    def strip_session_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Session ID cannot be blank")
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
