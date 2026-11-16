from pydantic import ConfigDict, Field, field_validator

from conflua.domain.rooms.models import RoomModel


class SessionModelOption(RoomModel):
    id: str
    model: str
    display_name: str
    description: str


class SessionModelCatalog(RoomModel):
    session_id: str
    provider: str
    current_model: str | None
    models: list[SessionModelOption]


class UpdateSessionModel(RoomModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1, max_length=128)
    model: str = Field(min_length=1, max_length=256)

    @field_validator("session_id", "model")
    @classmethod
    def strip_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Field cannot be blank")
        return value
