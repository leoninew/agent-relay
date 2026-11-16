from collections import defaultdict
from datetime import datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from conflua.application.dto.desktop import ShutdownNotificationTarget
from conflua.application.dto.positions import TopicPosition
from conflua.application.dto.rooms import RoomEvent, RoomEventPage, RoomMetadata, RoomSummary
from conflua.domain.rooms.errors import RoomConflictError, RoomNotFoundError
from conflua.domain.rooms.models import (
    USER_MEMBER_ID,
    Member,
    Room,
    RoomState,
)
from conflua.infrastructure.persistence.mappers import (
    member_from_model,
    room_from_model,
    session_from_model,
    topic_from_model,
)
from conflua.infrastructure.persistence.models import (
    ChannelRecord,
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
from conflua.infrastructure.persistence.sqlite import insertion_order


class SQLAlchemyRoomReads:
    def __init__(self, session: Session, channel_id: str) -> None:
        self.session = session
        self.channel_id = channel_id

    def room(self, room_id: str) -> Room:
        record = self.session.get(RoomRecord, room_id)
        if record is None or record.archived_at is not None:
            raise RoomNotFoundError("聊天室不存在", code="room_not_found")
        channel = self.session.get(ChannelRecord, (room_id, self.channel_id))
        if channel is None:
            raise RoomNotFoundError("频道不存在", code="channel_not_found")
        if channel.archived_at is not None:
            raise RoomConflictError("频道当前不可用", code="channel_unavailable")
        return room_from_model(record)

    def working_path(self, room_id: str) -> str:
        self.room(room_id)
        channel = self.session.get(ChannelRecord, (room_id, self.channel_id))
        if channel is None:
            raise RoomNotFoundError("频道不存在", code="channel_not_found")
        if channel.archived_at is not None:
            raise RoomConflictError("频道当前不可用", code="channel_unavailable")
        if channel.workspace_kind == "worktree" and not Path(channel.working_path).is_dir():
            raise RoomConflictError("频道工作目录不存在", code="channel_directory_missing")
        return channel.working_path

    def rooms(self) -> list[Room]:
        return [
            room_from_model(record)
            for record in self.session.scalars(
                select(RoomRecord)
                .where(RoomRecord.archived_at.is_(None))
                .order_by(insertion_order("rooms"))
            )
        ]

    def project_exists(self, project_path: str) -> bool:
        return (
            self.session.scalar(
                select(RoomRecord.id)
                .where(RoomRecord.project_path == project_path, RoomRecord.archived_at.is_(None))
                .limit(1)
            )
            is not None
        ) or self.session.scalar(
            select(ChannelRecord.id)
            .where(
                ChannelRecord.working_path_key == project_path,
                ChannelRecord.workspace_kind == "worktree",
                ChannelRecord.archived_at.is_(None),
            )
            .limit(1)
        ) is not None

    def _member(self, record: MemberRecord) -> Member:
        topic_ids = list(
            self.session.scalars(
                select(MemberTopicRecord.topic_id)
                .where(
                    MemberTopicRecord.room_id == record.room_id,
                    MemberTopicRecord.channel_id == record.channel_id,
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
                MemberRecord.channel_id == self.channel_id,
                MemberRecord.id == (member_id if member_id is not None else USER_MEMBER_ID),
                MemberRecord.deleted_at.is_(None),
            )
        )
        if record is None:
            raise RoomNotFoundError("聊天室成员不存在", code="member_not_found")
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
            raise RoomNotFoundError("该 Codex 会话尚未加入此聊天室", code="session_not_joined")
        if record.channel_id != self.channel_id:
            raise RoomConflictError("请显式选择会话所属频道", code="channel_required")
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

    def bindings(self) -> list[tuple[str, str, str]]:
        return [
            (room_id, channel_id, session_id)
            for room_id, channel_id, session_id in self.session.execute(
                select(
                    MemberRecord.room_id, MemberRecord.channel_id, MemberRecord.session_id
                ).where(
                    MemberRecord.deleted_at.is_(None),
                    MemberRecord.session_id.is_not(None),
                    MemberRecord.kind == "agent",
                )
            )
            if session_id is not None
        ]

    def resources(self, room_id: str) -> RoomState:
        room = self.room(room_id)
        working_path = self.working_path(room_id)
        topics = [
            topic_from_model(record)
            for record in self.session.scalars(
                select(TopicRecord)
                .where(
                    TopicRecord.room_id == room_id,
                    TopicRecord.channel_id == self.channel_id,
                )
                .order_by(insertion_order("topics"))
            )
        ]
        subscriptions: dict[str, list[str]] = {}
        for member_id, topic_id in self.session.execute(
            select(MemberTopicRecord.member_id, MemberTopicRecord.topic_id)
            .where(
                MemberTopicRecord.room_id == room_id,
                MemberTopicRecord.channel_id == self.channel_id,
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
                    MemberRecord.channel_id == self.channel_id,
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
        return RoomState(
            room=room,
            channel_id=self.channel_id,
            working_path=working_path,
            topics=topics,
            members=members,
            sessions=sessions,
        )

    def positions(self, room_id: str, member_id: str | None = None) -> list[TopicPosition]:
        position_seq = func.coalesce(TopicPositionRecord.seq, 0)
        topic_matches = (
            select(MessageTopicRecord.message_id)
            .where(
                MessageTopicRecord.room_id == MessageRecord.room_id,
                MessageTopicRecord.channel_id == MessageRecord.channel_id,
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
                MessageRecord.channel_id == MemberTopicRecord.channel_id,
                MessageRecord.deleted_at.is_(None),
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
                    & (MemberRecord.channel_id == MemberTopicRecord.channel_id)
                    & (MemberRecord.id == MemberTopicRecord.member_id)
                    & MemberRecord.deleted_at.is_(None)
                ),
            )
            .join(
                TopicRecord,
                (
                    (TopicRecord.room_id == MemberTopicRecord.room_id)
                    & (TopicRecord.channel_id == MemberTopicRecord.channel_id)
                    & (TopicRecord.id == MemberTopicRecord.topic_id)
                    & TopicRecord.deleted_at.is_(None)
                ),
            )
            .outerjoin(
                TopicPositionRecord,
                (
                    (TopicPositionRecord.room_id == MemberTopicRecord.room_id)
                    & (TopicPositionRecord.channel_id == MemberTopicRecord.channel_id)
                    & (TopicPositionRecord.member_id == MemberTopicRecord.member_id)
                    & (TopicPositionRecord.topic_id == MemberTopicRecord.topic_id)
                ),
            )
            .where(
                MemberTopicRecord.room_id == room_id,
                MemberTopicRecord.channel_id == self.channel_id,
            )
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
                    DeliveryRecord.channel_id == self.channel_id,
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
                    MessageRecord.channel_id == self.channel_id,
                    MessageRecord.deleted_at.is_(None),
                )
            )
            or 0
        )
        event_id = (
            self.session.scalar(
                select(func.max(RoomEventRecord.event_id)).where(
                    RoomEventRecord.room_id == room_id,
                    RoomEventRecord.channel_id == self.channel_id,
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

    def events(self, room_id: str, after_event_id: int, limit: int = 200) -> RoomEventPage:
        self.working_path(room_id)
        if (
            self.session.scalar(
                select(RoomEventRecord.event_id)
                .where(
                    RoomEventRecord.room_id == room_id,
                    RoomEventRecord.channel_id == self.channel_id,
                    RoomEventRecord.kind == "clear",
                    RoomEventRecord.event_id > after_event_id,
                )
                .limit(1)
            )
            is not None
        ):
            return self._resync(room_id)
        if (
            after_event_id
            and self.session.scalar(
                select(RoomEventRecord.event_id).where(
                    RoomEventRecord.room_id == room_id,
                    RoomEventRecord.event_id == after_event_id,
                )
            )
            is None
        ):
            return self._resync(room_id)
        rows = list(
            self.session.scalars(
                select(RoomEventRecord)
                .where(
                    RoomEventRecord.room_id == room_id,
                    RoomEventRecord.event_id > after_event_id,
                    RoomEventRecord.channel_id == self.channel_id,
                )
                .order_by(RoomEventRecord.event_id)
                .limit(limit + 1)
            )
        )
        events = [
            RoomEvent.model_validate(
                {
                    "event_id": record.event_id,
                    "kind": record.kind,
                    "entity_id": record.entity_id,
                    "message_id": record.message_id,
                }
            )
            for record in rows[:limit]
        ]
        return RoomEventPage(
            events=events,
            next_event_id=events[-1].event_id if events else after_event_id,
            has_more=len(rows) > limit,
            resync_required=False,
        )

    def _resync(self, room_id: str) -> RoomEventPage:
        latest = self.session.scalar(
            select(func.max(RoomEventRecord.event_id)).where(
                RoomEventRecord.room_id == room_id, RoomEventRecord.channel_id == self.channel_id
            )
        )
        return RoomEventPage(
            events=[], next_event_id=latest or 0, has_more=False, resync_required=True
        )

    def notification_targets(self, started_at: datetime) -> list[ShutdownNotificationTarget]:
        rows = self.session.execute(
            select(MessageRecord.room_id, MessageRecord.channel_id, MemberRecord.id)
            .join(
                MemberRecord,
                (MemberRecord.room_id == MessageRecord.room_id)
                & (MemberRecord.channel_id == MessageRecord.channel_id)
                & (MemberRecord.kind == "agent")
                & MemberRecord.deleted_at.is_(None)
                & MemberRecord.session_id.is_not(None),
            )
            .join(
                ChannelRecord,
                (ChannelRecord.room_id == MessageRecord.room_id)
                & (ChannelRecord.id == MessageRecord.channel_id)
                & ChannelRecord.archived_at.is_(None),
            )
            .where(
                MessageRecord.publisher_id == USER_MEMBER_ID,
                MessageRecord.deleted_at.is_(None),
                MessageRecord.created_at >= started_at,
            )
            .distinct()
            .order_by(MessageRecord.room_id, MemberRecord.id)
        ).tuples()
        grouped: dict[tuple[str, str], list[str]] = defaultdict(list)
        for room_id, channel_id, member_id in rows:
            grouped[(room_id, channel_id)].append(member_id)
        return [
            ShutdownNotificationTarget(room_id, tuple(member_ids), channel_id)
            for (room_id, channel_id), member_ids in grouped.items()
        ]
