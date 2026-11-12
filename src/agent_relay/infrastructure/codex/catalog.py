import hashlib
import json
import ntpath
import posixpath
from dataclasses import dataclass
from pathlib import PureWindowsPath
from typing import Any, Literal

from pydantic import ConfigDict, Field

from agent_relay.application.capabilities.contracts import (
    CatalogIssue,
    McpServerOption,
    McpToolOption,
    SkillCatalog,
    SkillOption,
)
from agent_relay.domain.rooms.models import RoomModel
from agent_relay.domain.rooms.rules import normalize_project_path


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


def decode_skills(payload: dict[str, Any], project_path: str) -> SkillDiscovery:
    cwd = normalize_project_path(project_path)
    entries = [
        entry
        for entry in _SkillsResponse.model_validate(payload).data
        if normalize_project_path(entry.cwd) == cwd
    ]
    if len(entries) != 1:
        raise ValueError("Skill catalog does not match the requested directory")
    entry = entries[0]
    bindings: list[SkillBinding] = []
    seen: set[str] = set()
    for skill in entry.skills:
        native_path = normalize_project_path(skill.path)
        if PureWindowsPath(cwd).drive:
            try:
                relative = ntpath.relpath(native_path, cwd).replace("\\", "/").casefold()
            except ValueError:
                relative = native_path
        else:
            relative = posixpath.relpath(native_path, cwd)
        identity = json.dumps(
            [skill.scope, skill.plugin_id, skill.name, relative], ensure_ascii=False
        )
        skill_id = "skill-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()
        if skill_id in seen:
            raise ValueError("Ambiguous skill identity")
        seen.add(skill_id)
        interface = skill.interface
        option = SkillOption(
            id=skill_id,
            name=skill.name,
            display_name=(interface.display_name if interface else None) or skill.name,
            description=(interface.short_description if interface else None)
            or skill.short_description
            or skill.description,
            scope=skill.scope,
            source="plugin" if skill.plugin_id else skill.scope,
            plugin_id=skill.plugin_id,
            enabled=skill.enabled,
        )
        bindings.append(SkillBinding(option, skill.name, skill.path))
    return SkillDiscovery(
        bindings=tuple(bindings),
        errors=tuple(
            CatalogIssue(code="skill_load_failed", error="部分技能加载失败，请刷新后重试")
            for _ in entry.errors
        ),
    )


def server_option(server: _Server) -> McpServerOption:
    errors: list[CatalogIssue] = []
    if server.auth_status == "notLoggedIn" or server.runtime_status == "authenticationRequired":
        status: Literal[
            "ready", "starting", "authentication_required", "unavailable", "unknown"
        ] = "authentication_required"
        errors.append(CatalogIssue(code="mcp_authentication_required", error="MCP 服务器需要认证"))
    elif server.runtime_status == "connected":
        status = "ready"
    elif server.runtime_status in {"starting", "notStarted"}:
        status = "starting"
    elif server.runtime_status is None:
        status = "unknown"
        errors.append(CatalogIssue(code="mcp_status_unknown", error="未能核验目标会话的 MCP 状态"))
    else:
        status = "unavailable"
        errors.append(CatalogIssue(code="mcp_server_unavailable", error="MCP 服务器当前不可用"))
    if server.tools_error is not None:
        status = "unavailable"
        errors.append(CatalogIssue(code="mcp_tools_unavailable", error="MCP 工具目录读取失败"))
    tools = [
        McpToolOption(name=tool.name, description=tool.description or "")
        for tool in server.tools.values()
    ]
    if len({tool.name for tool in tools}) != len(tools):
        raise ValueError("Duplicate MCP tool identity")
    return McpServerOption(
        id="mcp-" + hashlib.sha256(server.name.encode("utf-8")).hexdigest(),
        name=server.name,
        available=status == "ready",
        status=status,
        tools=tools,
        errors=errors,
    )
