from dataclasses import dataclass
from typing import Any, Literal

from pydantic import ConfigDict, Field

from agent_relay.application.dto.capabilities import CatalogIssue, SkillCatalog, SkillOption
from agent_relay.domain.rooms.models import RoomModel


class _WireModel(RoomModel):
    model_config = ConfigDict(strict=True)


class _SkillInterface(_WireModel):
    display_name: str | None = None
    short_description: str | None = None


class _SkillMetadata(_WireModel):
    name: str = Field(min_length=1)
    description: str
    path: str = Field(min_length=1)
    scope: Literal["user", "repo", "system", "admin"]
    plugin_id: str | None = None
    enabled: bool
    interface: _SkillInterface | None = None
    short_description: str | None = None


class _SkillError(_WireModel):
    path: str
    message: str


class _SkillEntry(_WireModel):
    cwd: str
    skills: list[_SkillMetadata]
    errors: list[_SkillError]


class _SkillsResponse(_WireModel):
    data: list[_SkillEntry]


class _Tool(_WireModel):
    name: str = Field(min_length=1)
    description: str | None = None
    input_schema: Any


class _Server(_WireModel):
    name: str
    auth_status: Literal["unknown", "unsupported", "notLoggedIn", "bearerToken", "oAuth"]
    tools: dict[str, _Tool]
    resources: list[Any]
    resource_templates: list[Any]
    runtime_status: (
        Literal[
            "notStarted",
            "starting",
            "connected",
            "authenticationRequired",
            "failed",
            "cancelled",
            "disabled",
        ]
        | None
    ) = None
    tools_error: str | None = None


class McpPage(_WireModel):
    data: list[_Server]
    next_cursor: str | None


@dataclass(frozen=True)
class SkillBinding:
    option: SkillOption
    native_name: str
    native_path: str


@dataclass(frozen=True)
class SkillDiscovery:
    bindings: tuple[SkillBinding, ...]
    errors: tuple[CatalogIssue, ...]

    def public_catalog(self) -> SkillCatalog:
        return SkillCatalog(
            skills=[item.option for item in self.bindings], errors=list(self.errors)
        )
