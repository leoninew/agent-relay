from collections.abc import Callable

from conflua.application.capabilities.ports import CapabilityDriver, CapabilityUnavailableError
from conflua.application.dto.capabilities import McpCatalog, SkillCatalog
from conflua.application.rooms.ports import RoomStore
from conflua.domain.rooms.errors import RoomInputError


class CapabilityService:
    def __init__(self, store: RoomStore, driver: CapabilityDriver) -> None:
        self.store = store
        self.driver = driver

    @staticmethod
    def _catalog[CatalogT](query: Callable[[], CatalogT]) -> CatalogT:
        try:
            return query()
        except Exception as exc:
            raise CapabilityUnavailableError(
                "无法读取能力目录，请刷新后重试", code="capability_metadata_unavailable"
            ) from exc

    def skills(self, room_id: str, *, force_reload: bool = False) -> SkillCatalog:
        with self.store.read() as rooms:
            workspace_path = rooms.working_path(room_id)
        return self._catalog(
            lambda: self.driver.list_skills(workspace_path, force_reload=force_reload)
        )

    def mcp_servers(self, room_id: str, member_id: str) -> McpCatalog:
        with self.store.read() as rooms:
            member = rooms.member(room_id, member_id)
            if member.kind != "agent" or member.session_id is None:
                raise RoomInputError(
                    "仅绑定 Codex 会话的成员支持 MCP 目录", code="member_mcp_unsupported"
                )
            thread_id = member.session_id
        return self._catalog(lambda: self.driver.list_mcp_servers(thread_id))
