from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from agent_relay.application.members.context import (
    CatalogMember,
    CatalogTopic,
    ContextMessage,
    ContextQuery,
    ContextResult,
    MemberCatalog,
)
from agent_relay.domain.rooms.errors import RoomNotFoundError
from agent_relay.domain.rooms.models import TopicPosition
from agent_relay.domain.rooms.positions import position_updates, require_subscribed_topic
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

    def _subscriptions(self, room_id: str, member_id: str) -> set[str]:
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
        subscriptions = self._subscriptions(room_id, member_id)
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

    def positions(self, room_id: str, member_id: str) -> list[TopicPosition]:
        self._subscriptions(room_id, member_id)
        return self.resources.positions(room_id, member_id)

    @staticmethod
    def _visibility(member_id: str, subscriptions: set[str]) -> ColumnElement[bool]:
        delivered = (
            select(DeliveryRecord.message_id)
            .where(
                DeliveryRecord.room_id == MessageRecord.room_id,
                DeliveryRecord.message_id == MessageRecord.id,
                DeliveryRecord.target_member_id == member_id,
            )
            .correlate(MessageRecord)
            .exists()
        )
        subscribed = (
            select(MessageTopicRecord.message_id)
            .where(
                MessageTopicRecord.room_id == MessageRecord.room_id,
                MessageTopicRecord.message_id == MessageRecord.id,
                MessageTopicRecord.topic_id.in_(subscriptions),
            )
            .correlate(MessageRecord)
            .exists()
        )
        return or_(MessageRecord.publisher_id == member_id, delivered, subscribed)

    def _select(
        self, room_id: str, member_id: str, request: ContextQuery, subscriptions: set[str]
    ) -> tuple[list[ContextMessage], bool]:
        require_subscribed_topic(request.topic_id, subscriptions)
        statement = self.messages.statement().where(
            MessageRecord.room_id == room_id, self._visibility(member_id, subscriptions)
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

    def _record(
        self,
        room_id: str,
        member_id: str,
        request: ContextQuery,
        subscriptions: set[str],
        messages: list[ContextMessage],
    ) -> str | None:
        if not messages:
            return None
        query_id = str(uuid4())
        now = datetime.now(UTC)
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
                provided_at=now,
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
        updates = position_updates(
            subscriptions,
            request.topic_id,
            ((message.seq, message.topic_ids) for message in messages),
        )
        for topic_id, seq in sorted(updates.items()):
            self._advance_position(room_id, member_id, topic_id, seq, now)
        self.session.flush()
        return query_id

    def query(self, room_id: str, member_id: str, request: ContextQuery) -> ContextResult:
        subscriptions = self._subscriptions(room_id, member_id)
        messages, more = self._select(room_id, member_id, request, subscriptions)
        query_id = self._record(room_id, member_id, request, subscriptions, messages)
        forward = request.after_seq is not None
        return ContextResult(
            query_id=query_id,
            messages=messages,
            has_more=more,
            next_before_seq=messages[0].seq if more and not forward else None,
            next_after_seq=messages[-1].seq if more and forward else None,
            positions=self.resources.positions(room_id, member_id),
        )
