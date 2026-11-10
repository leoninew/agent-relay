import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from copy import copy
from datetime import UTC, datetime, timedelta
from pathlib import Path

from agent_relay.application.delivery.ports import ClaimedDelivery, QueueHead, ReceivedInput
from agent_relay.application.rooms.ports import RoomData, RoomQueries
from agent_relay.domain.rooms.events import RoomChange
from agent_relay.domain.rooms.models import (
    USER_MEMBER_ID,
    Delivery,
    Message,
    Room,
)
from agent_relay.domain.rooms.state import RoomState
from agent_relay.infrastructure.persistence.migrations import MIGRATION_HEAD
from agent_relay.infrastructure.persistence.records import (
    delivery_from_record,
    delivery_record,
    messages_from_rows,
)
from agent_relay.infrastructure.persistence.transaction import SQLiteTransaction


class SQLiteRoomStore:
    """Transactions over persisted room resources, with no cross-request state cache."""

    def __init__(self, path: Path) -> None:
        self.path = path.expanduser().resolve()
        self._request_transaction: SQLiteTransaction | None = None
        if not self.path.is_file():
            raise RuntimeError("Room database is missing; run `python -m agent_relay.migrate`")
        with closing(sqlite3.connect(self.path, timeout=5.0)) as connection:
            try:
                versions = connection.execute("SELECT version_num FROM alembic_version").fetchall()
            except sqlite3.Error as exc:
                raise RuntimeError(
                    "Room database is not migrated; run `python -m agent_relay.migrate`"
                ) from exc
        if versions != [(MIGRATION_HEAD,)]:
            raise RuntimeError(
                f"Room database revisions are {versions!r}; expected {MIGRATION_HEAD!r}. "
                "Run `python -m agent_relay.migrate` or rebuild an incompatible "
                "development database."
            )

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        with closing(self._open_connection()) as connection:
            yield connection

    def _open_connection(self) -> sqlite3.Connection:
        # A request can execute in FastAPI's pool and finish in another worker.
        connection = sqlite3.connect(
            self.path, timeout=5.0, isolation_level=None, check_same_thread=False
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def request_transaction(self) -> SQLiteTransaction:
        return SQLiteTransaction(self._open_connection)

    @property
    def queries(self) -> RoomQueries:
        from agent_relay.infrastructure.persistence.queries import SQLiteRoomQueries

        return SQLiteRoomQueries(self)

    @contextmanager
    def read_rooms(self) -> Iterator[RoomData]:
        from agent_relay.infrastructure.persistence.rooms import SQLiteRoomData

        with self.read() as connection:
            yield SQLiteRoomData(self, connection)

    @contextmanager
    def write_rooms(self) -> Iterator[RoomData]:
        from agent_relay.infrastructure.persistence.rooms import SQLiteRoomData

        with self.write() as connection:
            yield SQLiteRoomData(self, connection)

    def for_request(self, transaction: SQLiteTransaction) -> "SQLiteRoomStore":
        store = copy(self)
        store._request_transaction = transaction
        return store

    @contextmanager
    def read(self) -> Iterator[sqlite3.Connection]:
        if self._request_transaction is not None:
            connection = self._request_transaction.connection
            if connection is not None:
                yield connection
                return
        with self._connection() as connection:
            connection.execute("BEGIN")
            try:
                yield connection
            finally:
                connection.rollback()

    @contextmanager
    def write(self) -> Iterator[sqlite3.Connection]:
        """Borrow request writes, or own a short transaction for a background operation."""
        if self._request_transaction is not None:
            yield self._request_transaction.begin()
            return
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                yield connection
                connection.commit()
            except BaseException:
                connection.rollback()
                raise

    @staticmethod
    def record_event(connection: sqlite3.Connection, event: RoomChange) -> None:
        connection.execute(
            "INSERT INTO room_events(room_id, kind, entity_id, message_id) VALUES (?, ?, ?, ?)",
            (event.room_id, event.kind, event.entity_id, event.message_id),
        )

    def interrupt_submissions(self) -> None:
        """Called only while holding the exclusive local submitter lock."""
        with self.write() as connection:
            events = connection.execute(
                "SELECT room_id, id, message_id FROM deliveries WHERE status = 'submitting'"
            ).fetchall()
            cursor = connection.execute(
                "UPDATE deliveries SET status = 'unknown', updated_at = ?, error = ? "
                "WHERE status = 'submitting'",
                (datetime.now(UTC).isoformat(), "提交中断，入队结果未知；不会自动重发"),
            )
            if cursor.rowcount:
                for row in events:
                    self.record_event(
                        connection,
                        RoomChange(row["room_id"], "delivery", row["id"], row["message_id"]),
                    )

    def save_resources(
        self,
        connection: sqlite3.Connection,
        state: RoomState,
        original: RoomState,
    ) -> None:
        """Flush one room's resource changes inside its existing write transaction."""
        room_id = state.room.id
        if state.room != original.room:
            connection.execute(
                "UPDATE rooms SET project_path = ?, name = ?, description = ? WHERE id = ?",
                (state.room.project_path, state.room.name, state.room.description, room_id),
            )
            self.record_event(connection, RoomChange(room_id, "room", room_id))
        old_topics = {topic.id: topic for topic in original.topics}
        for topic in state.topics:
            if old_topics.get(topic.id) != topic:
                self._upsert(
                    connection,
                    "topics",
                    ("room_id", "id", "name", "description", "created_at", "deleted_at"),
                    (
                        room_id,
                        topic.id,
                        topic.name,
                        topic.description,
                        topic.created_at.isoformat() if topic.created_at else None,
                        topic.deleted_at.isoformat() if topic.deleted_at else None,
                    ),
                )
                self.record_event(connection, RoomChange(room_id, "topic", topic.id))
        old_sessions = {session.id: session for session in original.sessions}
        for session in state.sessions:
            if old_sessions.get(session.id) != session:
                self._upsert(
                    connection,
                    "sessions",
                    (
                        "room_id",
                        "id",
                        "name",
                        "provider",
                        "project_path",
                        "presence",
                        "observed_at",
                    ),
                    (
                        room_id,
                        session.id,
                        session.name,
                        session.provider,
                        session.project_path,
                        session.presence,
                        session.observed_at.isoformat() if session.observed_at else None,
                    ),
                )
                self.record_event(connection, RoomChange(room_id, "session", session.id))
        old_members = {member.id: member for member in original.members}
        for member in state.members:
            previous = old_members.get(member.id)
            if previous == member:
                continue
            self._upsert(
                connection,
                "members",
                (
                    "room_id",
                    "id",
                    "name",
                    "session_id",
                    "kind",
                    "initials",
                    "presence",
                    "activity",
                    "activity_source",
                    "observed_at",
                    "deleted_at",
                ),
                (
                    room_id,
                    member.id,
                    member.name,
                    member.session_id,
                    member.kind,
                    member.initials,
                    member.presence,
                    member.activity,
                    member.activity_source,
                    member.observed_at.isoformat() if member.observed_at else None,
                    member.deleted_at.isoformat() if member.deleted_at else None,
                ),
            )
            self.record_event(connection, RoomChange(room_id, "member", member.id))
            if previous is None or previous.topic_ids != member.topic_ids:
                connection.execute(
                    "DELETE FROM member_topics WHERE room_id = ? AND member_id = ?",
                    (room_id, member.id),
                )
                connection.executemany(
                    "INSERT INTO member_topics(room_id, member_id, topic_id, position) "
                    "VALUES (?, ?, ?, ?)",
                    [
                        (room_id, member.id, topic_id, position)
                        for position, topic_id in enumerate(member.topic_ids)
                    ],
                )

    @staticmethod
    def insert_room(connection: sqlite3.Connection, room: Room) -> None:
        connection.execute(
            "INSERT INTO rooms (id, project_path, name, description) VALUES (?, ?, ?, ?)",
            (room.id, room.project_path, room.name, room.description),
        )
        connection.execute(
            "INSERT INTO members "
            "(room_id, id, name, kind, initials, presence, activity, activity_source) "
            "VALUES (?, ?, '你', 'human', '你', 'available', '', 'user')",
            (room.id, USER_MEMBER_ID),
        )
        SQLiteRoomStore.record_event(connection, RoomChange(room.id, "room", room.id))
        SQLiteRoomStore.record_event(connection, RoomChange(room.id, "member", USER_MEMBER_ID))

    @staticmethod
    def insert_message(connection: sqlite3.Connection, room_id: str, message: Message) -> None:
        connection.execute(
            "INSERT INTO messages "
            "(room_id, id, seq, publisher_id, publication_id, content, "
            "reply_to_message_id, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                room_id,
                message.id,
                message.seq,
                message.sender_id,
                message.publication_id,
                message.content,
                message.reply_to_message_id,
                message.created_at.isoformat(),
            ),
        )
        for table, column, targets in (
            ("message_topics", "topic_id", message.topic_ids),
            ("message_mentions", "member_id", message.mentioned_member_ids),
            ("message_recipients", "member_id", message.recipient_ids),
        ):
            connection.executemany(
                f"INSERT INTO {table}(room_id, message_id, {column}, position) VALUES (?, ?, ?, ?)",
                [
                    (room_id, message.id, target_id, position)
                    for position, target_id in enumerate(targets)
                ],
            )
        SQLiteRoomStore.record_event(
            connection, RoomChange(room_id, "message", message.id, message.id)
        )
        for delivery in message.deliveries:
            record = delivery_record(delivery)
            columns = ("room_id", "message_id", *record)
            slots = ", ".join("?" for _ in columns)
            connection.execute(
                f"INSERT INTO deliveries ({', '.join(columns)}) VALUES ({slots})",
                (room_id, message.id, *record.values()),
            )
            SQLiteRoomStore.record_event(
                connection,
                RoomChange(room_id, "delivery", delivery.id, message.id),
            )

    @staticmethod
    def save_observation(
        connection: sqlite3.Connection,
        room_id: str,
        member_id: str,
        session_id: str,
        presence: str,
        activity: str,
        observed_at: datetime,
        session_name: str | None,
    ) -> None:
        checkpoint_before = (observed_at - timedelta(seconds=30)).isoformat()
        member_cursor = connection.execute(
            "UPDATE members SET presence = ?, activity = ?, "
            "activity_source = 'codex', observed_at = ? "
            "WHERE room_id = ? AND id = ? AND session_id = ? AND deleted_at IS NULL "
            "AND (presence IS NOT ? OR activity IS NOT ? OR activity_source IS NOT 'codex' "
            "OR observed_at IS NULL OR julianday(observed_at) <= julianday(?))",
            (
                presence,
                activity,
                observed_at.isoformat(),
                room_id,
                member_id,
                session_id,
                presence,
                activity,
                checkpoint_before,
            ),
        )
        if member_cursor.rowcount:
            SQLiteRoomStore.record_event(connection, RoomChange(room_id, "member", member_id))
        session_cursor = connection.execute(
            "UPDATE sessions SET presence = ?, observed_at = ?, name = COALESCE(?, name) "
            "WHERE room_id = ? AND id = ? "
            "AND (presence IS NOT ? OR (? IS NOT NULL AND name IS NOT ?) "
            "OR observed_at IS NULL OR julianday(observed_at) <= julianday(?))",
            (
                presence,
                observed_at.isoformat(),
                session_name,
                room_id,
                session_id,
                presence,
                session_name,
                session_name,
                checkpoint_before,
            ),
        )
        if session_cursor.rowcount:
            SQLiteRoomStore.record_event(connection, RoomChange(room_id, "session", session_id))

    def claim_delivery(self) -> ClaimedDelivery | None:
        with self.write() as connection:
            row = connection.execute(
                "SELECT d.* FROM deliveries d JOIN members target ON target.room_id = d.room_id "
                "AND target.id = d.target_member_id AND target.session_id = d.target_session_id "
                "AND target.kind = 'agent' "
                "WHERE d.status = 'pending' AND NOT EXISTS (SELECT 1 FROM deliveries active "
                "WHERE active.target_session_id = d.target_session_id "
                "AND active.status = 'submitting') ORDER BY d.rowid LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            delivery = delivery_from_record(dict(row))
            delivery.status = "submitting"
            delivery.updated_at = datetime.now(UTC)
            connection.execute(
                "UPDATE deliveries SET status = ?, updated_at = ? WHERE room_id = ? AND id = ?",
                (delivery.status, delivery.updated_at.isoformat(), row["room_id"], delivery.id),
            )
            self.record_event(
                connection,
                RoomChange(row["room_id"], "delivery", row["id"], row["message_id"]),
            )
            room = connection.execute(
                "SELECT * FROM rooms WHERE id = ?", (row["room_id"],)
            ).fetchone()
            message = connection.execute(
                "SELECT m.*, sender.name AS sender_name FROM messages m JOIN members sender "
                "ON sender.room_id = m.room_id AND sender.id = m.publisher_id "
                "WHERE m.room_id = ? AND m.id = ?",
                (row["room_id"], row["message_id"]),
            ).fetchone()
            return ClaimedDelivery(
                row["room_id"],
                Room.model_validate(dict(room)),
                messages_from_rows(connection, row["room_id"], [message])[0],
                delivery,
            )

    def finish_delivery(self, room_id: str, delivery: Delivery) -> None:
        with self.write() as connection:
            event = connection.execute(
                "SELECT message_id FROM deliveries WHERE room_id = ? AND id = ? "
                "AND status = 'submitting' "
                "AND client_message_id = ?",
                (room_id, delivery.id, delivery.client_message_id),
            ).fetchone()
            record = delivery_record(delivery)
            for field in ("id", "target_member_id", "target_session_id", "client_message_id"):
                del record[field]
            assignments = ", ".join(f"{field} = ?" for field in record)
            cursor = connection.execute(
                f"UPDATE deliveries SET {assignments} "
                "WHERE room_id = ? AND id = ? AND status = 'submitting' "
                "AND client_message_id = ?",
                (
                    *record.values(),
                    room_id,
                    delivery.id,
                    delivery.client_message_id,
                ),
            )
            if cursor.rowcount and event is not None:
                self.record_event(
                    connection,
                    RoomChange(room_id, "delivery", delivery.id, event["message_id"]),
                )

    def claim_activation(self, session_id: str, head: QueueHead) -> bool:
        """A fresh submission may start a confirmed Relay FIFO head at most once."""
        if head.client_message_id is None:
            return False
        with self.write() as connection:
            criteria = (
                "target_session_id = ? AND status = 'queued' "
                "AND queued_submission_id = ? AND client_message_id = ? "
                "AND activation_attempted_at IS NULL"
            )
            parameters = (session_id, head.id, head.client_message_id)
            events = connection.execute(
                "SELECT room_id, id, message_id FROM deliveries WHERE " + criteria,
                parameters,
            ).fetchall()
            cursor = connection.execute(
                "UPDATE deliveries SET activation_attempted_at = ? WHERE " + criteria,
                (datetime.now(UTC).isoformat(), *parameters),
            )
            if cursor.rowcount:
                for row in events:
                    self.record_event(
                        connection,
                        RoomChange(row["room_id"], "delivery", row["id"], row["message_id"]),
                    )
            return cursor.rowcount == 1

    def delivery_note(self, session_id: str, client_message_id: str, note: str) -> None:
        with self.write() as connection:
            events = connection.execute(
                "SELECT room_id, id, message_id FROM deliveries "
                "WHERE target_session_id = ? AND status = 'queued' "
                "AND client_message_id = ?",
                (session_id, client_message_id),
            ).fetchall()
            cursor = connection.execute(
                "UPDATE deliveries SET note = ? "
                "WHERE target_session_id = ? AND status = 'queued' "
                "AND client_message_id = ?",
                (note, session_id, client_message_id),
            )
            if cursor.rowcount:
                for row in events:
                    self.record_event(
                        connection,
                        RoomChange(row["room_id"], "delivery", row["id"], row["message_id"]),
                    )

    def unconfirmed_inputs(self) -> dict[str, set[str]]:
        with self.read() as connection:
            result: dict[str, set[str]] = {}
            for row in connection.execute(
                "SELECT target_session_id, client_message_id "
                "FROM deliveries WHERE status IN ('queued', 'unknown') ORDER BY rowid"
            ):
                result.setdefault(row["target_session_id"], set()).add(row["client_message_id"])
            return result

    def confirm_input(self, session_id: str, received: ReceivedInput) -> None:
        now = datetime.now(UTC).isoformat()
        with self.write() as connection:
            events = connection.execute(
                "SELECT room_id, id, message_id FROM deliveries "
                "WHERE target_session_id = ? AND status IN ('queued', 'unknown') "
                "AND client_message_id = ?",
                (session_id, received.client_message_id),
            ).fetchall()
            cursor = connection.execute(
                "UPDATE deliveries SET status = 'received', updated_at = ?, received_at = ?, "
                "received_item_id = ?, received_turn_id = ?, note = NULL, error = NULL "
                "WHERE target_session_id = ? AND status IN ('queued', 'unknown') "
                "AND client_message_id = ?",
                (
                    now,
                    now,
                    received.item_id,
                    received.turn_id,
                    session_id,
                    received.client_message_id,
                ),
            )
            if cursor.rowcount:
                for row in events:
                    self.record_event(
                        connection,
                        RoomChange(row["room_id"], "delivery", row["id"], row["message_id"]),
                    )

    @staticmethod
    def _upsert(
        connection: sqlite3.Connection,
        table: str,
        columns: tuple[str, ...],
        values: tuple[str | int | None, ...],
        *,
        key: str = "room_id, id",
    ) -> None:
        # Table and column identifiers are constants owned by this module.
        placeholders = ", ".join("?" for _ in columns)
        updates = ", ".join(f"{column} = excluded.{column}" for column in columns)
        connection.execute(
            f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders}) "
            f"ON CONFLICT({key}) DO UPDATE SET {updates}",
            values,
        )
