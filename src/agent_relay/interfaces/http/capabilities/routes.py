from typing import Annotated

from fastapi import APIRouter, Query

from agent_relay.application.capabilities.contracts import McpCatalog, SkillCatalog
from agent_relay.interfaces.http.capabilities.dependencies import CapabilityServiceDependency

router = APIRouter(prefix="/room", tags=["capabilities"])


@router.get("/{room_id}/skills")
def list_skills(
    room_id: str,
    service: CapabilityServiceDependency,
    force_reload: Annotated[bool, Query()] = False,
) -> SkillCatalog:
    return service.skills(room_id, force_reload=force_reload)


@router.get("/{room_id}/member/{member_id}/mcp")
def list_mcp_servers(
    room_id: str, member_id: str, service: CapabilityServiceDependency
) -> McpCatalog:
    return service.mcp_servers(room_id, member_id)
