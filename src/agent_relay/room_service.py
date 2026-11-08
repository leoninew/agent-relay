from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import PurePosixPath, PureWindowsPath
from threading import Lock
from uuid import uuid4

from agent_relay.room_errors import (
    RoomConflictError,
    RoomInputError,
    RoomNotFoundError,
)
from agent_relay.room_models import (
    CreateMessage,
    CreateRoom,
    CreateTopic,
    Delivery,
    Member,
    Message,
    Room,
    RoomSnapshot,
    Topic,
    UpdateMember,
)
from agent_relay.room_queries import RoomQueries
from agent_relay.room_state import RoomState
from agent_relay.room_store import SQLiteRoomStore


class RoomService:
    def __init__(self, store: SQLiteRoomStore) -> None:
        self._lock = Lock()
        self._rooms: dict[str, RoomState] = {}
        self._store = store

    @property
    def store(self) -> SQLiteRoomStore:
        return self._store

    @contextmanager
    def _transaction(self, *, write: bool) -> Iterator[None]:
        with self._lock, self._store.transaction(write=write) as rooms:
            self._rooms = rooms
            try:
                yield
            finally:
                self._rooms = {}

    def list_rooms(self) -> list[Room]:
        with self._transaction(write=False):
            return [state.room.model_copy(deep=True) for state in self._rooms.values()]

    def create_room(self, request: CreateRoom) -> Room:
        with self._transaction(write=True):
            project_path = self._normalize_project_path(request.project_path)
            if any(state.room.project_path == project_path for state in self._rooms.values()):
                raise RoomConflictError("该项目已有聊天室，请直接打开")
            room = Room(
                id=f"room-{uuid4().hex[:12]}",
                name=request.name,
                project_path=project_path,
                description="",
            )
            self._rooms[room.id] = RoomState(
                room=room,
                topics=[],
            )
            return room.model_copy(deep=True)

    def update_member(self, room_id: str, member_id: str, request: UpdateMember) -> Member:
        with self._transaction(write=True):
            state = self._get_room(room_id)
            member = next(
                (
                    member
                    for member in state.members
                    if member.id == member_id and not member.deleted_at
                ),
                None,
            )
            if member is None:
                raise RoomNotFoundError("成员不存在")
            self._validate_member(state, request, member_id)
            member.name = request.name
            member.initials = request.name[:2].upper()
            member.topic_ids = list(dict.fromkeys(request.topic_ids))
            return member.model_copy(deep=True)

    @staticmethod
    def _validate_member(
        state: RoomState, request: UpdateMember, member_id: str | None = None
    ) -> None:
        if any(
            not member.deleted_at and member.name == request.name and member.id != member_id
            for member in state.members
        ):
            raise RoomConflictError("房间中已有同名成员")
        if not set(request.topic_ids) <= {
            topic.id for topic in state.topics if not topic.deleted_at
        }:
            raise RoomInputError("成员订阅的话题不存在")

    def add_topic(self, room_id: str, request: CreateTopic) -> Topic:
        with self._transaction(write=True):
            state = self._get_room(room_id)
            if any(topic.name == request.name and not topic.deleted_at for topic in state.topics):
                raise RoomConflictError("房间中已有同名话题")
            topic = Topic(
                id=f"topic-{uuid4().hex[:12]}",
                name=request.name,
                description=request.description.strip(),
            )
            state.topics.append(topic)
            return topic.model_copy(deep=True)

    def update_topic(self, room_id: str, topic_id: str, request: CreateTopic) -> Topic:
        with self._transaction(write=True):
            state = self._get_room(room_id)
            topic = next(
                (topic for topic in state.topics if topic.id == topic_id and not topic.deleted_at),
                None,
            )
            if topic is None:
                raise RoomNotFoundError("话题不存在")
            if any(
                other.id != topic_id and not other.deleted_at and other.name == request.name
                for other in state.topics
            ):
                raise RoomConflictError("房间中已有同名话题")
            topic.name = request.name
            topic.description = request.description.strip()
            return topic.model_copy(
                update={
                    "message_count": sum(
                        topic.id in message.topic_ids for message in state.messages
                    )
                },
                deep=True,
            )

    def delete_topic(self, room_id: str, topic_id: str) -> Topic:
        with self._transaction(write=True):
            state = self._get_room(room_id)
            topic = next(
                (topic for topic in state.topics if topic.id == topic_id and not topic.deleted_at),
                None,
            )
            if topic is None:
                raise RoomNotFoundError("话题不存在")
            topic.deleted_at = datetime.now(UTC)
            for member in state.members:
                member.topic_ids = [
                    subscribed for subscribed in member.topic_ids if subscribed != topic_id
                ]
            return topic.model_copy(deep=True)

    def delete_member(self, room_id: str, member_id: str) -> Member:
        with self._transaction(write=True):
            state = self._get_room(room_id)
            member = next(
                (
                    member
                    for member in state.members
                    if member.id == member_id and not member.deleted_at
                ),
                None,
            )
            if member is None:
                raise RoomNotFoundError("成员不存在")
            member.deleted_at = datetime.now(UTC)
            member.topic_ids = []
            return member.model_copy(deep=True)

    def _get_room(self, room_id: str) -> RoomState:
        state = self._rooms.get(room_id)
        if state is None:
            raise RoomNotFoundError("聊天室不存在")
        return state

    @staticmethod
    def _normalize_project_path(value: str) -> str:
        windows_path = PureWindowsPath(value)
        if windows_path.drive:
            if not windows_path.is_absolute():
                raise RoomInputError("请输入项目的绝对路径")
            return windows_path.as_posix().casefold()
        posix_path = PurePosixPath(value)
        if not posix_path.is_absolute():
            raise RoomInputError("请输入项目的绝对路径")
        return posix_path.as_posix()

    def snapshot(self, room_id: str, topic_id: str | None = None) -> RoomSnapshot:
        return RoomQueries(self._store).snapshot(room_id, topic_id)

    @staticmethod
    def _publisher(state: RoomState, member_id: str | None) -> Member | None:
        if member_id is None:
            return None
        member = next(
            (
                member
                for member in state.members
                if member.id == member_id and not member.deleted_at
            ),
            None,
        )
        if member is None:
            raise RoomNotFoundError("聊天室成员不存在")
        return member

    def post_message(
        self, room_id: str, request: CreateMessage, *, member_id: str | None = None
    ) -> Message:
        with self._transaction(write=True):
            state = self._get_room(room_id)
            sender = self._publisher(state, member_id)
            sender_id = sender.id if sender is not None else None
            topic_ids = list(dict.fromkeys(request.topic_ids))
            mentioned_member_ids = list(dict.fromkeys(request.mentioned_member_ids))
            existing = next(
                (
                    m
                    for m in state.messages
                    if m.sender_id == sender_id and m.publication_id == request.publication_id
                ),
                None,
            )
            if existing is not None:
                if (
                    existing.content != request.content
                    or set(existing.topic_ids) != set(topic_ids)
                    or set(existing.mentioned_member_ids) != set(mentioned_member_ids)
                    or existing.reply_to_message_id != request.reply_to_message_id
                ):
                    raise RoomConflictError("发布编号已用于另一条消息")
                return existing.model_copy(deep=True)
            if request.reply_to_message_id is not None and not any(
                message.id == request.reply_to_message_id for message in state.messages
            ):
                raise RoomInputError("引用的消息不存在")
            message = self._append_message(
                state,
                content=request.content,
                topic_ids=topic_ids,
                mentioned_member_ids=mentioned_member_ids,
                sender_id=sender_id,
                sender_name=sender.name if sender is not None else "控制台",
                created_at=datetime.now(UTC),
                reply_to_message_id=request.reply_to_message_id,
                publication_id=request.publication_id,
            )
            return message.model_copy(deep=True)

    def publication(
        self, room_id: str, publication_id: str, *, member_id: str | None = None
    ) -> Message:
        with self._transaction(write=False):
            state = self._get_room(room_id)
            sender = self._publisher(state, member_id)
            sender_id = sender.id if sender is not None else None
            for message in state.messages:
                if message.sender_id == sender_id and message.publication_id == publication_id:
                    return message.model_copy(deep=True)
            raise RoomNotFoundError("发布记录不存在")

    @staticmethod
    def _resolve_recipient_ids(
        state: RoomState,
        topic_ids: list[str],
        mentioned_member_ids: list[str],
        *,
        sender_id: str | None,
    ) -> list[str]:
        topics = set(topic_ids)
        mentions = set(mentioned_member_ids)
        if not topics <= {topic.id for topic in state.topics if not topic.deleted_at}:
            raise RoomInputError("消息包含不存在的话题")
        if not mentions <= {member.id for member in state.members if not member.deleted_at}:
            raise RoomInputError("@ 成员不存在")
        recipient_ids = [
            member.id
            for member in state.members
            if not member.deleted_at
            and member.id != sender_id
            and (member.id in mentions or topics.intersection(member.topic_ids))
        ]
        if not recipient_ids:
            if sender_id is not None:
                raise RoomInputError("排除发布成员后没有实际接收人，请选择其他话题或 @ 其他成员")
            raise RoomInputError("所选话题暂无成员，请选择其他话题或 @ 成员")
        return recipient_ids

    def _append_message(
        self,
        state: RoomState,
        *,
        content: str,
        topic_ids: list[str],
        mentioned_member_ids: list[str],
        sender_id: str | None,
        sender_name: str,
        created_at: datetime,
        reply_to_message_id: str | None = None,
        publication_id: str | None = None,
    ) -> Message:
        recipient_ids = self._resolve_recipient_ids(
            state, topic_ids, mentioned_member_ids, sender_id=sender_id
        )
        seq = max((message.seq for message in state.messages), default=0) + 1
        message_id = f"{state.room.id}-msg-{seq:04d}"
        message = Message(
            id=message_id,
            publication_id=publication_id,
            seq=seq,
            sender_id=sender_id,
            sender_name=sender_name,
            content=content,
            topic_ids=topic_ids,
            mentioned_member_ids=mentioned_member_ids,
            recipient_ids=recipient_ids,
            reply_to_message_id=reply_to_message_id,
            created_at=created_at,
            deliveries=[
                Delivery(
                    id=f"{message_id}:{recipient_id}",
                    target_member_id=recipient_id,
                    target_session_id=next(
                        m.session_id for m in state.members if m.id == recipient_id
                    ),
                    client_message_id=str(uuid4()),
                    status="pending",
                    updated_at=created_at,
                )
                for recipient_id in recipient_ids
            ],
        )
        state.messages.append(message)
        return message
