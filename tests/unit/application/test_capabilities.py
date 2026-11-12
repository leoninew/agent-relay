from datetime import UTC, datetime
from unittest.mock import MagicMock, Mock

import pytest

from agent_relay.application.capabilities.ports import CapabilityDriver, CapabilityUnavailableError
from agent_relay.application.capabilities.service import CapabilityService
from agent_relay.application.dto.capabilities import McpCatalog, SkillCatalog
from agent_relay.domain.rooms.errors import RoomConflictError, RoomInputError, RoomNotFoundError
from agent_relay.domain.rooms.models import RoomState


def test_capability_queries_release_scope_and_pass_exact_room_and_target(
    room_store: MagicMock,
) -> None:
    driver = Mock(spec=CapabilityDriver)
    skills = SkillCatalog(skills=[], errors=[])
    servers = McpCatalog(servers=[])

    def list_skills(project_path: str, *, force_reload: bool = False) -> SkillCatalog:
        room_store.read.return_value.__exit__.assert_called_once()
        return skills

    def list_mcp_servers(thread_id: str, project_path: str) -> McpCatalog:
        assert room_store.read.return_value.__exit__.call_count == 2
        return servers

    driver.list_skills.side_effect = list_skills
    driver.list_mcp_servers.side_effect = list_mcp_servers
    service = CapabilityService(room_store, driver)
    assert service.skills("agent-relay", force_reload=True) is skills
    assert service.mcp_servers("agent-relay", "frontend-worker") is servers
    driver.list_skills.assert_called_once_with("d:/project", force_reload=True)
    driver.list_mcp_servers.assert_called_once_with("frontend-worker-session", "d:/project")


@pytest.mark.parametrize("case", ["missing", "deleted", "human", "session", "directory"])
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
    elif case == "session":
        room_state.sessions.clear()
        error = RoomConflictError
    else:
        session = next(item for item in room_state.sessions if item.id == member.session_id)
        session.project_path = "D:/other"
        error = RoomConflictError
    with pytest.raises(error):
        CapabilityService(room_store, driver).mcp_servers("agent-relay", member_id)
    driver.list_mcp_servers.assert_not_called()


def test_missing_room_does_not_query_codex(room_store: MagicMock, room_repository: Mock) -> None:
    driver = Mock(spec=CapabilityDriver)
    room_repository.room.side_effect = RoomNotFoundError("聊天室不存在")
    with pytest.raises(RoomNotFoundError):
        CapabilityService(room_store, driver).skills("another-room")
    driver.list_skills.assert_not_called()


def test_driver_failure_has_a_safe_public_error(room_store: MagicMock) -> None:
    driver = Mock(spec=CapabilityDriver)
    driver.list_skills.side_effect = RuntimeError("secret-token D:/private")
    with pytest.raises(CapabilityUnavailableError, match="无法读取能力目录") as caught:
        CapabilityService(room_store, driver).skills("agent-relay")
    assert "secret-token" not in str(caught.value)
