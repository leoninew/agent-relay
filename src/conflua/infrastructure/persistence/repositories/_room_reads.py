from collections import defaultdict
from datetime import datetime
from pathlib import Path

from sqlalchemy import false, func, select
from sqlalchemy.sql.elements import ColumnElement

from conflua.application.dto.desktop import ShutdownNotificationTarget
from conflua.application.dto.members import SessionChannel
from conflua.application.dto.positions import TopicPosition
from conflua.application.dto.rooms import (
    ChannelMessageHead,
    RoomActivity,
    RoomEvent,
    RoomEventPage,
    RoomMetadata,
    RoomSummary,
)
from conflua.domain.rooms.errors import RoomConflictError, RoomNotFoundError
from conflua.domain.rooms.models import (
    Member,
    Room,
    RoomState,
)
from conflua.domain.rooms.rules import normalize_workspace_identity
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
from conflua.infrastructure.persistence.repositories._channel_scope import SQLAlchemyChannelScope
from conflua.infrastructure.persistence.sqlite import insertion_order


def _human_publisher() -> ColumnElement[bool]:
    return (
        select(MemberRecord.id)
        .where(
            MemberRecord.room_id == MessageRecord.room_id,
            MemberRecord.channel_id == MessageRecord.channel_id,
            MemberRecord.id == MessageRecord.publisher_id,
            MemberRecord.kind == "human",
        )
        .correlate(MessageRecord)
        .exists()
    )


