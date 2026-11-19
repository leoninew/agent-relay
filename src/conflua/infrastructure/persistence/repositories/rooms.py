from datetime import UTC, datetime

from sqlalchemy import delete, false, func, or_, select, update

from conflua.domain.rooms.errors import RoomConflictError
from conflua.domain.rooms.members import observation_cutoff
from conflua.domain.rooms.models import (
    RoomChangeKind,
    RoomState,
)
from conflua.infrastructure.persistence.models import (
    ChannelRecord,
    DeliveryRecord,
    MemberRecord,
    MemberTopicRecord,
    MessageRecord,
    RoomEventRecord,
    RoomRecord,
    SessionRecord,
    TopicRecord,
    audit_now,
)
from conflua.infrastructure.persistence.repositories._room_reads import SQLAlchemyRoomReads
from conflua.infrastructure.persistence.sqlite import time_at_or_before


class SQLAlchemyRoomRepository(SQLAlchemyRoomReads):
    def _event(self, room_id: str, kind: RoomChangeKind, entity_id: str) -> None:
        self.session.add(
            RoomEventRecord(
                room_id=room_id,
                channel_id=self.channel_id_for(room_id),
                kind=kind,
                entity_id=entity_id,
            )
        )

    def insert_room(self, state: RoomState) -> None:
        room = state.room
        user = state.members[0]
        self.session.add(RoomRecord(**room.model_dump(exclude={"archived_at"})))
        self.session.flush()
        self.session.add(
            ChannelRecord(
                room_id=room.id,
                id=state.channel_id,
                name="默认",
                description="",
                is_default=True,
                workspace_kind="existing",
            )
        )
        self.session.flush()
        self.session.add(
            MemberRecord(
                room_id=room.id,
                channel_id=state.channel_id,
                **user.model_dump(exclude={"topic_ids"}),
            )
        )
        self.session.flush()
        scoped = SQLAlchemyRoomRepository(self.session, state.channel_id)
        scoped._event(room.id, "room", room.id)
        scoped._event(room.id, "member", user.id)
        scoped.save_resources(
            state,
            RoomState(
                room=room,
                channel_id=state.channel_id,
                working_path=state.working_path,
                members=[user],
            ),
        )

    def save_resources(self, state: RoomState, original: RoomState) -> None:
        room_id = state.room.id
        channel_id = self.channel_id_for(room_id)
        if state.room != original.room:
            self.session.execute(
                update(RoomRecord)
                .where(RoomRecord.id == room_id)
                .values(
                    workspace_path=state.room.workspace_path,
                    raw_workspace_path=state.room.raw_workspace_path,
                    name=state.room.name,
                    description=state.room.description,
                )
                .execution_options(synchronize_session="fetch")
            )
            self._event(room_id, "room", room_id)
        old_topics = {topic.id: topic for topic in original.topics}
        for topic in state.topics:
            if old_topics.get(topic.id) != topic:
                topic_record = self.session.get(TopicRecord, (room_id, topic.id, channel_id))
                if topic_record is None:
                    self.session.add(
                        TopicRecord(
                            room_id=room_id,
                            channel_id=channel_id,
                            **topic.model_dump(),
                            is_deleted=topic.deleted_at is not None,
                            updated_at=topic.deleted_at,
                        )
                    )
                elif not topic_record.is_deleted:
                    topic_record.name = topic.name
                    topic_record.description = topic.description
                    if topic.deleted_at is not None:
                        topic_record.is_deleted = True
                        topic_record.deleted_at = topic.deleted_at
                        topic_record.updated_at = topic.deleted_at
                else:
                    continue
                self.session.flush()
                self._event(room_id, "topic", topic.id)
        old_sessions = {item.id: item for item in original.sessions}
        for item in state.sessions:
            if old_sessions.get(item.id) != item:
                self.session.merge(SessionRecord(room_id=room_id, **item.model_dump()))
                self.session.flush()
                self._event(room_id, "session", item.id)
        old_members = {member.id: member for member in original.members}
        for member in state.members:
            previous = old_members.get(member.id)
            if previous == member:
                continue
            if member.session_id and member.deleted_at is None:
                existing = self.session.scalar(
                    select(MemberRecord.id).where(
                        MemberRecord.room_id == room_id,
                        MemberRecord.channel_id == channel_id,
                        MemberRecord.session_id == member.session_id,
                        (MemberRecord.is_deleted == false()),
                        MemberRecord.id != member.id,
                    )
                )
                if existing is not None:
                    raise RoomConflictError("该会话已加入此频道", code="session_already_joined")
            existing_record = self.session.get(MemberRecord, (room_id, member.id, channel_id))
            if existing_record is not None and existing_record.is_deleted:
                continue
            member_record = self.session.merge(
                MemberRecord(
                    room_id=room_id,
                    channel_id=channel_id,
                    **member.model_dump(exclude={"topic_ids"}),
                    is_deleted=member.deleted_at is not None,
                )
            )
            if member.deleted_at is not None:
                member_record.updated_at = member.deleted_at
            elif (
                existing_record is not None
                and previous is not None
                and previous.topic_ids != member.topic_ids
            ):
                member_record.updated_at = audit_now()
            self.session.flush()
            self._event(room_id, "member", member.id)
            if previous is None or previous.topic_ids != member.topic_ids:
                self.session.execute(
                    delete(MemberTopicRecord)
                    .where(
                        MemberTopicRecord.room_id == room_id,
                        MemberTopicRecord.channel_id == channel_id,
                        MemberTopicRecord.member_id == member.id,
                    )
                    .execution_options(synchronize_session="fetch")
                )
                self.session.add_all(
                    [
                        MemberTopicRecord(
                            room_id=room_id,
                            channel_id=channel_id,
                            member_id=member.id,
                            topic_id=topic_id,
                            position=position,
                        )
                        for position, topic_id in enumerate(member.topic_ids)
                    ]
                )
                self.session.flush()
        self.session.flush()

    def delete_room(self, room_id: str) -> None:
        if (
            self.session.scalar(
                select(DeliveryRecord.id)
                .where(
                    DeliveryRecord.room_id == room_id,
                    DeliveryRecord.status == "submitting",
                    (DeliveryRecord.is_deleted == false()),
                )
                .limit(1)
            )
            is not None
        ):
            raise RoomConflictError("聊天室操作正在进行", code="channel_operation_busy")
        now = datetime.now(UTC)
        self.session.execute(
            update(RoomRecord)
            .where(RoomRecord.id == room_id, RoomRecord.is_deleted == false())
            .values(is_deleted=True, deleted_at=now, updated_at=now)
        )
        self.session.execute(
            update(ChannelRecord)
            .where(
                ChannelRecord.room_id == room_id,
                ChannelRecord.is_deleted == false(),
                ChannelRecord.status == "active",
            )
            .values(is_deleted=True, deleted_at=now, updated_at=now)
        )
        self.session.execute(
            update(MemberRecord)
            .where(
                MemberRecord.room_id == room_id,
                MemberRecord.kind == "agent",
                (MemberRecord.is_deleted == false()),
            )
            .values(is_deleted=True, deleted_at=now, updated_at=now)
        )
        self.session.execute(
            update(DeliveryRecord)
            .where(
                DeliveryRecord.room_id == room_id,
                DeliveryRecord.status == "pending",
                (DeliveryRecord.is_deleted == false()),
            )
            .values(is_deleted=True, deleted_at=now, updated_at=now)
        )

    def clear_messages(self, room_id: str, deleted_at: datetime) -> int:
        channel_id = self.channel_id_for(room_id)
        removed = list(
            self.session.scalars(
                update(MessageRecord)
                .where(
                    MessageRecord.room_id == room_id,
                    MessageRecord.channel_id == channel_id,
                    (MessageRecord.is_deleted == false()),
                )
                .values(is_deleted=True, deleted_at=deleted_at, updated_at=deleted_at)
                .returning(MessageRecord.id)
                .execution_options(synchronize_session="fetch")
            )
        )
        self.session.execute(
            update(DeliveryRecord)
            .where(
                DeliveryRecord.room_id == room_id,
                DeliveryRecord.channel_id == channel_id,
                (DeliveryRecord.is_deleted == false()),
            )
            .values(is_deleted=True, deleted_at=deleted_at, updated_at=deleted_at)
            .execution_options(synchronize_session="fetch")
        )
        self._event(room_id, "clear", room_id)
        self.session.flush()
        return len(removed)

    def save_bound_session_observation(
        self, session_id: str, presence: str, activity: str, observed_at: datetime, name: str
    ) -> None:
        bindings = self.session.execute(
            select(MemberRecord.room_id, MemberRecord.channel_id, MemberRecord.id)
            .join(RoomRecord, RoomRecord.id == MemberRecord.room_id)
            .join(
                ChannelRecord,
                (ChannelRecord.room_id == MemberRecord.room_id)
                & (ChannelRecord.id == MemberRecord.channel_id),
            )
            .where(
                MemberRecord.session_id == session_id,
                MemberRecord.kind == "agent",
                (MemberRecord.is_deleted == false()),
                (RoomRecord.is_deleted == false()),
                ChannelRecord.is_deleted == false(),
                ChannelRecord.status == "active",
            )
        ).all()
        for room_id, channel_id, member_id in bindings:
            SQLAlchemyRoomRepository(self.session, channel_id).save_observation(
                room_id,
                member_id,
                session_id,
                presence,
                activity,
                observed_at,
                name,
                refresh_cutoff=observation_cutoff(observed_at),
            )

    def save_observation(
        self,
        room_id: str,
        member_id: str,
        session_id: str,
        presence: str,
        activity: str,
        observed_at: datetime,
        session_name: str | None,
        *,
        refresh_cutoff: datetime,
    ) -> None:
        member_updated = self.session.scalar(
            update(MemberRecord)
            .where(
                MemberRecord.room_id == room_id,
                MemberRecord.channel_id == self.channel_id_for(room_id),
                MemberRecord.id == member_id,
                MemberRecord.session_id == session_id,
                (MemberRecord.is_deleted == false()),
                or_(MemberRecord.observed_at.is_(None), MemberRecord.observed_at <= observed_at),
                or_(
                    MemberRecord.presence.is_distinct_from(presence),
                    MemberRecord.activity.is_distinct_from(activity),
                    MemberRecord.activity_source.is_distinct_from("codex"),
                    MemberRecord.observed_at.is_(None),
                    time_at_or_before(MemberRecord.observed_at, refresh_cutoff),
                ),
            )
            .values(
                presence=presence,
                activity=activity,
                activity_source="codex",
                observed_at=observed_at,
            )
            .returning(MemberRecord.id)
            .execution_options(synchronize_session="fetch")
        )
        if member_updated is not None:
            self._event(room_id, "member", member_id)
        name_changed = (
            SessionRecord.name.is_distinct_from(session_name)
            if session_name is not None
            else false()
        )
        session_updated = self.session.scalar(
            update(SessionRecord)
            .where(
                SessionRecord.room_id == room_id,
                SessionRecord.id == session_id,
                or_(SessionRecord.observed_at.is_(None), SessionRecord.observed_at <= observed_at),
                or_(
                    SessionRecord.presence.is_distinct_from(presence),
                    name_changed,
                    SessionRecord.observed_at.is_(None),
                    time_at_or_before(SessionRecord.observed_at, refresh_cutoff),
                ),
            )
            .values(
                presence=presence,
                observed_at=observed_at,
                name=func.coalesce(session_name, SessionRecord.name),
            )
            .returning(SessionRecord.id)
            .execution_options(synchronize_session="fetch")
        )
        if session_updated is not None:
            self._event(room_id, "session", session_id)
        self.session.flush()
