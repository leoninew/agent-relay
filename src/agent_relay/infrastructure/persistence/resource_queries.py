from sqlalchemy import func, select
from sqlalchemy.orm import Session

from agent_relay.application.dto.positions import TopicPosition
from agent_relay.application.dto.rooms import RoomMetadata, RoomSummary
from agent_relay.domain.rooms.errors import RoomNotFoundError
from agent_relay.domain.rooms.models import USER_MEMBER_ID, Member, Room, RoomState
from agent_relay.infrastructure.persistence.mappers import (
    member_from_model,
    room_from_model,
    session_from_model,
    topic_from_model,
)
from agent_relay.infrastructure.persistence.models import (
    DeliveryRecord,
    MemberRecord,
    MemberTopicRecord,
    MessageRecord,
    MessageTopicRecord,
    RoomEventRecord,
    RoomRecord,
    SessionRecord,
    TopicPositionRecord,
    TopicRecord,
)
from agent_relay.infrastructure.persistence.sqlite import insertion_order


class ResourceQueries:
    def __init__(self, session: Session) -> None:
        self.session = session

    def room(self, room_id: str) -> Room:
        record = self.session.get(RoomRecord, room_id)
        if record is None:
            raise RoomNotFoundError("聊天室不存在")
        return room_from_model(record)

    def rooms(self) -> list[Room]:
        return [
            room_from_model(record)
            for record in self.session.scalars(
                select(RoomRecord).order_by(insertion_order("rooms"))
            )
        ]

    def project_exists(self, project_path: str) -> bool:
        return (
            self.session.scalar(
                select(RoomRecord.id).where(RoomRecord.project_path == project_path).limit(1)
            )
            is not None
        )

    def _member(self, record: MemberRecord) -> Member:
        topic_ids = list(
            self.session.scalars(
                select(MemberTopicRecord.topic_id)
                .where(
                    MemberTopicRecord.room_id == record.room_id,
                    MemberTopicRecord.member_id == record.id,
                )
                .order_by(MemberTopicRecord.position)
            )
        )
        return member_from_model(record, topic_ids)

    def publisher(self, room_id: str, member_id: str | None) -> Member:
        record = self.session.scalar(
            select(MemberRecord).where(
                MemberRecord.room_id == room_id,
                MemberRecord.id == (member_id if member_id is not None else USER_MEMBER_ID),
                MemberRecord.deleted_at.is_(None),
            )
        )
        if record is None:
            raise RoomNotFoundError("聊天室成员不存在")
        return self._member(record)

    def member_for_session(self, room_id: str, session_id: str) -> Member:
        self.room(room_id)
        record = self.session.scalar(
            select(MemberRecord).where(
                MemberRecord.room_id == room_id,
                MemberRecord.session_id == session_id,
                MemberRecord.deleted_at.is_(None),
            )
        )
        if record is None:
            raise RoomNotFoundError("该 Codex 会话尚未加入此聊天室")
        return self._member(record)

    def joined_members(self, room_id: str) -> dict[str, str]:
        return {
            session_id: member_id
            for session_id, member_id in self.session.execute(
                select(MemberRecord.session_id, MemberRecord.id).where(
                    MemberRecord.room_id == room_id,
                    MemberRecord.deleted_at.is_(None),
                    MemberRecord.session_id.is_not(None),
                    MemberRecord.kind == "agent",
                )
            )
            if session_id is not None
        }

    def bindings(self) -> list[tuple[str, str]]:
        return [
            (room_id, session_id)
            for room_id, session_id in self.session.execute(
                select(MemberRecord.room_id, MemberRecord.session_id).where(
                    MemberRecord.deleted_at.is_(None),
                    MemberRecord.session_id.is_not(None),
                    MemberRecord.kind == "agent",
                )
            )
            if session_id is not None
        ]

    def resources(self, room_id: str) -> RoomState:
        room = self.room(room_id)
        topics = [
            topic_from_model(record)
            for record in self.session.scalars(
                select(TopicRecord)
                .where(
                    TopicRecord.room_id == room_id,
                )
                .order_by(insertion_order("topics"))
            )
        ]
        subscriptions: dict[str, list[str]] = {}
        for member_id, topic_id in self.session.execute(
            select(MemberTopicRecord.member_id, MemberTopicRecord.topic_id)
            .where(
                MemberTopicRecord.room_id == room_id,
            )
            .order_by(MemberTopicRecord.position)
        ):
            subscriptions.setdefault(member_id, []).append(topic_id)
        members = [
            member_from_model(record, subscriptions.get(record.id, []))
            for record in self.session.scalars(
                select(MemberRecord)
                .where(
                    MemberRecord.room_id == room_id,
                )
                .order_by(MemberRecord.session_id.is_(None), insertion_order("members"))
            )
        ]
        sessions = [
            session_from_model(record)
            for record in self.session.scalars(
                select(SessionRecord)
                .where(
                    SessionRecord.room_id == room_id,
                )
                .order_by(insertion_order("sessions"))
            )
        ]
        return RoomState(room=room, topics=topics, members=members, sessions=sessions)

    def positions(self, room_id: str, member_id: str | None = None) -> list[TopicPosition]:
        position_seq = func.coalesce(TopicPositionRecord.seq, 0)
        topic_matches = (
            select(MessageTopicRecord.message_id)
            .where(
                MessageTopicRecord.room_id == MessageRecord.room_id,
                MessageTopicRecord.message_id == MessageRecord.id,
                MessageTopicRecord.topic_id == MemberTopicRecord.topic_id,
            )
            .correlate(MessageRecord, MemberTopicRecord)
            .exists()
        )
        later_count = (
            select(func.count())
            .select_from(MessageRecord)
            .where(
                MessageRecord.room_id == MemberTopicRecord.room_id,
                MessageRecord.seq > position_seq,
                topic_matches,
            )
            .correlate(MemberTopicRecord, TopicPositionRecord)
            .scalar_subquery()
        )
        statement = (
            select(
                MemberTopicRecord.member_id,
                MemberTopicRecord.topic_id,
                position_seq.label("seq"),
                TopicPositionRecord.updated_at,
                later_count.label("later_count"),
            )
            .select_from(MemberTopicRecord)
            .join(
                MemberRecord,
                (
                    (MemberRecord.room_id == MemberTopicRecord.room_id)
                    & (MemberRecord.id == MemberTopicRecord.member_id)
                    & MemberRecord.deleted_at.is_(None)
                ),
            )
            .join(
                TopicRecord,
                (
                    (TopicRecord.room_id == MemberTopicRecord.room_id)
                    & (TopicRecord.id == MemberTopicRecord.topic_id)
                    & TopicRecord.deleted_at.is_(None)
                ),
            )
            .outerjoin(
                TopicPositionRecord,
                (
                    (TopicPositionRecord.room_id == MemberTopicRecord.room_id)
                    & (TopicPositionRecord.member_id == MemberTopicRecord.member_id)
                    & (TopicPositionRecord.topic_id == MemberTopicRecord.topic_id)
                ),
            )
            .where(MemberTopicRecord.room_id == room_id)
        )
        if member_id is not None:
            statement = statement.where(MemberTopicRecord.member_id == member_id)
        statement = statement.order_by(insertion_order("members"), MemberTopicRecord.position)
        return [
            TopicPosition.model_validate(row._mapping) for row in self.session.execute(statement)
        ]

    def metadata(self, room_id: str) -> RoomMetadata:
        state = self.resources(room_id)
        statuses = {
            status: count
            for status, count in self.session.execute(
                select(DeliveryRecord.status, func.count())
                .where(
                    DeliveryRecord.room_id == room_id,
                    DeliveryRecord.deleted_at.is_(None),
                )
                .group_by(DeliveryRecord.status)
            )
        }
        total = (
            self.session.scalar(
                select(func.count())
                .select_from(MessageRecord)
                .where(
                    MessageRecord.room_id == room_id,
                )
            )
            or 0
        )
        event_id = (
            self.session.scalar(
                select(func.max(RoomEventRecord.event_id)).where(
                    RoomEventRecord.room_id == room_id,
                )
            )
            or 0
        )
        return RoomMetadata(
            room=state.room,
            topics=state.topics,
            members=state.members,
            sessions=state.sessions,
            positions=self.positions(room_id),
            summary=RoomSummary(
                total_messages=total,
                queued_count=statuses.get("queued", 0),
                received_count=statuses.get("received", 0),
                pending_count=statuses.get("pending", 0),
                submitting_count=statuses.get("submitting", 0),
                rejected_count=statuses.get("rejected", 0),
                unknown_count=statuses.get("unknown", 0),
            ),
            event_id=event_id,
        )
