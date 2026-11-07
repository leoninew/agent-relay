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


class Member(RoomModel):
    id: str
    session_id: str
    name: str
    role: str
    initials: str
    presence: Literal["available", "busy", "offline"]
    activity: str
    topic_ids: list[str]


class Session(RoomModel):
    id: str
    name: str
    provider: str
    project_path: str
    presence: Literal["available", "busy", "offline"]


class Delivery(RoomModel):
    id: str
    target_member_id: str
    status: Literal["queued", "delivered"]
    updated_at: datetime


class Message(RoomModel):
    id: str
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
    delivered_count: int
    queued_count: int


class RoomSnapshot(RoomModel):
    room: Room
    topics: list[Topic]
    members: list[Member]
    messages: list[Message]
    summary: RoomSummary


class CreateMessage(RoomModel):
    model_config = ConfigDict(extra="forbid")

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
    name: str = Field(min_length=1, max_length=80)
    role: str = Field(min_length=1, max_length=80)
    topic_ids: list[str] = Field(min_length=1)

    @field_validator("name", "role")
    @classmethod
    def strip_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Field cannot be blank")
        return value


class CreateMember(UpdateMember):
    session_id: str = Field(min_length=1)


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