class SQLAlchemyRoomReads(SQLAlchemyChannelScope):
    def room(self, room_id: str) -> Room:
        record = self.session.get(RoomRecord, room_id)
        if record is None or record.is_deleted:
            raise RoomNotFoundError("聊天室不存在", code="room_not_found")
        channel = self.session.get(ChannelRecord, (room_id, self.channel_id_for(room_id)))
        if channel is None:
            raise RoomNotFoundError("频道不存在", code="channel_not_found")
        if channel.is_deleted:
            raise RoomConflictError("频道当前不可用", code="channel_unavailable")
        return room_from_model(record)

    def working_path(self, room_id: str) -> str:
        room = self.room(room_id)
        channel = self.session.get(ChannelRecord, (room_id, self.channel_id_for(room_id)))
        if channel is None:
            raise RoomNotFoundError("频道不存在", code="channel_not_found")
        if channel.workspace_kind == "existing":
            return room.workspace_path
        if not channel.worktree_path or not Path(channel.worktree_path).is_dir():
            raise RoomConflictError("频道工作目录不存在", code="channel_directory_missing")
        return channel.worktree_path

    def rooms(self) -> list[Room]:
        return [
            room_from_model(record)
            for record in self.session.scalars(
                select(RoomRecord)
                .where(RoomRecord.is_deleted == false())
                .order_by(insertion_order("rooms"))
            )
        ]

    def channel_message_heads(self) -> list[ChannelMessageHead]:
        latest = (
            select(func.max(MessageRecord.seq))
            .where(
                MessageRecord.room_id == ChannelRecord.room_id,
                MessageRecord.channel_id == ChannelRecord.id,
                ~_human_publisher(),
                (MessageRecord.is_deleted == false()),
            )
            .correlate(ChannelRecord)
            .scalar_subquery()
        )
        rows = self.session.execute(
            select(ChannelRecord.room_id, ChannelRecord.id, func.coalesce(latest, 0))
            .join(RoomRecord, RoomRecord.id == ChannelRecord.room_id)
            .where(
                (RoomRecord.is_deleted == false()),
                ChannelRecord.status == "active",
                ChannelRecord.is_deleted == false(),
            )
        )
        return [
            ChannelMessageHead(room_id=room_id, channel_id=channel_id, latest_seq=seq)
            for room_id, channel_id, seq in rows
        ]

    def workspace_exists(self, workspace_path: str, *, exclude_room_id: str | None = None) -> bool:
        identity = normalize_workspace_identity(workspace_path)
        statement = select(RoomRecord.workspace_path).where(RoomRecord.is_deleted == false())
        if exclude_room_id is not None:
            statement = statement.where(RoomRecord.id != exclude_room_id)
        room_paths = self.session.scalars(statement)
        if any(normalize_workspace_identity(path) == identity for path in room_paths):
            return True
        channel_paths = self.session.scalars(
            select(ChannelRecord.worktree_path).where(
                ChannelRecord.workspace_kind == "worktree",
                ChannelRecord.is_deleted == false(),
            )
        )
        return any(
            path is not None and normalize_workspace_identity(path) == identity
            for path in channel_paths
        )

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
        identity = (
            MemberRecord.kind == "human" if member_id is None else MemberRecord.id == member_id
        )
        record = self.session.scalar(
            select(MemberRecord).where(
                MemberRecord.room_id == room_id,
                MemberRecord.channel_id == self.channel_id_for(room_id),
                identity,
                (MemberRecord.is_deleted == false()),
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
                MemberRecord.channel_id == self.channel_id_for(room_id),
                MemberRecord.session_id == session_id,
                (MemberRecord.is_deleted == false()),
            )
        )
        if record is None:
            raise RoomNotFoundError("该 Codex 会话尚未加入此频道", code="session_not_joined")
        return self._member(record)

    def joined_members(self, room_id: str) -> dict[str, str]:
        return {
            session_id: member_id
            for session_id, member_id in self.session.execute(
                select(MemberRecord.session_id, MemberRecord.id).where(
                    MemberRecord.room_id == room_id,
                    MemberRecord.channel_id == self.channel_id_for(room_id),
                    (MemberRecord.is_deleted == false()),
                    MemberRecord.session_id.is_not(None),
                    MemberRecord.kind == "agent",
                )
            )
            if session_id is not None
        }

    def member(self, room_id: str, member_id: str) -> Member:
        self.room(room_id)
        return self.publisher(room_id, member_id)

    def joined_channels(self, room_id: str) -> dict[str, list[SessionChannel]]:
        self.room(room_id)
        channels: dict[str, list[SessionChannel]] = defaultdict(list)
        for session_id, channel_id, name in self.session.execute(
            select(MemberRecord.session_id, ChannelRecord.id, ChannelRecord.name)
            .join(
                ChannelRecord,
                (ChannelRecord.room_id == MemberRecord.room_id)
                & (ChannelRecord.id == MemberRecord.channel_id),
            )
            .where(
                MemberRecord.room_id == room_id,
                MemberRecord.kind == "agent",
                MemberRecord.session_id.is_not(None),
                (MemberRecord.is_deleted == false()),
                ChannelRecord.is_deleted == false(),
                ChannelRecord.status == "active",
            )
            .order_by(ChannelRecord.is_default.desc(), ChannelRecord.created_at, ChannelRecord.id)
        ):
            if session_id is not None:
                channels[session_id].append(SessionChannel(id=channel_id, name=name))
        return dict(channels)

    def active_bindings(self, room_id: str) -> dict[str, str]:
        self.room(room_id)
        return {
            member_id: session_id for session_id, member_id in self.joined_members(room_id).items()
        }

    def bindings(self) -> list[tuple[str, str, str]]:
        return [
            (room_id, channel_id, session_id)
            for room_id, channel_id, session_id in self.session.execute(
                select(
                    MemberRecord.room_id, MemberRecord.channel_id, MemberRecord.session_id
                ).where(
                    (MemberRecord.is_deleted == false()),
                    MemberRecord.session_id.is_not(None),
                    MemberRecord.kind == "agent",
                )
            )
            if session_id is not None
        ]

    def resources(self, room_id: str) -> RoomState:
        room = self.room(room_id)
        working_path = self.working_path(room_id)
        channel_id = self.channel_id_for(room_id)
        topics = [
            topic_from_model(record)
            for record in self.session.scalars(
                select(TopicRecord)
                .where(
                    TopicRecord.room_id == room_id,
                    TopicRecord.channel_id == channel_id,
                )
                .order_by(insertion_order("topics"))
            )
        ]
        subscriptions: dict[str, list[str]] = {}
        for member_id, topic_id in self.session.execute(
            select(MemberTopicRecord.member_id, MemberTopicRecord.topic_id)
            .where(
                MemberTopicRecord.room_id == room_id,
                MemberTopicRecord.channel_id == channel_id,
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
                    MemberRecord.channel_id == channel_id,
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
                    select(MemberRecord.id)
                    .where(
                        MemberRecord.room_id == SessionRecord.room_id,
                        MemberRecord.channel_id == channel_id,
                        MemberRecord.session_id == SessionRecord.id,
                    )
                    .exists(),
                )
                .order_by(insertion_order("sessions"))
            )
        ]
        return RoomState(
            room=room,
            channel_id=channel_id,
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
                (MessageRecord.is_deleted == false()),
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
                    & (MemberRecord.is_deleted == false())
                ),
            )
            .join(
                TopicRecord,
                (
                    (TopicRecord.room_id == MemberTopicRecord.room_id)
                    & (TopicRecord.channel_id == MemberTopicRecord.channel_id)
                    & (TopicRecord.id == MemberTopicRecord.topic_id)
                    & (TopicRecord.is_deleted == false())
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
                MemberTopicRecord.channel_id == self.channel_id_for(room_id),
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
        return RoomMetadata(
            room=state.room,
            topics=state.topics,
            members=state.members,
            sessions=state.sessions,
            **self.activity(room_id).model_dump(),
        )

    def activity(self, room_id: str) -> RoomActivity:
        self.room(room_id)
        channel_id = self.channel_id_for(room_id)
        statuses = {
            status: count
            for status, count in self.session.execute(
                select(DeliveryRecord.status, func.count())
                .where(
                    DeliveryRecord.room_id == room_id,
                    DeliveryRecord.channel_id == channel_id,
                    (DeliveryRecord.is_deleted == false()),
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
                    MessageRecord.channel_id == channel_id,
                    (MessageRecord.is_deleted == false()),
                )
            )
            or 0
        )
        event_id = (
            self.session.scalar(
                select(func.max(RoomEventRecord.event_id)).where(
                    RoomEventRecord.room_id == room_id,
                    RoomEventRecord.channel_id == channel_id,
                )
            )
            or 0
        )
        return RoomActivity(
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
        channel_id = self.channel_id_for(room_id)
        if (
            self.session.scalar(
                select(RoomEventRecord.event_id)
                .where(
                    RoomEventRecord.room_id == room_id,
                    RoomEventRecord.channel_id == channel_id,
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
                    RoomEventRecord.channel_id == channel_id,
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
                RoomEventRecord.room_id == room_id,
                RoomEventRecord.channel_id == self.channel_id_for(room_id),
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
                & (MemberRecord.is_deleted == false())
                & MemberRecord.session_id.is_not(None),
            )
            .join(
                ChannelRecord,
                (ChannelRecord.room_id == MessageRecord.room_id)
                & (ChannelRecord.id == MessageRecord.channel_id)
                & (ChannelRecord.is_deleted == false()),
            )
            .where(
                _human_publisher(),
                (MessageRecord.is_deleted == false()),
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
