from typing import Annotated

from pydantic import ConfigDict, StringConstraints, field_validator

from conflua.application.dto.messages import MAX_MESSAGE_CONTENT_LENGTH, validate_message_content
from conflua.domain.rooms.models import RoomModel


class MemberRoleInput(RoomModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    prompt: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, min_length=1, max_length=MAX_MESSAGE_CONTENT_LENGTH
        ),
    ]

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, prompt: str) -> str:
        validate_message_content(prompt, set())
        return prompt


class MemberRole(RoomModel):
    id: str
    name: str
    prompt: str
