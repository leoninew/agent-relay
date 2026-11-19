from copy import deepcopy
from datetime import UTC, datetime

from conflua.application.dto.rooms import (
    ChangedTopic,
    ClearedRoom,
    CreateRoom,
    CreateTopic,
    UpdateRoom,
)
from conflua.application.members.sessions import SessionDriver, SessionUnavailableError
from conflua.application.rooms.ports import RoomStore
from conflua.domain.identifiers import new_tsid
from conflua.domain.rooms.errors import RoomConflictError
from conflua.domain.rooms.members import retire_member
from conflua.domain.rooms.models import Room, Topic
from conflua.domain.rooms.resources import (
    new_room_state,
    require_topic,
    retire_topic,
    validate_topic_name,
)
from conflua.domain.rooms.rules import normalize_workspace_path


class RoomService:
    def __init__(self, store: RoomStore) -> None:
        self.store = store

    def create_room(self, request: CreateRoom) -> Room:
        workspace_path = normalize_workspace_path(request.workspace_path)
        with self.store.write() as rooms:
            if rooms.workspace_exists(workspace_path):
                raise RoomConflictError(
                    "该路径已有聊天室，请直接打开", code="workspace_room_exists"
                )
            room = Room(
                id=new_tsid(),
                name=request.name,
                workspace_path=workspace_path,
                raw_workspace_path=request.workspace_path,
                description="",
            )
            state = new_room_state(
                room,
                datetime.now(UTC),
                channel_id=new_tsid(),
                working_path=room.workspace_path,
            )
            rooms.insert_room(state)
            return room.model_copy(deep=True)

    def delete_room(self, room_id: str) -> None:
        with self.store.guard(room_id), self.store.write() as rooms:
            rooms.room(room_id)
            rooms.delete_room(room_id)

    def clear_room(self, room_id: str, driver: SessionDriver) -> ClearedRoom:
        with self.store.read() as rooms:
            bindings = rooms.active_bindings(room_id)
        unavailable: set[str] = set()
        if bindings:
            try:
                sessions = driver.connected_sessions(
                    frozenset(session_id for session_id in bindings.values() if session_id)
                )
            except Exception as exc:
                raise SessionUnavailableError(
                    "无法核验成员连接状态，请刷新后重试", code="session_metadata_unavailable"
                ) from exc
            reachable = {info.id for info in sessions if info.usable}
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
        with self.store.guard(room_id), self.store.write() as rooms:
            state = rooms.resources(room_id)
            original = deepcopy(state)
            if request.workspace_path is not None:
                workspace_path = normalize_workspace_path(request.workspace_path)
                if rooms.workspace_exists(workspace_path, exclude_room_id=room_id):
                    raise RoomConflictError(
                        "该路径已有聊天室，请直接打开", code="workspace_room_exists"
                    )
                state.room.raw_workspace_path = request.workspace_path
                state.room.workspace_path = workspace_path
            state.room.name = request.name
            rooms.save_resources(state, original)
            return state.room.model_copy(deep=True)

    def add_topic(self, room_id: str, request: CreateTopic) -> ChangedTopic:
        with self.store.write() as rooms:
            state = rooms.resources(room_id)
            original = deepcopy(state)
            validate_topic_name(state, request.name)
            topic = Topic(
                id=new_tsid(),
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
