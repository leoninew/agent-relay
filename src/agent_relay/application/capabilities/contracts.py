from typing import Literal

from pydantic import Field

from agent_relay.domain.rooms.models import RoomModel


class CatalogIssue(RoomModel):
    code: Literal[
        "skill_load_failed",
        "mcp_tools_unavailable",
        "mcp_server_unavailable",
        "mcp_authentication_required",
        "mcp_status_unknown",
    ]
    error: str


class SkillOption(RoomModel):
    type: Literal["skill"] = "skill"
    id: str
    name: str
    display_name: str
    description: str
    scope: Literal["user", "repo", "system", "admin"]
    source: Literal["plugin", "user", "repo", "system", "admin"]
    plugin_id: str | None
    enabled: bool


class SkillCatalog(RoomModel):
    skills: list[SkillOption]
    errors: list[CatalogIssue] = Field(default_factory=list)


class McpToolOption(RoomModel):
    name: str
    description: str


class McpServerOption(RoomModel):
    type: Literal["mcp_server"] = "mcp_server"
    id: str
    name: str
    available: bool
    status: Literal["ready", "starting", "authentication_required", "unavailable", "unknown"]
    tools: list[McpToolOption]
    errors: list[CatalogIssue] = Field(default_factory=list)


class McpCatalog(RoomModel):
    servers: list[McpServerOption]
