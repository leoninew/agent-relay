import sqlite3

from agent_relay.room_errors import RoomNotFoundError
from agent_relay.room_models import (
    USER_MEMBER_ID,
    Delivery,
    Member,
    Message,
    MessagePage,
    Room,
    RoomEvent,
    RoomEventPage,
    RoomMetadata,
    RoomSnapshot,
    RoomSummary,
    Session,
    Topic,
)
from agent_relay.room_state import RoomState
from agent_relay.room_store import SQLiteRoomStore
from agent_relay.topic_positions import read_topic_positions


class RoomQueries:
    def __init__(self, store: SQLiteRoomStore) -> None:
        self.store = store

    @staticmethod
    def room_in(connection: sqlite3.Connection, room_id: str) -> Room:
        row = connection.execute("SELECT payload FROM rooms WHERE id = ?", (room_id,)).fetchone()
        if row is None:
            raise RoomNotFoundError("聊天室不存在")
        return Room.model_validate_json(row["payload"])

    def rooms(self) -> list[Room]:
        with self.store.read() as connection:
            return [
                Room.model_validate_json(row["payload"])
                for row in connection.execute("SELECT payload FROM rooms ORDER BY rowid")
            ]

    def member_for_session(self, room_id: str, session_id: str) -> Member:
        with self.store.read() as connection:
            self.room_in(connection, room_id)
            row = connection.execute(
                "SELECT payload FROM members WHERE room_id = ? AND session_id = ? "
                "AND deleted_at IS NULL",
                (room_id, session_id),
            ).fetchone()
            if row is None:
                raise RoomNotFoundError("该 Codex 会话尚未加入此聊天室")
            return Member.model_validate_json(row["payload"])

    @staticmethod
    def project_exists_in(connection: sqlite3.Connection, project_path: str) -> bool:
        return (
            connection.execute(
                "SELECT 1 FROM rooms WHERE project_path = ?", (project_path,)
            ).fetchone()
            is not None
        )

    @staticmethod
    def publisher_in(connection: sqlite3.Connection, room_id: str, member_id: str | None) -> Member:
        row = connection.execute(
            "SELECT payload FROM members WHERE room_id = ? AND id = ? AND deleted_at IS NULL",
            (room_id, member_id if member_id is not None else USER_MEMBER_ID),
        ).fetchone()
        if row is None:
            raise RoomNotFoundError("聊天室成员不存在")
        return Member.model_validate_json(row["payload"])

    @staticmethod
    def joined_members_in(connection: sqlite3.Connection, room_id: str) -> dict[str, str]:
        return {
            row["session_id"]: row["id"]
            for row in connection.execute(
                "SELECT id, session_id FROM members WHERE room_id = ? AND deleted_at IS NULL "
                "AND session_id IS NOT NULL AND json_extract(payload, '$.kind') = 'agent'",
                (room_id,),
            )
        }

    @staticmethod
    def message_exists_in(connection: sqlite3.Connection, room_id: str, message_id: str) -> bool:
        return (
            connection.execute(
                "SELECT 1 FROM messages WHERE room_id = ? AND id = ?", (room_id, message_id)
            ).fetchone()
            is not None
        )

    @staticmethod
    def next_message_seq_in(connection: sqlite3.Connection, room_id: str) -> int:
        return int(
            connection.execute(
                "SELECT COALESCE(MAX(seq), 0) + 1 FROM messages WHERE room_id = ?", (room_id,)
            ).fetchone()[0]
        )

    @staticmethod
    def _event_id(connection: sqlite3.Connection, room_id: str) -> int:
        return int(
            connection.execute(
                "SELECT COALESCE(MAX(event_id), 0) FROM room_events WHERE room_id = ?", (room_id,)
            ).fetchone()[0]
        )

    def resources_in(self, connection: sqlite3.Connection, room_id: str) -> RoomState:
        room = self.room_in(connection, room_id)
        topics = [
            Topic.model_validate_json(row["payload"])
            for row in connection.execute(
                "SELECT id, payload FROM topics WHERE room_id = ? ORDER BY rowid", (room_id,)
            )
        ]
        subscriptions: dict[str, list[str]] = {}
        for row in connection.execute(
            "SELECT member_id, topic_id FROM member_topics WHERE room_id = ? ORDER BY position",
            (room_id,),
        ):
            subscriptions.setdefault(row["member_id"], []).append(row["topic_id"])
        members = []
        for row in connection.execute(
            "SELECT id, payload FROM members WHERE room_id = ? ORDER BY session_id IS NULL, rowid",
            (room_id,),
        ):
            member = Member.model_validate_json(row["payload"]).model_copy(
                update={"topic_ids": subscriptions.get(row["id"], [])}
            )
            members.append(member)
        sessions = [
            Session.model_validate_json(row["payload"])
            for row in connection.execute(
                "SELECT payload FROM sessions WHERE room_id = ? ORDER BY rowid", (room_id,)
            )
        ]
        return RoomState(room=room, topics=topics, members=members, sessions=sessions)

    def metadata_in(self, connection: sqlite3.Connection, room_id: str) -> RoomMetadata:
        state = self.resources_in(connection, room_id)
        counts = dict(
            connection.execute(
                "SELECT j.value, COUNT(*) FROM messages m, json_each(m.payload, '$.topic_ids') j "
                "WHERE m.room_id = ? GROUP BY j.value",
                (room_id,),
            ).fetchall()
        )
        statuses = dict(
            connection.execute(
                "SELECT status, COUNT(*) FROM deliveries WHERE room_id = ? GROUP BY status",
                (room_id,),
            ).fetchall()
        )
        total = connection.execute(
            "SELECT COUNT(*) FROM messages WHERE room_id = ?", (room_id,)
        ).fetchone()[0]
        return RoomMetadata(
            room=state.room,
            topics=[
                topic.model_copy(update={"message_count": counts.get(topic.id, 0)})
                for topic in state.topics
            ],
            members=state.members,
            sessions=state.sessions,
            positions=read_topic_positions(connection, room_id),
            summary=RoomSummary(
                total_messages=total,
                queued_count=statuses.get("queued", 0),
                received_count=statuses.get("received", 0),
                pending_count=statuses.get("pending", 0),
                submitting_count=statuses.get("submitting", 0),
                rejected_count=statuses.get("rejected", 0),
                unknown_count=statuses.get("unknown", 0),
            ),
            event_id=self._event_id(connection, room_id),
        )

    @staticmethod
    def _messages(
        connection: sqlite3.Connection, room_id: str, rows: list[sqlite3.Row]
    ) -> list[Message]:
        messages = [Message.model_validate_json(row["payload"]) for row in rows]
        if not messages:
            return messages
        deliveries: dict[str, list[Delivery]] = {}
        slots = ",".join("?" for _ in messages)
        for row in connection.execute(
            f"SELECT message_id, payload FROM deliveries WHERE room_id = ? "
            f"AND message_id IN ({slots}) ORDER BY rowid",
            (room_id, *(message.id for message in messages)),
        ):
            deliveries.setdefault(row["message_id"], []).append(
                Delivery.model_validate_json(row["payload"])
            )
        for message in messages:
            message.deliveries = deliveries.get(message.id, [])
        return messages

    def _page(
        self,
        connection: sqlite3.Connection,
        room_id: str,
        *,
        topic_id: str | None,
        member_id: str | None,
        before_seq: int | None,
        limit: int,
    ) -> MessagePage:
        clauses = ["m.room_id = ?"]
        args: list[str | int] = [room_id]
        if topic_id is not None:
            if (
                connection.execute(
                    "SELECT 1 FROM topics WHERE room_id = ? AND id = ?", (room_id, topic_id)
                ).fetchone()
                is None
            ):
                raise RoomNotFoundError("话题不存在")
            clauses.append(
                "(EXISTS (SELECT 1 FROM json_each(m.payload, '$.topic_ids') WHERE value = ?) "
                "OR EXISTS (SELECT 1 FROM json_each(m.payload, '$.recipient_ids') WHERE value = ?))"
            )
            args.extend([topic_id, USER_MEMBER_ID])
        if member_id is not None:
            if (
                connection.execute(
                    "SELECT 1 FROM members WHERE room_id = ? AND id = ?", (room_id, member_id)
                ).fetchone()
                is None
            ):
                raise RoomNotFoundError("成员不存在")
            clauses.append("m.publisher_id = ?")
            args.append(member_id)
        where = " AND ".join(clauses)
        newer = (
            before_seq is not None
            and connection.execute(
                f"SELECT 1 FROM messages m WHERE {where} AND m.seq >= ? LIMIT 1",
                (*args, before_seq),
            ).fetchone()
            is not None
        )
        if before_seq is not None:
            clauses.append("m.seq < ?")
            args.append(before_seq)
        rows = connection.execute(
            f"SELECT m.payload FROM messages m WHERE {' AND '.join(clauses)} "
            "ORDER BY m.seq DESC LIMIT ?",
            (*args, limit + 1),
        ).fetchall()
        more = len(rows) > limit
        messages = self._messages(connection, room_id, list(reversed(rows[:limit])))
        return MessagePage(
            messages=messages,
            has_more=more,
            next_before_seq=messages[0].seq if more else None,
            has_newer=newer,
        )

    def metadata(self, room_id: str) -> RoomMetadata:
        with self.store.read() as connection:
            return self.metadata_in(connection, room_id)

    def snapshot(
        self,
        room_id: str,
        topic_id: str | None = None,
        *,
        member_id: str | None = None,
        before_seq: int | None = None,
        limit: int = 50,
    ) -> RoomSnapshot:
        with self.store.read() as connection:
            metadata = self.metadata_in(connection, room_id)
            page = self._page(
                connection,
                room_id,
                topic_id=topic_id,
                member_id=member_id,
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
        before_seq: int | None = None,
        limit: int = 50,
    ) -> MessagePage:
        with self.store.read() as connection:
            self.room_in(connection, room_id)
            return self._page(
                connection,
                room_id,
                topic_id=topic_id,
                member_id=member_id,
                before_seq=before_seq,
                limit=limit,
            )

    def message(self, room_id: str, message_id: str) -> Message:
        with self.store.read() as connection:
            self.room_in(connection, room_id)
            rows = connection.execute(
                "SELECT payload FROM messages WHERE room_id = ? AND id = ?", (room_id, message_id)
            ).fetchall()
            if not rows:
                raise RoomNotFoundError("消息不存在")
            return self._messages(connection, room_id, rows)[0]

    def publication_in(
        self,
        connection: sqlite3.Connection,
        room_id: str,
        publisher_id: str,
        publication_id: str,
    ) -> Message | None:
        row = connection.execute(
            "SELECT payload FROM messages "
            "WHERE room_id = ? AND publisher_id = ? AND publication_id = ?",
            (room_id, publisher_id, publication_id),
        ).fetchone()
        if row is None:
            return None
        return self._messages(connection, room_id, [row])[0]

    def events(self, room_id: str, after_event_id: int, limit: int = 200) -> RoomEventPage:
        with self.store.read() as connection:
            self.room_in(connection, room_id)
            if (
                after_event_id
                and connection.execute(
                    "SELECT 1 FROM room_events WHERE room_id = ? AND event_id = ?",
                    (room_id, after_event_id),
                ).fetchone()
                is None
            ):
                return RoomEventPage(
                    events=[],
                    next_event_id=self._event_id(connection, room_id),
                    has_more=False,
                    resync_required=True,
                )
            rows = connection.execute(
                "SELECT event_id, kind, entity_id, message_id FROM room_events "
                "WHERE room_id = ? AND event_id > ? ORDER BY event_id LIMIT ?",
                (room_id, after_event_id, limit + 1),
            ).fetchall()
            events = [RoomEvent.model_validate(dict(row)) for row in rows[:limit]]
            return RoomEventPage(
                events=events,
                next_event_id=events[-1].event_id if events else after_event_id,
                has_more=len(rows) > limit,
                resync_required=False,
            )
