from datetime import UTC, datetime
from unittest.mock import MagicMock, Mock

import pytest

from conflua.application.capabilities.ports import CapabilityDriver, CapabilityUnavailableError
from conflua.application.capabilities.service import CapabilityService
from conflua.application.dto.capabilities import McpCatalog, SkillCatalog
from conflua.domain.rooms.errors import RoomInputError, RoomNotFoundError
from conflua.domain.rooms.models import RoomState


def test_capability_queries_release_scope_and_pass_exact_room_and_target(
    room_store: MagicMock,
    room_repository: Mock,
) -> None:
    driver = Mock(spec=CapabilityDriver)
    skills = SkillCatalog(skills=[], errors=[])
    servers = McpCatalog(servers=[])

    def list_skills(project_path: str, *, force_reload: bool = False) -> SkillCatalog:
        room_store.read.return_value.__exit__.assert_called_once()
        return skills

    def list_mcp_servers(thread_id: str) -> McpCatalog:
        assert room_store.read.return_value.__exit__.call_count == 2
        return servers

    driver.list_skills.side_effect = list_skills
    driver.list_mcp_servers.side_effect = list_mcp_servers
    service = CapabilityService(room_store, driver)
    assert service.skills("conflua", force_reload=True) is skills
    assert service.mcp_servers("conflua", "frontend-worker") is servers
    driver.list_skills.assert_called_once_with("d:/project", force_reload=True)
    driver.list_mcp_servers.assert_called_once_with("frontend-worker-session")
    room_repository.resources.assert_not_called()


@pytest.mark.parametrize("case", ["missing", "deleted", "human"])
def test_invalid_member_scope_never_queries_codex(
    case: str, room_state: RoomState, room_store: MagicMock
) -> None:
    driver = Mock(spec=CapabilityDriver)
    member_id = "frontend-worker"
    member = next(item for item in room_state.members if item.id == member_id)
    error: type[Exception] = RoomNotFoundError
    if case == "missing":
        member_id = "another-room-member"
    elif case == "deleted":
        member.deleted_at = datetime.now(UTC)
    elif case == "human":
        member_id = "user"
        error = RoomInputError
    with pytest.raises(error):
        CapabilityService(room_store, driver).mcp_servers("conflua", member_id)
    driver.list_mcp_servers.assert_not_called()


def test_mcp_uses_the_member_binding_without_cached_session_metadata(
    room_state: RoomState, room_store: MagicMock
) -> None:
    room_state.sessions.clear()
    driver = Mock(spec=CapabilityDriver)
    driver.list_mcp_servers.return_value = McpCatalog(servers=[])
    result = CapabilityService(room_store, driver).mcp_servers("conflua", "frontend-worker")
    assert result.servers == []
    driver.list_mcp_servers.assert_called_once_with("frontend-worker-session")


def test_missing_room_does_not_query_codex(room_store: MagicMock, room_repository: Mock) -> None:
    driver = Mock(spec=CapabilityDriver)
    room_repository.working_path.side_effect = RoomNotFoundError("聊天室不存在")
    with pytest.raises(RoomNotFoundError):
        CapabilityService(room_store, driver).skills("another-room")
    driver.list_skills.assert_not_called()


def test_driver_failure_has_a_safe_public_error(room_store: MagicMock) -> None:
    driver = Mock(spec=CapabilityDriver)
    driver.list_skills.side_effect = RuntimeError("secret-token D:/private")
    with pytest.raises(CapabilityUnavailableError, match="无法读取能力目录") as caught:
        CapabilityService(room_store, driver).skills("conflua")
    assert "secret-token" not in str(caught.value)
