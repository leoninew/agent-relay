from typing import Annotated, Literal

from pydantic import ConfigDict, Field, field_validator

from agent_relay.domain.rooms.models.base import RoomModel


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
