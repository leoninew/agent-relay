from datetime import datetime

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from agent_relay.application.dto.context import (
    CatalogMember,
    CatalogTopic,
    ContextMessage,
    ContextQuery,
    MemberCatalog,
)
from agent_relay.application.dto.positions import TopicPosition
from agent_relay.domain.rooms.errors import RoomNotFoundError
from agent_relay.domain.rooms.models import VisibilityScope
from agent_relay.infrastructure.persistence.message_queries import MessageQueries
from agent_relay.infrastructure.persistence.models import (
    ContextMessageRecord,
    ContextQueryRecord,
    DeliveryRecord,
    MemberRecord,
    MemberTopicRecord,
    MessageRecord,
    MessageTopicRecord,
    RoomEventRecord,
    TopicPositionRecord,
    TopicRecord,
)
from agent_relay.infrastructure.persistence.resource_queries import ResourceQueries
from agent_relay.infrastructure.persistence.sqlite import insertion_order, literal_contains


class SQLAlchemyContextRepository:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.resources = ResourceQueries(session)
        self.messages = MessageQueries(session)

    def subscriptions(self, room_id: str, member_id: str) -> set[str]:
        member = self.session.scalar(
            select(MemberRecord.id).where(
                MemberRecord.room_id == room_id,
                MemberRecord.id == member_id,
                MemberRecord.deleted_at.is_(None),
            )
        )
        if member is None:
            raise RoomNotFoundError("聊天室成员不存在")
        return set(
            self.session.scalars(
                select(MemberTopicRecord.topic_id)
                .join(
                    TopicRecord,
                    (TopicRecord.room_id == MemberTopicRecord.room_id)
                    & (TopicRecord.id == MemberTopicRecord.topic_id)
                    & TopicRecord.deleted_at.is_(None),
                )
                .where(
                    MemberTopicRecord.room_id == room_id,
                    MemberTopicRecord.member_id == member_id,
                )
            )
        )

    def catalog(self, room_id: str, member_id: str) -> MemberCatalog:
        subscriptions = self.subscriptions(room_id, member_id)
        room = self.resources.room(room_id)
        topics = [
            CatalogTopic(
                id=record.id,
                name=record.name,
                description=record.description,
                subscribed=record.id in subscriptions,
            )
            for record in self.session.scalars(
                select(TopicRecord)
                .where(TopicRecord.room_id == room_id, TopicRecord.deleted_at.is_(None))
                .order_by(insertion_order("topics"))
            )
        ]
        member_topics: dict[str, list[str]] = {}
        for target_id, topic_id in self.session.execute(
            select(MemberTopicRecord.member_id, MemberTopicRecord.topic_id)
            .where(MemberTopicRecord.room_id == room_id)
            .order_by(MemberTopicRecord.position)
        ):
            member_topics.setdefault(target_id, []).append(topic_id)
        members = [
            CatalogMember.model_validate(
                {
                    "id": record.id,
                    "kind": record.kind,
                    "name": record.name,
                    "topic_ids": member_topics.get(record.id, []),
                }
            )
            for record in self.session.scalars(
                select(MemberRecord)
                .where(MemberRecord.room_id == room_id, MemberRecord.deleted_at.is_(None))
                .order_by(insertion_order("members"))
            )
        ]
        return MemberCatalog(
            room_id=room.id,
            room_name=room.name,
            room_description=room.description,
            project_path=room.project_path,
            member_id=member_id,
            topics=topics,
            members=members,
        )

    def load_positions(self, room_id: str, member_id: str) -> list[TopicPosition]:
        return self.resources.positions(room_id, member_id)

    @staticmethod
    def _visibility(scope: VisibilityScope) -> ColumnElement[bool]:
        delivered = (
            select(DeliveryRecord.message_id)
            .where(
                DeliveryRecord.room_id == MessageRecord.room_id,
                DeliveryRecord.message_id == MessageRecord.id,
                DeliveryRecord.target_member_id == scope.delivery_member_id,
            )
            .correlate(MessageRecord)
            .exists()
        )
        subscribed = (
            select(MessageTopicRecord.message_id)
            .where(
                MessageTopicRecord.room_id == MessageRecord.room_id,
                MessageTopicRecord.message_id == MessageRecord.id,
                MessageTopicRecord.topic_id.in_(scope.topic_ids),
            )
            .correlate(MessageRecord)
            .exists()
        )
        return or_(MessageRecord.publisher_id == scope.publisher_id, delivered, subscribed)

    def select_messages(
        self, room_id: str, request: ContextQuery, scope: VisibilityScope
    ) -> tuple[list[ContextMessage], bool]:
        statement = self.messages.statement().where(
            MessageRecord.room_id == room_id, self._visibility(scope)
        )
        if request.message_id is not None:
            statement = statement.where(MessageRecord.id == request.message_id)
        if request.topic_id is not None:
            statement = statement.where(
                select(MessageTopicRecord.message_id)
                .where(
                    MessageTopicRecord.room_id == MessageRecord.room_id,
                    MessageTopicRecord.message_id == MessageRecord.id,
                    MessageTopicRecord.topic_id == request.topic_id,
                )
                .correlate(MessageRecord)
                .exists()
            )
        if request.keyword is not None:
            statement = statement.where(
                literal_contains(MessageRecord.content.expression, request.keyword)
            )
        if request.before_seq is not None:
            statement = statement.where(MessageRecord.seq < request.before_seq)
        if request.after_seq is not None:
            statement = statement.where(MessageRecord.seq > request.after_seq)
        forward = request.after_seq is not None
        statement = statement.order_by(
            MessageRecord.seq.asc() if forward else MessageRecord.seq.desc()
        ).limit(request.limit + 1)
        rows = self.session.execute(statement).tuples().all()
        if request.message_id is not None and not rows:
            raise RoomNotFoundError("消息不存在或不在查阅范围内")
        messages = [
            ContextMessage.model_validate(message.model_dump())
            for message in self.messages.load(
                room_id, rows[: request.limit], include_deliveries=False
            )
        ]
        if not forward:
            messages.reverse()
        return messages, len(rows) > request.limit

    def _advance_position(
        self, room_id: str, member_id: str, topic_id: str, seq: int, now: datetime
    ) -> None:
        criteria = (
            (TopicPositionRecord.room_id == room_id)
            & (TopicPositionRecord.member_id == member_id)
            & (TopicPositionRecord.topic_id == topic_id)
        )
        current = self.session.scalar(select(TopicPositionRecord.seq).where(criteria))
        if current is None:
            self.session.add(
                TopicPositionRecord(
                    room_id=room_id, member_id=member_id, topic_id=topic_id, seq=seq, updated_at=now
                )
            )
            self.session.flush()
        else:
            changed = self.session.scalar(
                update(TopicPositionRecord)
                .where(criteria, TopicPositionRecord.seq < seq)
                .values(seq=seq, updated_at=now)
                .returning(TopicPositionRecord.topic_id)
                .execution_options(synchronize_session="fetch")
            )
            if changed is None:
                return
        self.session.add(RoomEventRecord(room_id=room_id, kind="position", entity_id=member_id))

    def record_provision(
        self,
        room_id: str,
        member_id: str,
        request: ContextQuery,
        messages: list[ContextMessage],
        updates: dict[str, int],
        query_id: str,
        provided_at: datetime,
    ) -> None:
        self.session.add(
            ContextQueryRecord(
                id=query_id,
                room_id=room_id,
                member_id=member_id,
                message_id=request.message_id,
                topic_id=request.topic_id,
                keyword=request.keyword,
                before_seq=request.before_seq,
                after_seq=request.after_seq,
                page_limit=request.limit,
                provided_at=provided_at,
            )
        )
        self.session.flush()
        self.session.add_all(
            ContextMessageRecord(
                room_id=room_id, query_id=query_id, message_id=message.id, position=position
            )
            for position, message in enumerate(messages)
        )
        self.session.flush()
        for topic_id, seq in sorted(updates.items()):
            self._advance_position(room_id, member_id, topic_id, seq, provided_at)
        self.session.flush()
