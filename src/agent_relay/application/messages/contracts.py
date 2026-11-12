from typing import Self

from pydantic import ConfigDict, Field, field_validator, model_validator

from agent_relay.domain.rooms.models import CapabilityReference, Message, RoomModel


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


class CodexQueueClearResult(RoomModel):
    deleted: int = 0
    not_found: int = 0
    rejected: int = 0
    unknown: int = 0
    without_receipt: int = 0


class ClearedMessageQueue(RoomModel):
    removed_messages: int
    codex_queue: CodexQueueClearResult | None = None


class CreateMessage(RoomModel):
    model_config = ConfigDict(extra="forbid")

    publication_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    content: str = Field(min_length=1, max_length=6000)
    capabilities: list[CapabilityReference] = Field(default_factory=list, max_length=100)
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
