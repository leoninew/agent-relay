from copy import deepcopy
from datetime import UTC, datetime
from pathlib import PurePosixPath, PureWindowsPath
from uuid import uuid4

from agent_relay.room_errors import (
    RoomConflictError,
    RoomInputError,
    RoomNotFoundError,
)
from agent_relay.room_models import (
    USER_MEMBER_ID,
    ChangedMember,
    ChangedTopic,
    CreateMessage,
    CreateRoom,
    CreateTopic,
    Delivery,
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
        self._store = store

    @property
    def store(self) -> SQLiteRoomStore:
        return self._store

    def list_rooms(self) -> list[Room]:
        return RoomQueries(self._store).rooms()

    def create_room(self, request: CreateRoom) -> Room:
        project_path = self._normalize_project_path(request.project_path)
        with self._store.write() as connection:
            if RoomQueries.project_exists_in(connection, project_path):
                raise RoomConflictError("该项目已有聊天室，请直接打开")
            room = Room(
                id=f"room-{uuid4().hex[:12]}",
                name=request.name,
                project_path=project_path,
                description="",
            )
            self._store.insert_room(connection, room)
            return room.model_copy(deep=True)

    def update_member(self, room_id: str, member_id: str, request: UpdateMember) -> ChangedMember:
        with self._store.write() as connection:
            queries = RoomQueries(self._store)
            state = queries.resources_in(connection, room_id)
            original = deepcopy(state)
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
            if member.kind == "human":
                raise RoomInputError("不能编辑固定用户成员")
            self._validate_member(state, request, member_id)
            member.name = request.name
            member.initials = request.name[:2].upper()
            member.topic_ids = list(dict.fromkeys(request.topic_ids))
            self._store.save_resources(connection, state, original)
            return ChangedMember(
                **member.model_dump(), metadata=queries.metadata_in(connection, room_id)
            )

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

    def add_topic(self, room_id: str, request: CreateTopic) -> ChangedTopic:
        with self._store.write() as connection:
            queries = RoomQueries(self._store)
            state = queries.resources_in(connection, room_id)
            original = deepcopy(state)
            if any(topic.name == request.name and not topic.deleted_at for topic in state.topics):
                raise RoomConflictError("房间中已有同名话题")
            topic = Topic(
                id=f"topic-{uuid4().hex[:12]}",
                name=request.name,
                description=request.description.strip(),
            )
            state.topics.append(topic)
            self._store.save_resources(connection, state, original)
            return ChangedTopic(
                **topic.model_dump(), metadata=queries.metadata_in(connection, room_id)
            )

    def update_topic(self, room_id: str, topic_id: str, request: CreateTopic) -> ChangedTopic:
        with self._store.write() as connection:
            queries = RoomQueries(self._store)
            state = queries.resources_in(connection, room_id)
            original = deepcopy(state)
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
            self._store.save_resources(connection, state, original)
            return ChangedTopic(
                **topic.model_dump(), metadata=queries.metadata_in(connection, room_id)
            )

    def delete_topic(self, room_id: str, topic_id: str) -> ChangedTopic:
        with self._store.write() as connection:
            queries = RoomQueries(self._store)
            state = queries.resources_in(connection, room_id)
            original = deepcopy(state)
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
            self._store.save_resources(connection, state, original)
            return ChangedTopic(
                **topic.model_dump(), metadata=queries.metadata_in(connection, room_id)
            )

    def delete_member(self, room_id: str, member_id: str) -> ChangedMember:
        with self._store.write() as connection:
            queries = RoomQueries(self._store)
            state = queries.resources_in(connection, room_id)
            original = deepcopy(state)
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
            if member.kind == "human":
                raise RoomInputError("不能删除固定用户成员")
            member.deleted_at = datetime.now(UTC)
            member.topic_ids = []
            self._store.save_resources(connection, state, original)
            return ChangedMember(
                **member.model_dump(), metadata=queries.metadata_in(connection, room_id)
            )

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

    def post_message(
        self, room_id: str, request: CreateMessage, *, member_id: str | None = None
    ) -> Message:
        queries = RoomQueries(self._store)
        with self._store.write() as connection:
            queries.room_in(connection, room_id)
            sender = queries.publisher_in(connection, room_id, member_id)
            sender_id = sender.id
            if sender.kind == "human" and USER_MEMBER_ID in request.mentioned_member_ids:
                raise RoomInputError("不能将消息发送给自己")
            topic_ids = list(dict.fromkeys(request.topic_ids))
            mentioned_member_ids = list(dict.fromkeys(request.mentioned_member_ids))
            existing = queries.publication_in(
                connection, room_id, sender_id, request.publication_id
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
            if request.reply_to_message_id is not None and not queries.message_exists_in(
                connection, room_id, request.reply_to_message_id
            ):
                raise RoomInputError("引用的消息不存在")
            state = queries.resources_in(connection, room_id)
            message = self._build_message(
                state,
                content=request.content,
                topic_ids=topic_ids,
                mentioned_member_ids=mentioned_member_ids,
                sender_id=sender_id,
                sender_name=sender.name,
                created_at=datetime.now(UTC),
                reply_to_message_id=request.reply_to_message_id,
                publication_id=request.publication_id,
                seq=queries.next_message_seq_in(connection, room_id),
            )
            self._store.insert_message(connection, room_id, message)
            return message.model_copy(deep=True)

    def publication(
        self, room_id: str, publication_id: str, *, member_id: str | None = None
    ) -> Message:
        queries = RoomQueries(self._store)
        with self._store.read() as connection:
            queries.room_in(connection, room_id)
            sender = queries.publisher_in(connection, room_id, member_id)
            message = queries.publication_in(connection, room_id, sender.id, publication_id)
            if message is None:
                raise RoomNotFoundError("发布记录不存在")
            return message.model_copy(deep=True)

    @staticmethod
    def _resolve_recipient_ids(
        state: RoomState,
        topic_ids: list[str],
        mentioned_member_ids: list[str],
        *,
        sender_id: str,
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
            if sender_id != USER_MEMBER_ID:
                raise RoomInputError("排除发布成员后没有实际接收人，请选择其他话题或 @ 其他成员")
            raise RoomInputError("所选话题暂无成员，请选择其他话题或 @ 成员")
        return recipient_ids

    def _build_message(
        self,
        state: RoomState,
        *,
        content: str,
        topic_ids: list[str],
        mentioned_member_ids: list[str],
        sender_id: str,
        sender_name: str,
        created_at: datetime,
        seq: int,
        reply_to_message_id: str | None = None,
        publication_id: str | None = None,
    ) -> Message:
        recipient_ids = self._resolve_recipient_ids(
            state,
            topic_ids,
            mentioned_member_ids,
            sender_id=sender_id,
        )
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
                    target_session_id=member.session_id,
                    client_message_id=str(uuid4()),
                    status="pending",
                    updated_at=created_at,
                )
                for recipient_id in recipient_ids
                for member in state.members
                if member.id == recipient_id
                and member.kind == "agent"
                and member.session_id is not None
            ],
        )
        return message
