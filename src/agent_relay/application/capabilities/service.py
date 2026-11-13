from collections.abc import Callable

from agent_relay.application.capabilities.ports import CapabilityDriver, CapabilityUnavailableError
from agent_relay.application.dto.capabilities import McpCatalog, SkillCatalog
from agent_relay.application.rooms.ports import RoomStore
from agent_relay.domain.rooms.errors import RoomConflictError, RoomInputError, RoomNotFoundError
from agent_relay.domain.rooms.rules import normalize_project_path


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
            project_path = rooms.room(room_id).project_path
        return self._catalog(
            lambda: self.driver.list_skills(project_path, force_reload=force_reload)
        )

    def mcp_servers(self, room_id: str, member_id: str) -> McpCatalog:
        with self.store.read() as rooms:
            state = rooms.resources(room_id)
            member = next(
                (item for item in state.members if item.id == member_id and not item.deleted_at),
                None,
            )
            if member is None:
                raise RoomNotFoundError("聊天室成员不存在", code="member_not_found")
            if member.kind != "agent" or member.session_id is None:
                raise RoomInputError(
                    "仅绑定 Codex 会话的成员支持 MCP 目录", code="member_mcp_unsupported"
                )
            session = next((item for item in state.sessions if item.id == member.session_id), None)
            if session is None:
                raise RoomConflictError(
                    "成员绑定的 Codex 会话不存在", code="session_binding_not_found"
                )
            project_path = state.room.project_path
            if normalize_project_path(session.project_path) != normalize_project_path(project_path):
                raise RoomConflictError(
                    "成员会话不属于当前聊天室项目目录", code="session_project_mismatch"
                )
            thread_id = session.id
        return self._catalog(lambda: self.driver.list_mcp_servers(thread_id, project_path))
