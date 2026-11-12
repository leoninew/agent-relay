from dataclasses import dataclass
from typing import Literal

from pydantic import ConfigDict, Field, field_validator

from agent_relay.application.dto.rooms import RoomMetadata
from agent_relay.domain.rooms.models import Member, RoomModel, Session

type SessionStatus = Literal["unavailable", "idle", "active", "error"]


@dataclass(frozen=True)
class SessionInfo:
    id: str
    cwd: str
    provider: str
    name: str
    status: SessionStatus
    archived: bool = False

    @property
    def usable(self) -> bool:
        return not self.archived and self.status in {"idle", "active"}

    @property
    def unavailable_reason(self) -> str | None:
        if self.archived:
            return "会话已归档；请在 Codex 中恢复并接入共享 daemon 后刷新"
        if self.status == "error":
            return "会话状态异常；请在原 Codex 会话处理后刷新"
        if not self.usable:
            return (
                "未接入当前消息通道，可能未运行或在独立实例中运行；"
                "请使用共享 daemon 打开此会话后刷新"
            )
        return None

    @property
    def presence(self) -> Literal["available", "busy", "offline", "unknown"]:
        if not self.usable:
            return "unknown"
        return "available" if self.status == "idle" else "busy"


class SessionCandidate(Session):
    archived: bool
    member_id: str | None = None
    usable: bool
    unavailable_reason: str | None


class ChangedMember(Member):
    metadata: RoomMetadata


class CreatedMember(ChangedMember):
    session: Session


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
    session_id: str = Field(min_length=1, max_length=128)

    @field_validator("session_id")
    @classmethod
    def strip_session_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Session ID cannot be blank")
        return value
