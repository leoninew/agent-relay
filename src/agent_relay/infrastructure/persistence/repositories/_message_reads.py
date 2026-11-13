from collections.abc import Sequence

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from agent_relay.application.dto.messages import MessagePage, MessageQueuePage
from agent_relay.domain.rooms.delivery import ACTIVE_DELIVERY_STATUSES
from agent_relay.domain.rooms.errors import RoomNotFoundError
from agent_relay.domain.rooms.models import Delivery, Message
from agent_relay.infrastructure.persistence.mappers import delivery_from_model, message_from_model
from agent_relay.infrastructure.persistence.models import (
    DeliveryRecord,
    MemberRecord,
    MessageMentionRecord,
    MessageRecipientRecord,
    MessageRecord,
    MessageTopicRecord,
    TopicRecord,
)
from agent_relay.infrastructure.persistence.sqlite import insertion_order, literal_contains


class SQLAlchemyMessageReads:
    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def statement(*, include_deleted: bool = False) -> Select[tuple[MessageRecord, str]]:
        statement = select(MessageRecord, MemberRecord.name).join(
            MemberRecord,
            (MemberRecord.room_id == MessageRecord.room_id)
            & (MemberRecord.id == MessageRecord.publisher_id),
        )
        return statement if include_deleted else statement.where(MessageRecord.deleted_at.is_(None))

    def scope(
        self, room_id: str, *, topic_id: str | None, member_id: str | None
    ) -> ColumnElement[bool]:
        criteria: list[ColumnElement[bool]] = [
            MessageRecord.room_id == room_id,
            MessageRecord.deleted_at.is_(None),
        ]
        if topic_id is not None:
            if self.session.get(TopicRecord, (room_id, topic_id)) is None:
                raise RoomNotFoundError("话题不存在", code="topic_not_found")
            criteria.append(
                select(MessageTopicRecord.message_id)
                .where(
                    MessageTopicRecord.room_id == MessageRecord.room_id,
                    MessageTopicRecord.message_id == MessageRecord.id,
                    MessageTopicRecord.topic_id == topic_id,
                )
                .correlate(MessageRecord)
                .exists()
            )
        if member_id is not None:
            if self.session.get(MemberRecord, (room_id, member_id)) is None:
                raise RoomNotFoundError("成员不存在", code="member_not_found")
            criteria.append(
                or_(
                    MessageRecord.publisher_id == member_id,
                    select(MessageRecipientRecord.message_id)
                    .where(
                        MessageRecipientRecord.room_id == MessageRecord.room_id,
                        MessageRecipientRecord.message_id == MessageRecord.id,
                        MessageRecipientRecord.member_id == member_id,
                    )
                    .correlate(MessageRecord)
                    .exists(),
                )
            )
        return and_(*criteria)

    def _relations(self, statement: Select[tuple[str, str]]) -> dict[str, list[str]]:
        relations: dict[str, list[str]] = {}
        for message_id, target_id in self.session.execute(statement):
            relations.setdefault(message_id, []).append(target_id)
        return relations

    def load(
        self,
        room_id: str,
        rows: Sequence[tuple[MessageRecord, str]],
        *,
        include_deliveries: bool = True,
    ) -> list[Message]:
        if not rows:
            return []
        message_ids = [record.id for record, sender_name in rows]
        topics = self._relations(
            select(MessageTopicRecord.message_id, MessageTopicRecord.topic_id)
            .where(
                MessageTopicRecord.room_id == room_id,
                MessageTopicRecord.message_id.in_(message_ids),
            )
            .order_by(MessageTopicRecord.position)
        )
        mentions = self._relations(
            select(MessageMentionRecord.message_id, MessageMentionRecord.member_id)
            .where(
                MessageMentionRecord.room_id == room_id,
                MessageMentionRecord.message_id.in_(message_ids),
            )
            .order_by(MessageMentionRecord.position)
        )
        recipients = self._relations(
            select(MessageRecipientRecord.message_id, MessageRecipientRecord.member_id)
            .where(
                MessageRecipientRecord.room_id == room_id,
                MessageRecipientRecord.message_id.in_(message_ids),
            )
            .order_by(MessageRecipientRecord.position)
        )
        deliveries: dict[str, list[Delivery]] = {}
        if include_deliveries:
            for record in self.session.scalars(
                select(DeliveryRecord)
                .where(
                    DeliveryRecord.room_id == room_id,
                    DeliveryRecord.message_id.in_(message_ids),
                )
                .order_by(insertion_order("deliveries"))
            ):
                deliveries.setdefault(record.message_id, []).append(delivery_from_model(record))
        return [
            message_from_model(
                record,
                sender_name=sender_name,
                topic_ids=topics.get(record.id, []),
                mentioned_member_ids=mentions.get(record.id, []),
                recipient_ids=recipients.get(record.id, []),
                deliveries=deliveries.get(record.id, []),
            )
            for record, sender_name in rows
        ]

    def read(
        self,
        room_id: str,
        statement: Select[tuple[MessageRecord, str]],
        *,
        include_deliveries: bool = True,
    ) -> list[Message]:
        return self.load(
            room_id,
            self.session.execute(statement).tuples().all(),
            include_deliveries=include_deliveries,
        )

    def message(self, room_id: str, message_id: str) -> Message:
        messages = self.read(
            room_id,
            self.statement().where(
                MessageRecord.room_id == room_id, MessageRecord.id == message_id
            ),
        )
        if not messages:
            raise RoomNotFoundError("消息不存在", code="message_not_found")
        return messages[0]

    def publication(self, room_id: str, publisher_id: str, publication_id: str) -> Message | None:
        messages = self.read(
            room_id,
            self.statement(include_deleted=True).where(
                MessageRecord.room_id == room_id,
                MessageRecord.publisher_id == publisher_id,
                MessageRecord.publication_id == publication_id,
            ),
        )
        return messages[0] if messages else None

    def message_exists(self, room_id: str, message_id: str) -> bool:
        return (
            self.session.scalar(
                select(MessageRecord.id).where(
                    MessageRecord.room_id == room_id,
                    MessageRecord.id == message_id,
                    MessageRecord.deleted_at.is_(None),
                )
            )
            is not None
        )

    def next_message_seq(self, room_id: str) -> int:
        return int(
            self.session.scalar(
                select(func.coalesce(func.max(MessageRecord.seq), 0) + 1).where(
                    MessageRecord.room_id == room_id
                )
            )
            or 1
        )

    def page(
        self,
        room_id: str,
        *,
        topic_id: str | None = None,
        member_id: str | None = None,
        keyword: str | None = None,
        before_seq: int | None = None,
        limit: int = 50,
    ) -> MessagePage:
        criteria = self.scope(room_id, topic_id=topic_id, member_id=member_id)
        if keyword and keyword.strip():
            criteria = and_(
                criteria, literal_contains(MessageRecord.content.expression, keyword.strip())
            )
        newer = (
            before_seq is not None
            and self.session.scalar(
                select(MessageRecord.id).where(criteria, MessageRecord.seq >= before_seq).limit(1)
            )
            is not None
        )
        if before_seq is not None:
            criteria = and_(criteria, MessageRecord.seq < before_seq)
        rows = (
            self.session.execute(
                self.statement().where(criteria).order_by(MessageRecord.seq.desc()).limit(limit + 1)
            )
            .tuples()
            .all()
        )
        more = len(rows) > limit
        messages = self.load(room_id, list(reversed(rows[:limit])))
        return MessagePage(
            messages=messages,
            has_more=more,
            next_before_seq=messages[0].seq if more else None,
            has_newer=newer,
        )

    def queue(
        self,
        room_id: str,
        *,
        topic_id: str | None = None,
        member_id: str | None = None,
        before_seq: int | None = None,
        limit: int = 50,
    ) -> MessageQueuePage:
        active = (
            select(DeliveryRecord.id)
            .where(
                DeliveryRecord.room_id == MessageRecord.room_id,
                DeliveryRecord.message_id == MessageRecord.id,
                DeliveryRecord.deleted_at.is_(None),
                DeliveryRecord.status.in_(ACTIVE_DELIVERY_STATUSES),
            )
            .correlate(MessageRecord)
            .exists()
        )
        criteria = and_(self.scope(room_id, topic_id=topic_id, member_id=member_id), active)
        total = self.session.scalar(select(func.count()).select_from(MessageRecord).where(criteria))
        if before_seq is not None:
            criteria = and_(criteria, MessageRecord.seq < before_seq)
        rows = (
            self.session.execute(
                self.statement().where(criteria).order_by(MessageRecord.seq.desc()).limit(limit + 1)
            )
            .tuples()
            .all()
        )
        more = len(rows) > limit
        messages = self.load(room_id, rows[:limit])
        return MessageQueuePage(
            messages=messages,
            total_messages=total or 0,
            has_more=more,
            next_before_seq=messages[-1].seq if more else None,
        )
