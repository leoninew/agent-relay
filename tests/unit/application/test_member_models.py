from datetime import UTC, datetime
from unittest.mock import MagicMock, Mock

import pytest

from agent_relay.application.dto.session_models import SessionModelCatalog, UpdateSessionModel
from agent_relay.application.members.service import MemberService
from agent_relay.application.members.sessions import SessionDriver, SessionModelRejected
from agent_relay.domain.rooms.errors import RoomConflictError, RoomNotFoundError
from agent_relay.domain.rooms.models import RoomState


def test_model_calls_use_bound_session_outside_database_scope(room_store: MagicMock) -> None:
    driver = Mock(spec=SessionDriver)
    expected = SessionModelCatalog(
        session_id="frontend-worker-session", provider="provider", current_model="old", models=[]
    )

    def read(session_id: str, project_path: str) -> SessionModelCatalog:
        room_store.read.return_value.__exit__.assert_called_once()
        assert (session_id, project_path) == ("frontend-worker-session", "d:/project")
        return expected

    driver.model_catalog.side_effect = read
    service = MemberService(room_store, driver)
    assert service.model_catalog("agent-relay", "frontend-worker") == expected
    driver.update_model.return_value = expected
    request = UpdateSessionModel(session_id="frontend-worker-session", model="new")
    assert service.update_model("agent-relay", "frontend-worker", request) == expected
    driver.update_model.assert_called_once_with("frontend-worker-session", "d:/project", request)
    room_store.write.assert_not_called()


@pytest.mark.parametrize("target", ["missing", "deleted", "human", "unbound", "rebound"])
def test_invalid_model_targets_never_write(
    room_state: RoomState, room_store: MagicMock, target: str
) -> None:
    driver = Mock(spec=SessionDriver)
    member_id = "frontend-worker"
    member = next(member for member in room_state.members if member.id == member_id)
    if target == "missing":
        member_id = "absent"
    elif target == "deleted":
        member.deleted_at = datetime.now(UTC)
    elif target == "human":
        member_id = "user"
    elif target == "unbound":
        member.session_id = None
    else:
        member.session_id = "rebound"
    error = RoomNotFoundError if target in {"missing", "deleted"} else RoomConflictError
    with pytest.raises(error):
        MemberService(room_store, driver).update_model(
            "agent-relay",
            member_id,
            UpdateSessionModel(session_id="frontend-worker-session", model="new"),
        )
    driver.update_model.assert_not_called()


def test_rejection_maps_to_conflict(room_store: MagicMock) -> None:
    driver = Mock(spec=SessionDriver)
    driver.model_catalog.side_effect = SessionModelRejected(
        "safe", code="session_model_target_unavailable"
    )
    with pytest.raises(RoomConflictError) as caught:
        MemberService(room_store, driver).model_catalog("agent-relay", "frontend-worker")
    assert caught.value.code == "session_model_target_unavailable"
