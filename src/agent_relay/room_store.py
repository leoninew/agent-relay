import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from agent_relay.drivers.codex import QueueHead, ReceivedInput
from agent_relay.room_models import (
    Delivery,
    Member,
    Message,
    Room,
    Session,
    Topic,
)
from agent_relay.room_state import RoomState

_MIGRATION_HEAD = "member_api"


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
        with closing(sqlite3.connect(self.path, timeout=5.0, isolation_level=None)) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA busy_timeout = 5000")
            yield connection

    @contextmanager
    def read(self) -> Iterator[sqlite3.Connection]:
        with self._connection() as connection:
            connection.execute("BEGIN")
            try:
                yield connection
            finally:
                connection.rollback()

    @contextmanager
    def write(self) -> Iterator[sqlite3.Connection]:
        """A short SQL transaction for bounded reads with associated writes."""
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                yield connection
                connection.commit()
            except BaseException:
                connection.rollback()
                raise

    @contextmanager
    def transaction(self, *, write: bool) -> Iterator[dict[str, RoomState]]:
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            try:
                rooms = self._load(connection)
                original = deepcopy(rooms) if write else {}
                yield rooms
                if write:
                    self._save(connection, rooms, original)
                connection.commit()
            except BaseException:
                connection.rollback()
                raise

    def interrupt_submissions(self) -> None:
        """Called only while holding the exclusive local submitter lock."""
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "UPDATE deliveries SET status = 'unknown', payload = json_set(payload, "
                "'$.status', 'unknown', '$.updated_at', ?, '$.error', ?) "
                "WHERE status = 'submitting'",
                (datetime.now(UTC).isoformat(), "提交中断，入队结果未知；不会自动重发"),
            )
            connection.commit()

    def claim_delivery(self) -> ClaimedDelivery | None:
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT d.room_id, d.payload, m.payload AS message, r.payload AS room "
                "FROM deliveries d JOIN messages m ON m.room_id = d.room_id "
                "AND m.id = d.message_id JOIN rooms r ON r.id = d.room_id "
                "WHERE d.status = 'pending' AND NOT EXISTS (SELECT 1 FROM deliveries active "
                "WHERE active.target_session_id = d.target_session_id "
                "AND active.status = 'submitting') ORDER BY d.rowid LIMIT 1"
            ).fetchone()
            if row is None:
                connection.commit()
                return None
            delivery = Delivery.model_validate_json(row["payload"])
            delivery.status = "submitting"
            delivery.updated_at = datetime.now(UTC)
            connection.execute(
                "UPDATE deliveries SET status = ?, payload = ? WHERE room_id = ? AND id = ?",
                (delivery.status, delivery.model_dump_json(), row["room_id"], delivery.id),
            )
            connection.commit()
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
    def _load(connection: sqlite3.Connection) -> dict[str, RoomState]:
        rooms = {
            row["id"]: RoomState(room=Room.model_validate_json(row["payload"]))
            for row in connection.execute("SELECT id, payload FROM rooms ORDER BY rowid")
        }
        for row in connection.execute("SELECT room_id, payload FROM topics ORDER BY rowid"):
            rooms[row["room_id"]].topics.append(Topic.model_validate_json(row["payload"]))
        for row in connection.execute("SELECT room_id, payload FROM sessions ORDER BY rowid"):
            rooms[row["room_id"]].sessions.append(Session.model_validate_json(row["payload"]))
        subscriptions: dict[tuple[str, str], list[str]] = {}
        for row in connection.execute("SELECT * FROM member_topics ORDER BY position"):
            subscriptions.setdefault((row["room_id"], row["member_id"]), []).append(row["topic_id"])
        for row in connection.execute("SELECT room_id, id, payload FROM members ORDER BY rowid"):
            member = Member.model_validate_json(row["payload"])
            member.topic_ids = subscriptions.get((row["room_id"], row["id"]), [])
            rooms[row["room_id"]].members.append(member)
        deliveries: dict[tuple[str, str], list[Delivery]] = {}
        for row in connection.execute(
            "SELECT room_id, message_id, payload FROM deliveries ORDER BY rowid"
        ):
            deliveries.setdefault((row["room_id"], row["message_id"]), []).append(
                Delivery.model_validate_json(row["payload"])
            )
        for row in connection.execute("SELECT room_id, id, payload FROM messages ORDER BY seq"):
            message = Message.model_validate_json(row["payload"])
            message.deliveries = deliveries.get((row["room_id"], row["id"]), [])
            rooms[row["room_id"]].messages.append(message)
        return rooms

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

    def _save(
        self,
        connection: sqlite3.Connection,
        rooms: dict[str, RoomState],
        original: dict[str, RoomState],
    ) -> None:
        for room_id, state in rooms.items():
            old = original.get(room_id)
            if old == state:
                continue
            if old is None or old.room != state.room:
                self._upsert(
                    connection,
                    "rooms",
                    ("id", "project_path", "payload"),
                    (room_id, state.room.project_path, state.room.model_dump_json()),
                    key="id",
                )
            old_topics = {topic.id: topic for topic in old.topics} if old else {}
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
            old_sessions = {session.id: session for session in old.sessions} if old else {}
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
            old_members = {member.id: member for member in old.members} if old else {}
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
            old_messages = {message.id: message for message in old.messages} if old else {}
            for message in state.messages:
                previous_message = old_messages.get(message.id)
                if previous_message == message:
                    continue
                self._upsert(
                    connection,
                    "messages",
                    ("room_id", "id", "seq", "payload", "publisher_id", "publication_id"),
                    (
                        room_id,
                        message.id,
                        message.seq,
                        message.model_copy(update={"deliveries": []}).model_dump_json(),
                        message.sender_id or "",
                        message.publication_id,
                    ),
                )
                old_deliveries = (
                    {delivery.id: delivery for delivery in previous_message.deliveries}
                    if previous_message
                    else {}
                )
                for delivery in message.deliveries:
                    if old_deliveries.get(delivery.id) != delivery:
                        self._upsert(
                            connection,
                            "deliveries",
                            (
                                "room_id",
                                "id",
                                "message_id",
                                "target_member_id",
                                "payload",
                                "target_session_id",
                                "status",
                            ),
                            (
                                room_id,
                                delivery.id,
                                message.id,
                                delivery.target_member_id,
                                delivery.model_dump_json(),
                                delivery.target_session_id,
                                delivery.status,
                            ),
                        )
