from unittest.mock import MagicMock, Mock

import pytest

from conflua.application.dto.rooms import RoomMetadata, RoomSummary
from conflua.application.rooms.ports import RoomData, RoomStore
from conflua.domain.rooms.errors import RoomNotFoundError
from conflua.domain.rooms.models import Member, Room, RoomState, Session, Topic


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
        room=Room(
            id="conflua",
            name="Room",
            project_path="d:/project",
            raw_project_path="d:/project",
            description="",
        ),
        channel_id="channel-default",
        working_path="d:/project",
        topics=[Topic(id=topic, name=topic, description="") for topic in ["frontend", "backend"]],
        members=members,
        sessions=[
            Session(
                id=member.session_id,
                name=member.name,
                provider="codex",
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
    repository.working_path.side_effect = lambda room_id: room_state.working_path
    repository.resources.return_value = room_state

    def member(room_id: str, member_id: str) -> Member:
        found = next(
            (item for item in room_state.members if item.id == member_id and not item.deleted_at),
            None,
        )
        if found is None:
            raise RoomNotFoundError("聊天室成员不存在", code="member_not_found")
        return found

    repository.member.side_effect = member
    repository.active_bindings.side_effect = lambda room_id: {
        item.id: item.session_id
        for item in room_state.members
        if item.kind == "agent" and item.session_id and not item.deleted_at
    }
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
        (room_state.room.id, room_state.channel_id, member.session_id)
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
    store.for_channel.return_value = store
    return store
