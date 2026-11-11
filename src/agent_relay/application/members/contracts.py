from pydantic import ConfigDict, Field, field_validator

from agent_relay.application.rooms.contracts import RoomMetadata
from agent_relay.domain.rooms.models import Member, RoomModel, Session


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
