import pytest
from fakes.rooms import MemoryRoomStore, sample_room
from session_fixtures import FakeSessionDriver

from agent_relay.application.members.service import MemberSessions
from agent_relay.application.members.sessions import SessionInfo
from agent_relay.application.rooms.contracts import CreateMember
from agent_relay.domain.rooms.errors import RoomConflictError


@pytest.mark.parametrize("concurrent_conflict", [False, True])
def test_join_releases_the_read_scope_before_inspection_and_rechecks_current_facts(
    concurrent_conflict: bool,
) -> None:
    state = sample_room()
    store = MemoryRoomStore(state)

    class ObservingDriver(FakeSessionDriver):
        def inspect(self, thread_id: str) -> SessionInfo:
            assert store.active_scopes == 0
            if concurrent_conflict:
                store.data.states[state.room.id].members[0].name = "New member"
            return super().inspect(thread_id)

    driver = ObservingDriver([SessionInfo("fresh", "D:/project", "codex", "Original", "idle")])
    members = MemberSessions(store, driver)
    request = CreateMember(name="New member", session_id="fresh", topic_ids=[])
    if concurrent_conflict:
        with pytest.raises(RoomConflictError, match="同名"):
            members.add(state.room.id, request)
        assert all(
            member.session_id != "fresh" for member in store.data.states[state.room.id].members
        )
    else:
        member = members.add(state.room.id, request)
        assert member.session_id == "fresh" and member.topic_ids == []
        assert member.metadata.members[-1].id == member.id
    assert driver.inspected == ["fresh"] and store.active_scopes == 0
