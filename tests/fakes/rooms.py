from collections.abc import Iterator
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime

from agent_relay.application.rooms.contracts import RoomMetadata, RoomSummary
from agent_relay.application.rooms.ports import RoomData, RoomQueries
from agent_relay.domain.rooms.errors import RoomNotFoundError
from agent_relay.domain.rooms.models import USER_MEMBER_ID, Member, Message, Room, Topic
from agent_relay.domain.rooms.state import RoomState


def sample_room() -> RoomState:
    return RoomState(
        room=Room(id="agent-relay", name="Relay", project_path="d:/project", description=""),
        topics=[
            Topic(id=topic_id, name=topic_id, description="")
            for topic_id in ("frontend", "backend", "summary")
        ],
        members=[
            Member(
                id=member_id,
                session_id=member_id + "-session",
                name=member_id,
                initials=member_id[:2],
                presence="available",
                activity="",
                topic_ids=topics,
            )
            for member_id, topics in [
                ("coordinator", ["summary", "frontend", "backend"]),
                ("frontend-worker", ["frontend", "summary"]),
                ("backend-worker", ["backend", "summary"]),
                ("test-worker", ["frontend", "backend", "summary"]),
            ]
        ]
        + [
            Member(
                id="user",
                kind="human",
                session_id=None,
                name="你",
                initials="你",
                presence="available",
                activity="",
                topic_ids=[],
            )
        ],
    )


class MemoryRoomData:
    def __init__(self, state: RoomState) -> None:
        self.states = {state.room.id: deepcopy(state)}
        self.messages: dict[str, list[Message]] = {state.room.id: []}

    def resources(self, room_id: str) -> RoomState:
        if room_id not in self.states:
            raise RoomNotFoundError("聊天室不存在")
        return deepcopy(self.states[room_id])

    def room(self, room_id: str) -> Room:
        return self.resources(room_id).room

    def metadata(self, room_id: str) -> RoomMetadata:
        state = self.resources(room_id)
        return RoomMetadata(
            **state.__dict__,
            positions=[],
            event_id=0,
            summary=RoomSummary(total_messages=len(self.messages[room_id]), queued_count=0),
        )

    def project_exists(self, project_path: str) -> bool:
        return any(state.room.project_path == project_path for state in self.states.values())

    def publisher(self, room_id: str, member_id: str | None) -> Member:
        for member in self.resources(room_id).members:
            if member.id == (member_id or USER_MEMBER_ID) and not member.deleted_at:
                return member
        raise RoomNotFoundError("聊天室成员不存在")

    def publication(self, room_id: str, publisher_id: str, publication_id: str) -> Message | None:
        return next(
            (
                deepcopy(message)
                for message in self.messages[room_id]
                if message.sender_id == publisher_id and message.publication_id == publication_id
            ),
            None,
        )

    def message_exists(self, room_id: str, message_id: str) -> bool:
        return any(message.id == message_id for message in self.messages[room_id])

    def next_message_seq(self, room_id: str) -> int:
        return len(self.messages[room_id]) + 1

    def joined_members(self, room_id: str) -> dict[str, str]:
        return {
            member.session_id: member.id
            for member in self.resources(room_id).members
            if member.session_id and not member.deleted_at
        }

    def bindings(self) -> list[tuple[str, str]]:
        return [
            (room_id, session_id)
            for room_id in self.states
            for session_id in self.joined_members(room_id)
        ]

    def insert_room(self, room: Room) -> None:
        self.states[room.id] = RoomState(room=deepcopy(room))
        self.messages[room.id] = []

    def delete_room(self, room_id: str) -> None:
        del self.states[room_id]
        del self.messages[room_id]

    def save_resources(self, state: RoomState, original: RoomState) -> None:
        self.states[state.room.id] = deepcopy(state)

    def insert_message(self, room_id: str, message: Message) -> None:
        self.messages[room_id].append(deepcopy(message))

    def clear_queue(
        self,
        room_id: str,
        *,
        topic_id: str | None,
        member_id: str | None,
        deleted_at: datetime,
    ) -> int:
        raise NotImplementedError

    def save_observation(
        self,
        room_id: str,
        member_id: str,
        session_id: str,
        presence: str,
        activity: str,
        observed_at: datetime,
        session_name: str | None,
    ) -> None:
        raise NotImplementedError


class MemoryRoomStore:
    def __init__(self, state: RoomState) -> None:
        self.data = MemoryRoomData(state)
        self.active_scopes = 0

    @property
    def queries(self) -> RoomQueries:
        raise NotImplementedError

    @contextmanager
    def read_rooms(self) -> Iterator[RoomData]:
        self.active_scopes += 1
        try:
            yield self.data
        finally:
            self.active_scopes -= 1

    @contextmanager
    def write_rooms(self) -> Iterator[RoomData]:
        original = deepcopy(self.data)
        self.active_scopes += 1
        try:
            yield self.data
        except BaseException:
            self.data = original
            raise
        finally:
            self.active_scopes -= 1
