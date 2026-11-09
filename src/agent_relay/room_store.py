import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from copy import copy
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from agent_relay.drivers.codex import QueueHead, ReceivedInput
from agent_relay.room_models import (
    USER_MEMBER_ID,
    Delivery,
    Member,
    Message,
    Room,
)
from agent_relay.room_state import RoomState
from agent_relay.sqlite_transaction import SQLiteTransaction

_MIGRATION_HEAD = "user_member"


@dataclass(frozen=True)
class ClaimedDelivery:
    room_id: str
    room: Room
    message: Message
    delivery: Delivery


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
        if versions != [(_MIGRATION_HEAD,)]:
            raise RuntimeError(
                f"Room database revisions are {versions!r}; expected {_MIGRATION_HEAD!r}. "
                "Run `python -m agent_relay.migrate` before starting the service."
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

    def interrupt_submissions(self) -> None:
        """Called only while holding the exclusive local submitter lock."""
        with self.write() as connection:
            connection.execute(
                "UPDATE deliveries SET status = 'unknown', payload = json_set(payload, "
                "'$.status', 'unknown', '$.updated_at', ?, '$.error', ?) "
                "WHERE status = 'submitting'",
                (datetime.now(UTC).isoformat(), "提交中断，入队结果未知；不会自动重发"),
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
                "UPDATE rooms SET project_path = ?, payload = ? WHERE id = ?",
                (state.room.project_path, state.room.model_dump_json(), room_id),
            )
        old_topics = {topic.id: topic for topic in original.topics}
        for topic in state.topics:
            if old_topics.get(topic.id) != topic:
                self._upsert(
                    connection,
                    "topics",
                    ("room_id", "id", "name", "payload", "deleted_at"),
                    (
                        room_id,
                        topic.id,
                        topic.name,
                        topic.model_dump_json(),
                        topic.deleted_at.isoformat() if topic.deleted_at else None,
                    ),
                )
        old_sessions = {session.id: session for session in original.sessions}
        for session in state.sessions:
            if old_sessions.get(session.id) != session:
                self._upsert(
                    connection,
                    "sessions",
                    ("room_id", "id", "payload"),
                    (
                        room_id,
                        session.id,
                        session.model_dump_json(),
                    ),
                )
        old_members = {member.id: member for member in original.members}
        for member in state.members:
            previous = old_members.get(member.id)
            if previous == member:
                continue
            self._upsert(
                connection,
                "members",
                ("room_id", "id", "name", "session_id", "payload", "deleted_at"),
                (
                    room_id,
                    member.id,
                    member.name,
                    member.session_id,
                    member.model_copy(update={"topic_ids": []}).model_dump_json(),
                    member.deleted_at.isoformat() if member.deleted_at else None,
                ),
            )
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
            "INSERT INTO rooms (id, project_path, payload) VALUES (?, ?, ?)",
            (room.id, room.project_path, room.model_dump_json()),
        )
        user = Member(
            id=USER_MEMBER_ID,
            kind="human",
            session_id=None,
            name="你",
            initials="你",
            presence="available",
            activity="",
            activity_source="user",
            topic_ids=[],
        )
        connection.execute(
            "INSERT INTO members (room_id, id, name, session_id, payload) "
            "VALUES (?, ?, ?, NULL, ?)",
            (room.id, user.id, user.name, user.model_dump_json()),
        )

    @staticmethod
    def insert_message(connection: sqlite3.Connection, room_id: str, message: Message) -> None:
        connection.execute(
            "INSERT INTO messages "
            "(room_id, id, seq, payload, publisher_id, publication_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                room_id,
                message.id,
                message.seq,
                message.model_copy(update={"deliveries": []}).model_dump_json(
                    exclude={"sender_name"}
                ),
                message.sender_id,
                message.publication_id,
            ),
        )
        connection.executemany(
            "INSERT INTO deliveries "
            "(room_id, id, message_id, target_member_id, payload, target_session_id, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    room_id,
                    delivery.id,
                    message.id,
                    delivery.target_member_id,
                    delivery.model_dump_json(),
                    delivery.target_session_id,
                    delivery.status,
                )
                for delivery in message.deliveries
            ],
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
    ) -> None:
        connection.execute(
            "UPDATE members SET payload = json_set(payload, '$.presence', ?, "
            "'$.activity', ?, '$.activity_source', 'codex', '$.observed_at', ?) "
            "WHERE room_id = ? AND id = ? AND deleted_at IS NULL",
            (presence, activity, observed_at.isoformat(), room_id, member_id),
        )
        connection.execute(
            "UPDATE sessions SET payload = json_set(payload, '$.presence', ?, "
            "'$.observed_at', ?) WHERE room_id = ? AND id = ?",
            (presence, observed_at.isoformat(), room_id, session_id),
        )

    def claim_delivery(self) -> ClaimedDelivery | None:
        with self.write() as connection:
            row = connection.execute(
                "SELECT d.room_id, d.payload, "
                "json_set(m.payload, '$.sender_name', sender.name) AS message, r.payload AS room "
                "FROM deliveries d JOIN messages m ON m.room_id = d.room_id "
                "AND m.id = d.message_id JOIN rooms r ON r.id = d.room_id "
                "JOIN members sender ON sender.room_id = m.room_id AND sender.id = m.publisher_id "
                "JOIN members target ON target.room_id = d.room_id "
                "AND target.id = d.target_member_id AND target.session_id = d.target_session_id "
                "AND json_extract(target.payload, '$.kind') = 'agent' "
                "WHERE d.status = 'pending' AND NOT EXISTS (SELECT 1 FROM deliveries active "
                "WHERE active.target_session_id = d.target_session_id "
                "AND active.status = 'submitting') ORDER BY d.rowid LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            delivery = Delivery.model_validate_json(row["payload"])
            delivery.status = "submitting"
            delivery.updated_at = datetime.now(UTC)
            connection.execute(
                "UPDATE deliveries SET status = ?, payload = ? WHERE room_id = ? AND id = ?",
                (delivery.status, delivery.model_dump_json(), row["room_id"], delivery.id),
            )
            return ClaimedDelivery(
                row["room_id"],
                Room.model_validate_json(row["room"]),
                Message.model_validate_json(row["message"]),
                delivery,
            )

    def finish_delivery(self, room_id: str, delivery: Delivery) -> None:
        with self._connection() as connection:
            connection.execute(
                "UPDATE deliveries SET status = ?, payload = ? "
                "WHERE room_id = ? AND id = ? AND status = 'submitting' "
                "AND json_extract(payload, '$.client_message_id') = ?",
                (
                    delivery.status,
                    delivery.model_dump_json(),
                    room_id,
                    delivery.id,
                    delivery.client_message_id,
                ),
            )

    def claim_activation(self, session_id: str, head: QueueHead) -> bool:
        """A fresh submission may start a confirmed Relay FIFO head at most once."""
        if head.client_message_id is None:
            return False
        with self.write() as connection:
            cursor = connection.execute(
                "UPDATE deliveries SET payload = json_set(payload, '$.activation_attempted_at', ?) "
                "WHERE target_session_id = ? AND status = 'queued' "
                "AND json_extract(payload, '$.queued_submission_id') = ? "
                "AND json_extract(payload, '$.client_message_id') = ? "
                "AND json_extract(payload, '$.activation_attempted_at') IS NULL",
                (datetime.now(UTC).isoformat(), session_id, head.id, head.client_message_id),
            )
            return cursor.rowcount == 1

    def delivery_note(self, session_id: str, client_message_id: str, note: str) -> None:
        with self.write() as connection:
            connection.execute(
                "UPDATE deliveries SET payload = json_set(payload, '$.note', ?) "
                "WHERE target_session_id = ? AND status = 'queued' "
                "AND json_extract(payload, '$.client_message_id') = ?",
                (note, session_id, client_message_id),
            )

    def unconfirmed_inputs(self) -> dict[str, set[str]]:
        with self.read() as connection:
            result: dict[str, set[str]] = {}
            for row in connection.execute(
                "SELECT target_session_id, "
                "json_extract(payload, '$.client_message_id') AS client_id "
                "FROM deliveries WHERE status IN ('queued', 'unknown') ORDER BY rowid"
            ):
                result.setdefault(row["target_session_id"], set()).add(row["client_id"])
            return result

    def confirm_input(self, session_id: str, received: ReceivedInput) -> None:
        now = datetime.now(UTC).isoformat()
        with self.write() as connection:
            connection.execute(
                "UPDATE deliveries SET status = 'received', payload = json_set(payload, "
                "'$.status', 'received', '$.updated_at', ?, '$.received_at', ?, "
                "'$.received_item_id', ?, '$.received_turn_id', ?, "
                "'$.note', NULL, '$.error', NULL) "
                "WHERE target_session_id = ? AND status IN ('queued', 'unknown') "
                "AND json_extract(payload, '$.client_message_id') = ?",
                (
                    now,
                    now,
                    received.item_id,
                    received.turn_id,
                    session_id,
                    received.client_message_id,
                ),
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
