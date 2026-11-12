from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
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


class CapabilityReferenceModel(RoomModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1, max_length=256, pattern=r"^[A-Za-z0-9_][A-Za-z0-9_.@-]*$")
    name: str = Field(min_length=1, max_length=256)

    @field_validator("name")
    @classmethod
    def require_name(cls, name: str) -> str:
        if not name.strip():
            raise ValueError("Capability name cannot be blank")
        return name.strip()


class SkillReference(CapabilityReferenceModel):
    type: Literal["skill"] = "skill"


class McpServerReference(CapabilityReferenceModel):
    type: Literal["mcp_server"] = "mcp_server"


CapabilityReference = Annotated[SkillReference | McpServerReference, Field(discriminator="type")]


class Message(RoomModel):
    id: str
    publication_id: str | None = None
    seq: int
    sender_id: str
    sender_name: str
    content: str
    capabilities: tuple[CapabilityReference, ...] = ()
    topic_ids: list[str]
    mentioned_member_ids: list[str]
    recipient_ids: list[str]
    reply_to_message_id: str | None = None
    created_at: datetime
    deliveries: list[Delivery]
