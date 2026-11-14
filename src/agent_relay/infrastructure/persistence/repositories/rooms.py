from datetime import datetime

from sqlalchemy import delete, false, func, or_, select, update

from agent_relay.domain.rooms.errors import RoomConflictError
from agent_relay.domain.rooms.models import (
    DEFAULT_CHANNEL_ID,
    Member,
    Room,
    RoomChangeKind,
    RoomState,
)
from agent_relay.infrastructure.persistence.models import (
    ChannelRecord,
    DeliveryRecord,
    MemberRecord,
    MemberTopicRecord,
    MessageRecord,
    RoomEventRecord,
    RoomRecord,
    SessionRecord,
    TopicRecord,
)
from agent_relay.infrastructure.persistence.repositories._room_reads import SQLAlchemyRoomReads
from agent_relay.infrastructure.persistence.sqlite import time_at_or_before


class SQLAlchemyRoomRepository(SQLAlchemyRoomReads):
    def _event(self, room_id: str, kind: RoomChangeKind, entity_id: str) -> None:
        self.session.add(
            RoomEventRecord(
                room_id=room_id, channel_id=self.channel_id, kind=kind, entity_id=entity_id
            )
        )

    def insert_room(self, room: Room, user: Member) -> None:
        self.session.add(RoomRecord(**room.model_dump()))
        self.session.flush()
        self.session.add(
            ChannelRecord(
                room_id=room.id,
                id=DEFAULT_CHANNEL_ID,
                name="默认",
                description="",
                working_path=room.project_path,
                working_path_key=room.project_path,
                is_default=True,
                workspace_kind="existing",
            )
        )
        self.session.flush()
        self.session.add(
            MemberRecord(
                room_id=room.id,
                channel_id=self.channel_id,
                **user.model_dump(exclude={"topic_ids"}),
            )
        )
        self.session.flush()
        self._event(room.id, "room", room.id)
        self._event(room.id, "member", user.id)
        self.session.flush()

    def save_resources(self, state: RoomState, original: RoomState) -> None:
        room_id = state.room.id
        if state.room != original.room:
            self.session.execute(
                update(RoomRecord)
                .where(RoomRecord.id == room_id)
                .values(
                    project_path=state.room.project_path,
                    name=state.room.name,
                    description=state.room.description,
                )
                .execution_options(synchronize_session="fetch")
            )
            self._event(room_id, "room", room_id)
        old_topics = {topic.id: topic for topic in original.topics}
        for topic in state.topics:
            if old_topics.get(topic.id) != topic:
                self.session.merge(
                    TopicRecord(
                        room_id=room_id,
                        channel_id=self.channel_id,
                        **topic.model_dump(),
                    )
                )
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
                        MemberRecord.session_id == member.session_id,
                        MemberRecord.deleted_at.is_(None),
                        or_(
                            MemberRecord.channel_id != self.channel_id,
                            MemberRecord.id != member.id,
                        ),
                    )
                )
                if existing is not None:
                    raise RoomConflictError(
                        "该会话已加入此聊天室的频道", code="session_already_joined"
                    )
            self.session.merge(
                MemberRecord(
                    room_id=room_id,
                    channel_id=self.channel_id,
                    **member.model_dump(exclude={"topic_ids"}),
                )
            )
            self.session.flush()
            self._event(room_id, "member", member.id)
            if previous is None or previous.topic_ids != member.topic_ids:
                self.session.execute(
                    delete(MemberTopicRecord)
                    .where(
                        MemberTopicRecord.room_id == room_id,
                        MemberTopicRecord.channel_id == self.channel_id,
                        MemberTopicRecord.member_id == member.id,
                    )
                    .execution_options(synchronize_session="fetch")
                )
                self.session.add_all(
                    [
                        MemberTopicRecord(
                            room_id=room_id,
                            channel_id=self.channel_id,
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
                    DeliveryRecord.deleted_at.is_(None),
                )
                .limit(1)
            )
            is not None
        ):
            raise RoomConflictError("聊天室操作正在进行", code="channel_operation_busy")
        now = datetime.now().astimezone()
        self.session.execute(
            update(RoomRecord).where(RoomRecord.id == room_id).values(archived_at=now)
        )
        self.session.execute(
            update(ChannelRecord)
            .where(ChannelRecord.room_id == room_id, ChannelRecord.archived_at.is_(None))
            .values(archived_at=now)
        )
        self.session.execute(
            update(MemberRecord)
            .where(
                MemberRecord.room_id == room_id,
                MemberRecord.kind == "agent",
                MemberRecord.deleted_at.is_(None),
            )
            .values(deleted_at=now)
        )
        self.session.execute(
            update(DeliveryRecord)
            .where(
                DeliveryRecord.room_id == room_id,
                DeliveryRecord.status == "pending",
                DeliveryRecord.deleted_at.is_(None),
            )
            .values(deleted_at=now, updated_at=now)
        )

    def clear_messages(self, room_id: str, deleted_at: datetime) -> int:
        removed = list(
            self.session.scalars(
                update(MessageRecord)
                .where(
                    MessageRecord.room_id == room_id,
                    MessageRecord.channel_id == self.channel_id,
                    MessageRecord.deleted_at.is_(None),
                )
                .values(deleted_at=deleted_at)
                .returning(MessageRecord.id)
                .execution_options(synchronize_session="fetch")
            )
        )
        self.session.execute(
            update(DeliveryRecord)
            .where(
                DeliveryRecord.room_id == room_id,
                DeliveryRecord.channel_id == self.channel_id,
                DeliveryRecord.deleted_at.is_(None),
            )
            .values(deleted_at=deleted_at, updated_at=deleted_at)
            .execution_options(synchronize_session="fetch")
        )
        self._event(room_id, "clear", room_id)
        self.session.flush()
        return len(removed)

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
                MemberRecord.channel_id == self.channel_id,
                MemberRecord.id == member_id,
                MemberRecord.session_id == session_id,
                MemberRecord.deleted_at.is_(None),
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
