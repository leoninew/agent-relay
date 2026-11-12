from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from agent_relay.application.messages.ports import CodexQueueTarget
from agent_relay.domain.rooms.delivery import ACTIVE_DELIVERY_STATUSES
from agent_relay.domain.rooms.models import Message
from agent_relay.infrastructure.persistence.mappers import delivery_to_model
from agent_relay.infrastructure.persistence.message_queries import MessageQueries
from agent_relay.infrastructure.persistence.models import (
    DeliveryRecord,
    MessageMentionRecord,
    MessageRecipientRecord,
    MessageRecord,
    MessageTopicRecord,
    RoomEventRecord,
)


class SQLAlchemyMessageRepository:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.messages = MessageQueries(session)

    def publication(self, room_id: str, publisher_id: str, publication_id: str) -> Message | None:
        return self.messages.publication(room_id, publisher_id, publication_id)

    def message_exists(self, room_id: str, message_id: str) -> bool:
        return self.messages.message_exists(room_id, message_id)

    def next_message_seq(self, room_id: str) -> int:
        return self.messages.next_message_seq(room_id)

    def insert_message(self, room_id: str, message: Message) -> None:
        self.session.add(
            MessageRecord(
                room_id=room_id,
                id=message.id,
                seq=message.seq,
                publisher_id=message.sender_id,
                publication_id=message.publication_id,
                content=message.content,
                capabilities=message.capabilities,
                reply_to_message_id=message.reply_to_message_id,
                created_at=message.created_at,
            )
        )
        self.session.flush()
        self.session.add_all(
            MessageTopicRecord(
                room_id=room_id, message_id=message.id, topic_id=topic_id, position=position
            )
            for position, topic_id in enumerate(message.topic_ids)
        )
        self.session.add_all(
            MessageMentionRecord(
                room_id=room_id, message_id=message.id, member_id=member_id, position=position
            )
            for position, member_id in enumerate(message.mentioned_member_ids)
        )
        self.session.add_all(
            MessageRecipientRecord(
                room_id=room_id, message_id=message.id, member_id=member_id, position=position
            )
            for position, member_id in enumerate(message.recipient_ids)
        )
        self.session.add(
            RoomEventRecord(
                room_id=room_id, kind="message", entity_id=message.id, message_id=message.id
            )
        )
        self.session.flush()
        for delivery in message.deliveries:
            self.session.add(delivery_to_model(room_id, message.id, delivery))
            self.session.add(
                RoomEventRecord(
                    room_id=room_id, kind="delivery", entity_id=delivery.id, message_id=message.id
                )
            )
        self.session.flush()

    def clear_queue(
        self,
        room_id: str,
        *,
        topic_id: str | None,
        member_id: str | None,
        deleted_at: datetime,
        message_id: str | None = None,
    ) -> int:
        scope = self.messages.scope(room_id, topic_id=topic_id, member_id=member_id)
        if message_id is not None:
            scope &= MessageRecord.id == message_id
        criteria = (
            (DeliveryRecord.room_id == room_id)
            & DeliveryRecord.deleted_at.is_(None)
            & DeliveryRecord.status.in_(ACTIVE_DELIVERY_STATUSES)
            & DeliveryRecord.message_id.in_(select(MessageRecord.id).where(scope))
        )
        events = (
            self.session.execute(
                select(DeliveryRecord.id, DeliveryRecord.message_id).where(criteria)
            )
            .tuples()
            .all()
        )
        self.session.execute(
            update(DeliveryRecord)
            .where(criteria)
            .values(deleted_at=deleted_at, updated_at=deleted_at)
            .execution_options(synchronize_session="fetch")
        )
        self.session.add_all(
            RoomEventRecord(
                room_id=room_id, kind="delivery", entity_id=delivery_id, message_id=message_id
            )
            for delivery_id, message_id in events
        )
        self.session.flush()
        return len({message_id for delivery_id, message_id in events})

    def codex_queue_targets(
        self, room_id: str, *, topic_id: str | None, member_id: str | None
    ) -> list[CodexQueueTarget]:
        scope = self.messages.scope(room_id, topic_id=topic_id, member_id=member_id)
        return [
            CodexQueueTarget(session_id, submission_id)
            for session_id, submission_id in self.session.execute(
                select(DeliveryRecord.target_session_id, DeliveryRecord.queued_submission_id).where(
                    DeliveryRecord.room_id == room_id,
                    DeliveryRecord.deleted_at.is_not(None),
                    DeliveryRecord.status.in_(("submitting", "queued")),
                    DeliveryRecord.submission_method.is_distinct_from("steer"),
                    DeliveryRecord.message_id.in_(select(MessageRecord.id).where(scope)),
                )
            )
        ]
