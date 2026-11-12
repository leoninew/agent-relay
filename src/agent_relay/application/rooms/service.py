from copy import deepcopy
from datetime import UTC, datetime
from uuid import uuid4

from agent_relay.application.dto.rooms import (
    ChangedTopic,
    ClearedRoom,
    CreateRoom,
    CreateTopic,
    UpdateRoom,
)
from agent_relay.application.members.sessions import SessionDriver, SessionUnavailableError
from agent_relay.application.rooms.ports import RoomStore
from agent_relay.domain.rooms.errors import RoomConflictError
from agent_relay.domain.rooms.members import retire_member
from agent_relay.domain.rooms.models import Room, RoomState, Topic
from agent_relay.domain.rooms.resources import (
    new_room_state,
    require_topic,
    retire_topic,
    validate_topic_name,
)
from agent_relay.domain.rooms.rules import normalize_project_path


class RoomService:
    def __init__(self, store: RoomStore) -> None:
        self.store = store

    def create_room(self, request: CreateRoom) -> Room:
        project_path = normalize_project_path(request.project_path)
        with self.store.write() as rooms:
            if rooms.project_exists(project_path):
                raise RoomConflictError("该项目已有聊天室，请直接打开")
            room = Room(
                id=f"room-{uuid4().hex[:12]}",
                name=request.name,
                project_path=project_path,
                description="",
            )
            state = new_room_state(room, datetime.now(UTC))
            rooms.insert_room(room, state.members[0])
            rooms.save_resources(state, RoomState(room=room, members=[state.members[0]]))
            return room.model_copy(deep=True)

    def delete_room(self, room_id: str) -> None:
        with self.store.write() as rooms:
            rooms.room(room_id)
            rooms.delete_room(room_id)

    def clear_room(self, room_id: str, driver: SessionDriver) -> ClearedRoom:
        with self.store.read() as rooms:
            state = rooms.resources(room_id)
            bindings = {
                member.id: member.session_id
                for member in state.members
                if member.kind == "agent" and member.deleted_at is None
            }
            project_path = state.room.project_path
        unavailable: set[str] = set()
        if bindings:
            try:
                sessions = driver.list_sessions()
            except Exception as exc:
                raise SessionUnavailableError("无法核验成员连接状态，请刷新后重试") from exc
            reachable = {
                info.id
                for info in sessions
                if info.usable and normalize_project_path(info.cwd) == project_path
            }
            unavailable = {
                member_id
                for member_id, session_id in bindings.items()
                if session_id not in reachable
            }
        with self.store.write() as rooms:
            state = rooms.resources(room_id)
            original = deepcopy(state)
            now = datetime.now(UTC)
            removed_members = 0
            for member in state.members:
                if member.id in unavailable and member.deleted_at is None:
                    retire_member(state, member.id, now)
                    removed_members += 1
            rooms.save_resources(state, original)
            removed_messages = rooms.clear_messages(room_id, now)
            return ClearedRoom(
                removed_messages=removed_messages,
                removed_members=removed_members,
                metadata=rooms.metadata(room_id),
            )

    def update_room(self, room_id: str, request: UpdateRoom) -> Room:
        with self.store.write() as rooms:
            state = rooms.resources(room_id)
            original = deepcopy(state)
            state.room.name = request.name
            rooms.save_resources(state, original)
            return state.room.model_copy(deep=True)

    def add_topic(self, room_id: str, request: CreateTopic) -> ChangedTopic:
        with self.store.write() as rooms:
            state = rooms.resources(room_id)
            original = deepcopy(state)
            validate_topic_name(state, request.name)
            topic = Topic(
                id=f"topic-{uuid4().hex[:12]}",
                name=request.name,
                description=request.description.strip(),
                created_at=datetime.now(UTC),
            )
            state.topics.append(topic)
            rooms.save_resources(state, original)
            return ChangedTopic(**topic.model_dump(), metadata=rooms.metadata(room_id))

    def update_topic(self, room_id: str, topic_id: str, request: CreateTopic) -> ChangedTopic:
        with self.store.write() as rooms:
            state = rooms.resources(room_id)
            original = deepcopy(state)
            topic = require_topic(state, topic_id)
            validate_topic_name(state, request.name, topic_id)
            topic.name = request.name
            topic.description = request.description.strip()
            rooms.save_resources(state, original)
            return ChangedTopic(**topic.model_dump(), metadata=rooms.metadata(room_id))

    def delete_topic(self, room_id: str, topic_id: str) -> ChangedTopic:
        with self.store.write() as rooms:
            state = rooms.resources(room_id)
            original = deepcopy(state)
            topic = retire_topic(state, topic_id, datetime.now(UTC))
            rooms.save_resources(state, original)
            return ChangedTopic(**topic.model_dump(), metadata=rooms.metadata(room_id))
