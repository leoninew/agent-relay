import json
import sqlite3
from datetime import UTC, datetime
from uuid import uuid4

from agent_relay.member_context_models import (
    CatalogMember,
    CatalogTopic,
    ContextMessage,
    ContextQuery,
    ContextResult,
    MemberCatalog,
)
from agent_relay.room_errors import RoomNotFoundError
from agent_relay.room_models import Room, TopicPosition
from agent_relay.room_store import SQLiteRoomStore
from agent_relay.topic_positions import read_topic_positions


class MemberContext:
    def __init__(self, store: SQLiteRoomStore) -> None:
        self.store = store

    @staticmethod
    def _subscriptions(connection: sqlite3.Connection, room_id: str, member_id: str) -> set[str]:
        member = connection.execute(
            "SELECT 1 FROM members WHERE room_id = ? AND id = ? AND deleted_at IS NULL",
            (room_id, member_id),
        ).fetchone()
        if member is None:
            raise RoomNotFoundError("聊天室成员不存在")
        return {
            row[0]
            for row in connection.execute(
                "SELECT mt.topic_id FROM member_topics mt JOIN topics t "
                "ON t.room_id = mt.room_id AND t.id = mt.topic_id AND t.deleted_at IS NULL "
                "WHERE mt.room_id = ? AND mt.member_id = ?",
                (room_id, member_id),
            )
        }

    def catalog(self, room_id: str, member_id: str) -> MemberCatalog:
        with self.store.read() as connection:
            subscriptions = self._subscriptions(connection, room_id, member_id)
            room = Room.model_validate_json(
                connection.execute(
                    "SELECT payload FROM rooms WHERE id = ?",
                    (room_id,),
                ).fetchone()[0]
            )
            topics = [
                CatalogTopic(
                    **json.loads(row["payload"]),
                    subscribed=row["id"] in subscriptions,
                )
                for row in connection.execute(
                    "SELECT id, payload FROM topics WHERE room_id = ? "
                    "AND deleted_at IS NULL ORDER BY rowid",
                    (room_id,),
                )
            ]
            member_topics: dict[str, list[str]] = {}
            for row in connection.execute(
                "SELECT member_id, topic_id FROM member_topics WHERE room_id = ? ORDER BY position",
                (room_id,),
            ):
                member_topics.setdefault(row["member_id"], []).append(row["topic_id"])
            members = [
                CatalogMember(
                    id=row["id"],
                    name=row["name"],
                    topic_ids=member_topics.get(row["id"], []),
                )
                for row in connection.execute(
                    "SELECT id, name FROM members WHERE room_id = ? "
                    "AND deleted_at IS NULL ORDER BY rowid",
                    (room_id,),
                )
            ]
            return MemberCatalog(
                room_id=room.id,
                room_name=room.name,
                member_id=member_id,
                topics=topics,
                members=members,
            )

    def positions(self, room_id: str, member_id: str) -> list[TopicPosition]:
        with self.store.read() as connection:
            self._subscriptions(connection, room_id, member_id)
            return read_topic_positions(connection, room_id, member_id)

    @staticmethod
    def _select(
        connection: sqlite3.Connection,
        room_id: str,
        member_id: str,
        request: ContextQuery,
        subscriptions: set[str],
    ) -> tuple[list[ContextMessage], bool]:
        if request.topic_id is not None and request.topic_id not in subscriptions:
            raise RoomNotFoundError("话题不存在或未订阅")
        clauses = [
            "m.room_id = ?",
            (
                "(EXISTS (SELECT 1 FROM deliveries d WHERE d.room_id = m.room_id "
                "AND d.message_id = m.id AND d.target_member_id = ?) OR EXISTS "
                "(SELECT 1 FROM json_each(m.payload, '$.topic_ids') j JOIN member_topics mt "
                "ON mt.room_id = m.room_id AND mt.topic_id = j.value "
                "JOIN topics t ON t.room_id = mt.room_id AND t.id = mt.topic_id "
                "AND t.deleted_at IS NULL WHERE mt.member_id = ?))"
            ),
        ]
        args: list[str | int] = [room_id, member_id, member_id]
        if request.message_id is not None:
            clauses.append("m.id = ?")
            args.append(request.message_id)
        if request.topic_id is not None:
            clauses.append(
                "EXISTS (SELECT 1 FROM json_each(m.payload, '$.topic_ids') WHERE value = ?)"
            )
            args.append(request.topic_id)
        if request.keyword is not None:
            clauses.append("instr(json_extract(m.payload, '$.content'), ?) > 0")
            args.append(request.keyword)
        if request.before_seq is not None:
            clauses.append("m.seq < ?")
            args.append(request.before_seq)
        if request.after_seq is not None:
            clauses.append("m.seq > ?")
            args.append(request.after_seq)
        direction = "ASC" if request.after_seq is not None else "DESC"
        rows = connection.execute(
            f"SELECT m.payload FROM messages m WHERE {' AND '.join(clauses)} "
            f"ORDER BY m.seq {direction} LIMIT ?",
            (*args, request.limit + 1),
        ).fetchall()
        if request.message_id is not None and not rows:
            raise RoomNotFoundError("消息不存在或不在查阅范围内")
        messages = [
            ContextMessage.model_validate_json(row["payload"]) for row in rows[: request.limit]
        ]
        if direction == "DESC":
            messages.reverse()
        return messages, len(rows) > request.limit

    @staticmethod
    def _record(
        connection: sqlite3.Connection,
        room_id: str,
        member_id: str,
        request: ContextQuery,
        subscriptions: set[str],
        messages: list[ContextMessage],
    ) -> str | None:
        if not messages:
            return None
        query_id = str(uuid4())
        now = datetime.now(UTC).isoformat()
        records = [
            {"messageId": message.id, "seq": message.seq, "topicIds": message.topic_ids}
            for message in messages
        ]
        connection.execute(
            "INSERT INTO member_context_queries"
            "(id, room_id, member_id, request, messages, provided_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                query_id,
                room_id,
                member_id,
                request.model_dump_json(),
                json.dumps(records, ensure_ascii=False),
                now,
            ),
        )
        positions: dict[str, int] = {}
        for message in messages:
            for topic_id in subscriptions.intersection(message.topic_ids):
                if request.topic_id is None or topic_id == request.topic_id:
                    positions[topic_id] = max(positions.get(topic_id, 0), message.seq)
        connection.executemany(
            "INSERT INTO member_topic_positions(room_id, member_id, topic_id, seq, updated_at) "
            "VALUES (?, ?, ?, ?, ?) ON CONFLICT(room_id, member_id, topic_id) DO UPDATE SET "
            "seq = excluded.seq, updated_at = excluded.updated_at "
            "WHERE excluded.seq > member_topic_positions.seq",
            [
                (room_id, member_id, topic_id, seq, now)
                for topic_id, seq in sorted(positions.items())
            ],
        )
        return query_id

    def query(self, room_id: str, member_id: str, request: ContextQuery) -> ContextResult:
        # No transport calls or model work are performed while holding this transaction.
        with self.store.write() as connection:
            subscriptions = self._subscriptions(connection, room_id, member_id)
            messages, more = self._select(connection, room_id, member_id, request, subscriptions)
            query_id = self._record(
                connection, room_id, member_id, request, subscriptions, messages
            )
            forward = request.after_seq is not None
            return ContextResult(
                query_id=query_id,
                messages=messages,
                has_more=more,
                next_before_seq=messages[0].seq if more and not forward else None,
                next_after_seq=messages[-1].seq if more and forward else None,
                positions=read_topic_positions(connection, room_id, member_id),
            )
