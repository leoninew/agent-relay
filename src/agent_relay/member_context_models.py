from datetime import datetime
from typing import Self

from pydantic import ConfigDict, Field, field_validator, model_validator

from agent_relay.room_models import RoomModel, TopicPosition


class CatalogTopic(RoomModel):
    id: str
    name: str
    description: str
    subscribed: bool


class CatalogMember(RoomModel):
    id: str
    name: str
    topic_ids: list[str]


class MemberCatalog(RoomModel):
    room_id: str
    room_name: str
    member_id: str
    topics: list[CatalogTopic]
    members: list[CatalogMember]


class ContextQuery(RoomModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str | None = Field(default=None, min_length=1, max_length=128)
    topic_id: str | None = Field(default=None, min_length=1, max_length=128)
    keyword: str | None = Field(default=None, min_length=1, max_length=200)
    before_seq: int | None = Field(default=None, ge=1)
    after_seq: int | None = Field(default=None, ge=0)
    limit: int = Field(default=50, ge=1, le=200)

    @field_validator("keyword")
    @classmethod
    def strip_keyword(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Keyword cannot be blank")
        return value

    @model_validator(mode="after")
    def validate_selection(self) -> Self:
        if self.message_id is not None:
            if any(
                value is not None
                for value in (
                    self.topic_id,
                    self.keyword,
                    self.before_seq,
                    self.after_seq,
                )
            ):
                raise ValueError("Single message lookup cannot include filters or cursors")
        elif self.topic_id is None and self.keyword is None:
            raise ValueError("Choose a message, topic or keyword")
        if self.before_seq is not None and self.after_seq is not None:
            raise ValueError("Choose one pagination direction")
        return self


class ContextMessage(RoomModel):
    id: str
    seq: int
    sender_id: str | None
    sender_name: str
    content: str
    topic_ids: list[str]
    mentioned_member_ids: list[str]
    reply_to_message_id: str | None
    created_at: datetime


class ContextResult(RoomModel):
    query_id: str | None
    messages: list[ContextMessage]
    has_more: bool
    next_before_seq: int | None
    next_after_seq: int | None
    positions: list[TopicPosition]
