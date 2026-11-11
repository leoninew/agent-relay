from datetime import datetime

from sqlalchemy import delete, false, func, or_, update
from sqlalchemy.orm import Session

from agent_relay.application.rooms.contracts import RoomMetadata
from agent_relay.domain.rooms.events import RoomChangeKind
from agent_relay.domain.rooms.models import Member, Room
from agent_relay.domain.rooms.state import RoomState
from agent_relay.infrastructure.persistence.models import (
    ContextMessageRecord,
    ContextQueryRecord,
    DeliveryRecord,
    MemberRecord,
    MemberTopicRecord,
    MessageMentionRecord,
    MessageRecipientRecord,
    MessageRecord,
    MessageTopicRecord,
    RoomEventRecord,
    RoomRecord,
    SessionRecord,
    TopicPositionRecord,
    TopicRecord,
)
from agent_relay.infrastructure.persistence.resource_queries import ResourceQueries
from agent_relay.infrastructure.persistence.sqlite import time_at_or_before


class SQLAlchemyRoomRepository:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.queries = ResourceQueries(session)

    def room(self, room_id: str) -> Room:
        return self.queries.room(room_id)

    def resources(self, room_id: str) -> RoomState:
        return self.queries.resources(room_id)

    def metadata(self, room_id: str) -> RoomMetadata:
        return self.queries.metadata(room_id)

    def project_exists(self, project_path: str) -> bool:
        return self.queries.project_exists(project_path)

    def publisher(self, room_id: str, member_id: str | None) -> Member:
        return self.queries.publisher(room_id, member_id)

    def joined_members(self, room_id: str) -> dict[str, str]:
        return self.queries.joined_members(room_id)

    def bindings(self) -> list[tuple[str, str]]:
        return self.queries.bindings()

    def _event(self, room_id: str, kind: RoomChangeKind, entity_id: str) -> None:
        self.session.add(RoomEventRecord(room_id=room_id, kind=kind, entity_id=entity_id))

    def insert_room(self, room: Room, user: Member) -> None:
        self.session.add(RoomRecord(**room.model_dump()))
        self.session.flush()
        self.session.add(
            MemberRecord(
                room_id=room.id,
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
            self.session.merge(
                MemberRecord(
                    room_id=room_id,
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
                        MemberTopicRecord.member_id == member.id,
                    )
                    .execution_options(synchronize_session="fetch")
                )
                self.session.add_all(
                    [
                        MemberTopicRecord(
                            room_id=room_id,
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
        self.session.flush()
        for model in (
            DeliveryRecord,
            ContextMessageRecord,
            ContextQueryRecord,
            TopicPositionRecord,
            MemberTopicRecord,
            MessageTopicRecord,
            MessageMentionRecord,
            MessageRecipientRecord,
            MessageRecord,
            MemberRecord,
            SessionRecord,
            TopicRecord,
            RoomEventRecord,
        ):
            self.session.execute(
                delete(model)
                .where(
                    model.__table__.c.room_id == room_id,
                )
                .execution_options(synchronize_session="fetch")
            )
        self.session.execute(
            delete(RoomRecord)
            .where(
                RoomRecord.id == room_id,
            )
            .execution_options(synchronize_session="fetch")
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
