from datetime import UTC, datetime
from unittest.mock import MagicMock, Mock

import pytest

from agent_relay.application.dto.members import MemberInterruptResult
from agent_relay.application.members.service import MemberService
from agent_relay.application.members.sessions import SessionDriver, SessionInterruptRejected
from agent_relay.domain.rooms.errors import RoomConflictError, RoomNotFoundError
from agent_relay.domain.rooms.models import RoomState


def test_interrupt_uses_binding_and_releases_database_before_rpc(
    room_state: RoomState, room_store: MagicMock, room_repository: Mock
) -> None:
    driver = Mock(spec=SessionDriver)
    expected = MemberInterruptResult(status="interrupted", turn_id="original-turn")

    def interrupt(thread_id: str, project_path: str) -> MemberInterruptResult:
        room_store.read.return_value.__exit__.assert_called_once()
        assert (thread_id, project_path) == ("frontend-worker-session", "d:/project")
        return expected

    driver.interrupt.side_effect = interrupt
    assert (
        MemberService(room_store, driver).interrupt(room_state.room.id, "frontend-worker")
        == expected
    )
    room_store.write.assert_not_called()
    room_repository.save_resources.assert_not_called()


@pytest.mark.parametrize("target", ["absent", "deleted", "human", "unbound"])
def test_invalid_interrupt_targets_never_reach_codex(
    room_state: RoomState, room_store: MagicMock, target: str
) -> None:
    driver = Mock(spec=SessionDriver)
    member_id = "frontend-worker"
    if target == "absent":
        member_id = "absent"
    elif target == "deleted":
        room_state.members[1].deleted_at = datetime.now(UTC)
        member_id = room_state.members[1].id
    elif target == "human":
        member_id = "user"
    else:
        room_state.members[2].session_id = None
    error = RoomNotFoundError if target in {"absent", "deleted"} else RoomConflictError
    with pytest.raises(error):
        MemberService(room_store, driver).interrupt(room_state.room.id, member_id)
    driver.interrupt.assert_not_called()


def test_interrupt_rejection_uses_existing_conflict_contract(room_store: MagicMock) -> None:
    driver = Mock(spec=SessionDriver)
    driver.interrupt.side_effect = SessionInterruptRejected(
        "当前会话不支持打断", code="session_interrupt_unsupported"
    )
    with pytest.raises(RoomConflictError) as caught:
        MemberService(room_store, driver).interrupt("agent-relay", "frontend-worker")
    assert caught.value.code == "session_interrupt_unsupported"
