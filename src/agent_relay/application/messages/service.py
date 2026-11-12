import logging
from datetime import UTC, datetime

from agent_relay.application.delivery.ports import QueueDriver, QueueRejected
from agent_relay.application.dto.messages import (
    ClearedMessageQueue,
    CodexQueueClearResult,
    CreateMessage,
)
from agent_relay.application.rooms.ports import RoomStore
from agent_relay.domain.rooms.errors import RoomConflictError, RoomInputError, RoomNotFoundError
from agent_relay.domain.rooms.models import Message
from agent_relay.domain.rooms.rules import (
    build_message,
    validate_publication_replay,
    validate_sender_targets,
)


class MessageService:
    def __init__(self, store: RoomStore) -> None:
        self.store = store

    def post_message(
        self, room_id: str, request: CreateMessage, *, member_id: str | None = None
    ) -> Message:
        with self.store.write() as rooms:
            rooms.room(room_id)
            sender = rooms.publisher(room_id, member_id)
            validate_sender_targets(sender, request.mentioned_member_ids)
            topic_ids = list(dict.fromkeys(request.topic_ids))
            mentions = list(dict.fromkeys(request.mentioned_member_ids))
            existing = rooms.publication(room_id, sender.id, request.publication_id)
            if existing is not None:
                if not rooms.message_exists(room_id, existing.id):
                    raise RoomConflictError("该发布记录已清空，请使用新的发布标识")
                validate_publication_replay(
                    existing,
                    content=request.content,
                    topic_ids=topic_ids,
                    mentions=mentions,
                    reply_to_message_id=request.reply_to_message_id,
                    capabilities=request.capabilities,
                )
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
                capabilities=request.capabilities,
            )
            rooms.insert_message(room_id, message)
            return message.model_copy(deep=True)

    def publication(
        self, room_id: str, publication_id: str, *, member_id: str | None = None
    ) -> Message:
        with self.store.read() as rooms:
            rooms.room(room_id)
            sender = rooms.publisher(room_id, member_id)
            message = rooms.publication(room_id, sender.id, publication_id)
            if message is None or not rooms.message_exists(room_id, message.id):
                raise RoomNotFoundError("发布记录不存在")
            return message.model_copy(deep=True)

    def clear_queue(
        self, room_id: str, *, topic_id: str | None = None, member_id: str | None = None
    ) -> ClearedMessageQueue:
        with self.store.write() as rooms:
            rooms.room(room_id)
            removed = rooms.clear_queue(
                room_id, topic_id=topic_id, member_id=member_id, deleted_at=datetime.now(UTC)
            )
            return ClearedMessageQueue(removed_messages=removed)

    def delete_queue_message(self, room_id: str, message_id: str) -> ClearedMessageQueue:
        with self.store.write() as rooms:
            rooms.room(room_id)
            if not rooms.message_exists(room_id, message_id):
                raise RoomNotFoundError("消息不存在")
            removed = rooms.clear_queue(
                room_id,
                topic_id=None,
                member_id=None,
                message_id=message_id,
                deleted_at=datetime.now(UTC),
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
        with self.store.write() as rooms:
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
