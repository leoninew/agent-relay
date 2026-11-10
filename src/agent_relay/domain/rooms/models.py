from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, model_validator
from pydantic.alias_generators import to_camel

USER_MEMBER_ID = "user"


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
    created_at: datetime | None = None
    message_count: int = 0
    deleted_at: datetime | None = None


class Member(RoomModel):
    id: str
    kind: Literal["human", "agent"] = "agent"
    session_id: str | None
    name: str
    initials: str
    presence: Literal["available", "busy", "offline", "unknown"]
    activity: str
    activity_source: str = "unknown"
    observed_at: datetime | None = None
    topic_ids: list[str]
    deleted_at: datetime | None = None

    @model_validator(mode="after")
    def validate_session(self) -> Self:
        if self.kind == "agent" and not self.session_id:
            raise ValueError("Agent members require a session")
        if self.kind == "human" and self.session_id is not None:
            raise ValueError("Human members cannot bind a session")
        return self


class Session(RoomModel):
    id: str
    name: str
    provider: str
    project_path: str
    presence: Literal["available", "busy", "offline", "unknown"]
    observed_at: datetime | None = None


class Delivery(RoomModel):
    id: str
    target_member_id: str
    target_session_id: str
    client_message_id: str
    status: Literal["pending", "submitting", "queued", "received", "rejected", "unknown"]
    updated_at: datetime
    deleted_at: datetime | None = None
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
    sender_id: str
    sender_name: str
    content: str
    topic_ids: list[str]
    mentioned_member_ids: list[str]
    recipient_ids: list[str]
    reply_to_message_id: str | None = None
    created_at: datetime
    deliveries: list[Delivery]


class TopicPosition(RoomModel):
    member_id: str
    topic_id: str
    seq: int
    updated_at: datetime | None
    later_count: int
