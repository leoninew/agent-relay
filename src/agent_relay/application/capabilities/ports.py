from typing import Protocol

from agent_relay.application.dto.capabilities import McpCatalog, SkillCatalog


class CapabilityUnavailableError(RuntimeError):
    pass


class CapabilityDriver(Protocol):
    def list_skills(self, project_path: str, *, force_reload: bool = False) -> SkillCatalog: ...
    def list_mcp_servers(self, thread_id: str, project_path: str) -> McpCatalog: ...
