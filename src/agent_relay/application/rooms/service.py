import logging
from copy import deepcopy
from datetime import UTC, datetime
from uuid import uuid4

from agent_relay.application.delivery.ports import QueueDriver, QueueRejected
from agent_relay.application.rooms.contracts import (
    ChangedMember,
    ChangedTopic,
    ClearedMessageQueue,
    CodexQueueClearResult,
    CreateMessage,
    CreateRoom,
    CreateTopic,
    RoomSnapshot,
    UpdateMember,
    UpdateRoom,
)
from agent_relay.application.rooms.ports import RoomStore
from agent_relay.domain.rooms.errors import RoomConflictError, RoomInputError, RoomNotFoundError
from agent_relay.domain.rooms.models import USER_MEMBER_ID, Message, Room, Topic
from agent_relay.domain.rooms.rules import build_message, normalize_project_path, validate_member


class RoomService:
    def __init__(self, store: RoomStore) -> None:
        self.store = store

    def list_rooms(self) -> list[Room]:
        return self.store.queries.rooms()

    def snapshot(self, room_id: str, topic_id: str | None = None) -> RoomSnapshot:
        return self.store.queries.snapshot(room_id, topic_id)

    def create_room(self, request: CreateRoom) -> Room:
        project_path = normalize_project_path(request.project_path)
        with self.store.write_rooms() as rooms:
            if rooms.project_exists(project_path):
                raise RoomConflictError("该项目已有聊天室，请直接打开")
            room = Room(
                id=f"room-{uuid4().hex[:12]}",
                name=request.name,
                project_path=project_path,
                description="",
            )
            rooms.insert_room(room)
            state = rooms.resources(room.id)
            original = deepcopy(state)
            created_at = datetime.now(UTC)
            state.topics.extend(
                Topic(
                    id=f"topic-{uuid4().hex[:12]}",
                    name=name,
                    description="",
                    created_at=created_at,
                )
                for name in ("产品", "架构", "开发", "测试")
            )
            rooms.save_resources(state, original)
            return room.model_copy(deep=True)

    def delete_room(self, room_id: str) -> None:
        with self.store.write_rooms() as rooms:
            rooms.room(room_id)
            rooms.delete_room(room_id)

    def update_room(self, room_id: str, request: UpdateRoom) -> Room:
        with self.store.write_rooms() as rooms:
            state = rooms.resources(room_id)
            original = deepcopy(state)
            state.room.name = request.name
            rooms.save_resources(state, original)
            return state.room.model_copy(deep=True)

    def clear_queue(
        self, room_id: str, *, topic_id: str | None = None, member_id: str | None = None
    ) -> ClearedMessageQueue:
        with self.store.write_rooms() as rooms:
            rooms.room(room_id)
            removed = rooms.clear_queue(
                room_id, topic_id=topic_id, member_id=member_id, deleted_at=datetime.now(UTC)
            )
            return ClearedMessageQueue(removed_messages=removed)

    def clear_queue_with_codex(
        self,
        room_id: str,
        driver: QueueDriver,
        *,
        topic_id: str | None = None,
        member_id: str | None = None,
    ) -> ClearedMessageQueue:
        with self.store.write_rooms() as rooms:
            rooms.room(room_id)
            removed = rooms.clear_queue(
                room_id, topic_id=topic_id, member_id=member_id, deleted_at=datetime.now(UTC)
            )
            targets = rooms.codex_queue_targets(room_id, topic_id=topic_id, member_id=member_id)

        summary = CodexQueueClearResult()
        logger = logging.getLogger(__name__)
        for target in targets:
            if not target.submission_id:
                summary.without_receipt += 1
                continue
            try:
                if driver.delete(target.session_id, target.submission_id):
                    summary.deleted += 1
                else:
                    summary.not_found += 1
            except QueueRejected:
                summary.rejected += 1
                logger.warning("Codex rejected queue deletion for room=%s", room_id, exc_info=True)
            except Exception:
                summary.unknown += 1
                logger.exception("Codex queue deletion outcome unknown for room=%s", room_id)
        return ClearedMessageQueue(removed_messages=removed, codex_queue=summary)

    def update_member(self, room_id: str, member_id: str, request: UpdateMember) -> ChangedMember:
        with self.store.write_rooms() as rooms:
            state = rooms.resources(room_id)
            original = deepcopy(state)
            member = next(
                (item for item in state.members if item.id == member_id and not item.deleted_at),
                None,
            )
            if member is None:
                raise RoomNotFoundError("成员不存在")
            if member.kind == "human":
                raise RoomInputError("不能编辑固定用户成员")
            validate_member(state, request.name, request.topic_ids, member_id)
            member.name = request.name
            member.initials = request.name[:2].upper()
            member.topic_ids = list(dict.fromkeys(request.topic_ids))
            rooms.save_resources(state, original)
            return ChangedMember(**member.model_dump(), metadata=rooms.metadata(room_id))

    def add_topic(self, room_id: str, request: CreateTopic) -> ChangedTopic:
        with self.store.write_rooms() as rooms:
            state = rooms.resources(room_id)
            original = deepcopy(state)
            if any(item.name == request.name and not item.deleted_at for item in state.topics):
                raise RoomConflictError("房间中已有同名话题")
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
        with self.store.write_rooms() as rooms:
            state = rooms.resources(room_id)
            original = deepcopy(state)
            topic = next(
                (item for item in state.topics if item.id == topic_id and not item.deleted_at), None
            )
            if topic is None:
                raise RoomNotFoundError("话题不存在")
            if any(
                item.id != topic_id and not item.deleted_at and item.name == request.name
                for item in state.topics
            ):
                raise RoomConflictError("房间中已有同名话题")
            topic.name = request.name
            topic.description = request.description.strip()
            rooms.save_resources(state, original)
            return ChangedTopic(**topic.model_dump(), metadata=rooms.metadata(room_id))

    def delete_topic(self, room_id: str, topic_id: str) -> ChangedTopic:
        with self.store.write_rooms() as rooms:
            state = rooms.resources(room_id)
            original = deepcopy(state)
            topic = next(
                (item for item in state.topics if item.id == topic_id and not item.deleted_at), None
            )
            if topic is None:
                raise RoomNotFoundError("话题不存在")
            topic.deleted_at = datetime.now(UTC)
            for member in state.members:
                member.topic_ids = [item for item in member.topic_ids if item != topic_id]
            rooms.save_resources(state, original)
            return ChangedTopic(**topic.model_dump(), metadata=rooms.metadata(room_id))

    def delete_member(self, room_id: str, member_id: str) -> ChangedMember:
        with self.store.write_rooms() as rooms:
            state = rooms.resources(room_id)
            original = deepcopy(state)
            member = next(
                (item for item in state.members if item.id == member_id and not item.deleted_at),
                None,
            )
            if member is None:
                raise RoomNotFoundError("成员不存在")
            if member.kind == "human":
                raise RoomInputError("不能删除固定用户成员")
            member.deleted_at = datetime.now(UTC)
            member.topic_ids = []
            rooms.save_resources(state, original)
            return ChangedMember(**member.model_dump(), metadata=rooms.metadata(room_id))

    def post_message(
        self, room_id: str, request: CreateMessage, *, member_id: str | None = None
    ) -> Message:
        with self.store.write_rooms() as rooms:
            rooms.room(room_id)
            sender = rooms.publisher(room_id, member_id)
            if sender.kind == "human" and USER_MEMBER_ID in request.mentioned_member_ids:
                raise RoomInputError("不能将消息发送给自己")
            topic_ids = list(dict.fromkeys(request.topic_ids))
            mentions = list(dict.fromkeys(request.mentioned_member_ids))
            existing = rooms.publication(room_id, sender.id, request.publication_id)
            if existing is not None:
                if (
                    existing.content != request.content
                    or set(existing.topic_ids) != set(topic_ids)
                    or set(existing.mentioned_member_ids) != set(mentions)
                    or existing.reply_to_message_id != request.reply_to_message_id
                ):
                    raise RoomConflictError("发布编号已用于另一条消息")
                return existing.model_copy(deep=True)
            if request.reply_to_message_id is not None and not rooms.message_exists(
                room_id, request.reply_to_message_id
            ):
                raise RoomInputError("引用的消息不存在")
            message = build_message(
                rooms.resources(room_id),
                content=request.content,
                topic_ids=topic_ids,
                mentioned_member_ids=mentions,
                sender_id=sender.id,
                sender_name=sender.name,
                created_at=datetime.now(UTC),
                reply_to_message_id=request.reply_to_message_id,
                publication_id=request.publication_id,
                seq=rooms.next_message_seq(room_id),
            )
            rooms.insert_message(room_id, message)
            return message.model_copy(deep=True)

    def publication(
        self, room_id: str, publication_id: str, *, member_id: str | None = None
    ) -> Message:
        with self.store.read_rooms() as rooms:
            rooms.room(room_id)
            sender = rooms.publisher(room_id, member_id)
            message = rooms.publication(room_id, sender.id, publication_id)
            if message is None:
                raise RoomNotFoundError("发布记录不存在")
            return message.model_copy(deep=True)
