from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from agent_relay.application.rooms.contracts import (
    MessagePage,
    MessageQueuePage,
    RoomEvent,
    RoomEventPage,
    RoomMetadata,
    RoomSnapshot,
)
from agent_relay.domain.rooms.models import Member, Message, Room
from agent_relay.infrastructure.persistence.database import Database
from agent_relay.infrastructure.persistence.message_queries import MessageQueries
from agent_relay.infrastructure.persistence.models import RoomEventRecord
from agent_relay.infrastructure.persistence.resource_queries import ResourceQueries
from agent_relay.infrastructure.persistence.transaction import SQLAlchemyTransaction


class SQLAlchemyRoomQueries:
    def __init__(
        self, source: Database | Session, transaction: SQLAlchemyTransaction | None = None
    ) -> None:
        if isinstance(source, Session) and transaction is not None:
            raise ValueError("Bind queries to a session or a request transaction")
        self.source = source
        self.transaction = transaction

    @contextmanager
    def _read(self) -> Iterator[Session]:
        if isinstance(self.source, Session):
            yield self.source
        else:
            with self.source.read(self.transaction) as session:
                yield session

    def rooms(self) -> list[Room]:
        with self._read() as session:
            return ResourceQueries(session).rooms()

    def member_for_session(self, room_id: str, session_id: str) -> Member:
        with self._read() as session:
            return ResourceQueries(session).member_for_session(room_id, session_id)

    def metadata(self, room_id: str) -> RoomMetadata:
        with self._read() as session:
            return ResourceQueries(session).metadata(room_id)

    def snapshot(
        self,
        room_id: str,
        topic_id: str | None = None,
        *,
        member_id: str | None = None,
        keyword: str | None = None,
        before_seq: int | None = None,
        limit: int = 50,
    ) -> RoomSnapshot:
        with self._read() as session:
            metadata = ResourceQueries(session).metadata(room_id)
            page = MessageQueries(session).page(
                room_id,
                topic_id=topic_id,
                member_id=member_id,
                keyword=keyword,
                before_seq=before_seq,
                limit=limit,
            )
            return RoomSnapshot(**metadata.model_dump(), **page.model_dump())

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
        with self._read() as session:
            ResourceQueries(session).room(room_id)
            return MessageQueries(session).page(
                room_id,
                topic_id=topic_id,
                member_id=member_id,
                keyword=keyword,
                before_seq=before_seq,
                limit=limit,
            )

    def message(self, room_id: str, message_id: str) -> Message:
        with self._read() as session:
            ResourceQueries(session).room(room_id)
            return MessageQueries(session).message(room_id, message_id)

    def queue(
        self,
        room_id: str,
        *,
        topic_id: str | None = None,
        member_id: str | None = None,
        before_seq: int | None = None,
        limit: int = 50,
    ) -> MessageQueuePage:
        with self._read() as session:
            ResourceQueries(session).room(room_id)
            return MessageQueries(session).queue(
                room_id,
                topic_id=topic_id,
                member_id=member_id,
                before_seq=before_seq,
                limit=limit,
            )

    def events(self, room_id: str, after_event_id: int, limit: int = 200) -> RoomEventPage:
        with self._read() as session:
            ResourceQueries(session).room(room_id)
            if (
                after_event_id
                and session.scalar(
                    select(RoomEventRecord.event_id).where(
                        RoomEventRecord.room_id == room_id,
                        RoomEventRecord.event_id == after_event_id,
                    )
                )
                is None
            ):
                return self._resync(session, room_id)
            rows = list(
                session.scalars(
                    select(RoomEventRecord)
                    .where(
                        RoomEventRecord.room_id == room_id,
                        RoomEventRecord.event_id > after_event_id,
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

    @staticmethod
    def _resync(session: Session, room_id: str) -> RoomEventPage:
        latest = session.scalar(
            select(func.max(RoomEventRecord.event_id)).where(RoomEventRecord.room_id == room_id)
        )
        return RoomEventPage(
            events=[], next_event_id=latest or 0, has_more=False, resync_required=True
        )
