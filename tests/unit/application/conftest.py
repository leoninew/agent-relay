from unittest.mock import MagicMock, Mock

import pytest

from agent_relay.application.rooms.contracts import RoomMetadata, RoomSummary
from agent_relay.application.rooms.ports import RoomData, RoomStore
from agent_relay.domain.rooms.models import Member, Room, Session, Topic
from agent_relay.domain.rooms.state import RoomState


@pytest.fixture
def room_state() -> RoomState:
    members = [
        Member(
            id="user",
            kind="human",
            session_id=None,
            name="你",
            initials="你",
            presence="available",
            activity="",
            topic_ids=[],
        ),
        *[
            Member(
                id=member_id,
                session_id=f"{member_id}-session",
                name=member_id,
                initials=member_id[:2],
                presence="available",
                activity="",
                topic_ids=topics,
            )
            for member_id, topics in [
                ("coordinator", ["frontend", "backend"]),
                ("frontend-worker", ["frontend"]),
                ("backend-worker", ["backend"]),
                ("test-worker", ["frontend", "backend"]),
            ]
        ],
    ]
    return RoomState(
        room=Room(id="agent-relay", name="Room", project_path="d:/project", description=""),
        topics=[Topic(id=topic, name=topic, description="") for topic in ["frontend", "backend"]],
        members=members,
        sessions=[
            Session(
                id=member.session_id,
                name=member.name,
                provider="codex",
                project_path="D:/project",
                presence="available",
            )
            for member in members
            if member.session_id is not None
        ],
    )


@pytest.fixture
def room_repository(room_state: RoomState) -> Mock:
    repository = Mock(spec=RoomData)
    repository.room.return_value = room_state.room
    repository.resources.return_value = room_state
    repository.project_exists.return_value = False
    repository.publication.return_value = None
    repository.next_message_seq.return_value = 1
    repository.publisher.side_effect = lambda room_id, member_id: next(
        member for member in room_state.members if member.id == (member_id or "user")
    )
    repository.joined_members.return_value = {
        member.session_id: member.id for member in room_state.members if member.session_id
    }
    repository.bindings.return_value = [
        (room_state.room.id, member.session_id)
        for member in room_state.members
        if member.session_id
    ]

    def metadata(room_id: str) -> RoomMetadata:
        return RoomMetadata(
            room=room_state.room,
            topics=room_state.topics,
            members=room_state.members,
            sessions=room_state.sessions,
            positions=[],
            summary=RoomSummary(total_messages=0, queued_count=0),
            event_id=0,
        )

    repository.metadata.side_effect = metadata
    return repository


@pytest.fixture
def room_store(room_repository: Mock) -> MagicMock:
    store = MagicMock(spec=RoomStore)
    store.read.return_value.__enter__.return_value = room_repository
    store.write.return_value.__enter__.return_value = room_repository
    return store
