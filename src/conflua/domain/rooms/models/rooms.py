from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Self

from pydantic import model_validator

from conflua.domain.rooms.models.base import RoomModel

USER_MEMBER_ID = "user"
DEFAULT_CHANNEL_ID = "channel-default"
type ChannelStatus = Literal["active", "archived"]
RoomChangeKind = Literal[
    "room", "topic", "member", "session", "message", "delivery", "position", "clear"
]


class Room(RoomModel):
    id: str
    name: str
    workspace_path: str
    raw_workspace_path: str
    description: str
    archived_at: datetime | None = None


class Channel(RoomModel):
    id: str
    room_id: str
    name: str
    description: str = ""
    working_path: str
    is_default: bool
    status: ChannelStatus = "active"
    workspace_kind: Literal["existing", "worktree"] = "existing"
    branch: str | None = None
    base_commit: str | None = None
    created_at: datetime | None = None
    archived_at: datetime | None = None


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
    presence: Literal["available", "busy", "offline", "unknown"]
    observed_at: datetime | None = None


@dataclass
class RoomState:
    room: Room
    channel_id: str
    working_path: str
    topics: list[Topic] = field(default_factory=list)
    members: list[Member] = field(default_factory=list)
    sessions: list[Session] = field(default_factory=list)
