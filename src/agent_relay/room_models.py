from __future__ import annotations

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel


class RoomModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class Room(RoomModel):
    id: str
    name: str
    project_path: str
    description: str


class Topic(RoomModel):
    id: str
    name: str
    description: str
    message_count: int = 0
    deleted_at: datetime | None = None


class Member(RoomModel):
    id: str
    session_id: str
    name: str
    initials: str
    presence: Literal["available", "busy", "offline", "unknown"]
    activity: str
    activity_source: str = "unknown"
    observed_at: datetime | None = None
    topic_ids: list[str]
    deleted_at: datetime | None = None


class Session(RoomModel):
    id: str
    name: str
    provider: str
    project_path: str
    presence: Literal["available", "busy", "offline", "unknown"]

    observed_at: datetime | None = None


class SessionCandidate(Session):
    archived: bool
    member_id: str | None = None
    usable: bool
    unavailable_reason: str | None


class CreatedMember(Member):
    session: Session


class Delivery(RoomModel):
    id: str
    target_member_id: str
    target_session_id: str
    client_message_id: str
    status: Literal["pending", "submitting", "queued", "received", "rejected", "unknown"]
    updated_at: datetime
    queued_at: datetime | None = None
    received_at: datetime | None = None
    received_item_id: str | None = None
    received_turn_id: str | None = None
    activation_attempted_at: datetime | None = None
    note: str | None = None
    queued_submission_id: str | None = None
    receipt: dict[str, object] | None = None
    error: str | None = None


class Message(RoomModel):
    id: str
    publication_id: str | None = None
    seq: int
    sender_id: str | None
    sender_name: str
    content: str
    topic_ids: list[str]
    mentioned_member_ids: list[str]
    recipient_ids: list[str]
    reply_to_message_id: str | None = None
    created_at: datetime
    deliveries: list[Delivery]


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


class TopicPosition(RoomModel):
    member_id: str
    topic_id: str
    seq: int
    updated_at: datetime | None
    later_count: int


class RoomMetadata(RoomModel):
    room: Room
    topics: list[Topic]
    members: list[Member]
    sessions: list[Session]
    positions: list[TopicPosition]
    summary: RoomSummary
    event_id: int


class RoomSnapshot(RoomMetadata, MessagePage):
    pass


class RoomEvent(RoomModel):
    event_id: int
    kind: Literal["room", "topic", "member", "session", "message", "delivery", "position"]
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
    topic_ids: list[str] = Field(min_length=1)

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
