from typing import Annotated

from fastapi import APIRouter, Query

from conflua.application.dto.capabilities import McpCatalog, SkillCatalog
from conflua.interfaces.http.capabilities.dependencies import CapabilityServiceDependency

router = APIRouter(prefix="/room/{room_id}/channel/{channel_id}", tags=["capabilities"])


@router.get("/skills")
def list_skills(
    room_id: str,
    service: CapabilityServiceDependency,
    force_reload: Annotated[bool, Query()] = False,
) -> SkillCatalog:
    return service.skills(room_id, force_reload=force_reload)


@router.get("/member/{member_id}/mcp")
def list_mcp_servers(
    room_id: str, member_id: str, service: CapabilityServiceDependency
) -> McpCatalog:
    return service.mcp_servers(room_id, member_id)
