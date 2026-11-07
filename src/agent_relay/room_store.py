import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from copy import deepcopy
from pathlib import Path

from agent_relay.room_models import (
    Delivery,
    Member,
    Message,
    Room,
    Session,
    Topic,
)
from agent_relay.room_state import RoomState

_MIGRATION_HEAD = "sidebar_node_actions"


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
                    ("room_id", "id", "seq", "payload"),
                    (
                        room_id,
                        message.id,
                        message.seq,
                        message.model_copy(update={"deliveries": []}).model_dump_json(),
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
                            ("room_id", "id", "message_id", "target_member_id", "payload"),
                            (
                                room_id,
                                delivery.id,
                                message.id,
                                delivery.target_member_id,
                                delivery.model_dump_json(),
                            ),
                        )
