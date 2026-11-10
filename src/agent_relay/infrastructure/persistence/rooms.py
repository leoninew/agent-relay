import sqlite3
from datetime import datetime

from agent_relay.application.rooms.contracts import RoomMetadata
from agent_relay.domain.rooms.events import RoomChange
from agent_relay.domain.rooms.models import Member, Message, Room
from agent_relay.domain.rooms.state import RoomState
from agent_relay.infrastructure.persistence.queries import SQLiteRoomQueries
from agent_relay.infrastructure.persistence.store import SQLiteRoomStore


class SQLiteRoomData:
    def __init__(self, store: SQLiteRoomStore, connection: sqlite3.Connection) -> None:
        self.store = store
        self.connection = connection
        self.queries = SQLiteRoomQueries(store)

    def room(self, room_id: str) -> Room:
        return self.queries.room_in(self.connection, room_id)

    def resources(self, room_id: str) -> RoomState:
        return self.queries.resources_in(self.connection, room_id)

    def metadata(self, room_id: str) -> RoomMetadata:
        return self.queries.metadata_in(self.connection, room_id)

    def project_exists(self, project_path: str) -> bool:
        return self.queries.project_exists_in(self.connection, project_path)

    def publisher(self, room_id: str, member_id: str | None) -> Member:
        return self.queries.publisher_in(self.connection, room_id, member_id)

    def publication(self, room_id: str, publisher_id: str, publication_id: str) -> Message | None:
        return self.queries.publication_in(self.connection, room_id, publisher_id, publication_id)

    def message_exists(self, room_id: str, message_id: str) -> bool:
        return self.queries.message_exists_in(self.connection, room_id, message_id)

    def next_message_seq(self, room_id: str) -> int:
        return self.queries.next_message_seq_in(self.connection, room_id)

    def joined_members(self, room_id: str) -> dict[str, str]:
        return self.queries.joined_members_in(self.connection, room_id)

    def bindings(self) -> list[tuple[str, str]]:
        return [
            (row["room_id"], row["session_id"])
            for row in self.connection.execute(
                "SELECT room_id, session_id FROM members WHERE deleted_at IS NULL "
                "AND session_id IS NOT NULL AND kind = 'agent'"
            )
        ]

    def insert_room(self, room: Room) -> None:
        self.store.insert_room(self.connection, room)

    def delete_room(self, room_id: str) -> None:
        for table in (
            "deliveries",
            "member_context_messages",
            "member_context_queries",
            "member_topic_positions",
            "member_topics",
            "message_topics",
            "message_mentions",
            "message_recipients",
            "messages",
            "members",
            "sessions",
            "topics",
            "room_events",
        ):
            self.connection.execute(f"DELETE FROM {table} WHERE room_id = ?", (room_id,))
        self.connection.execute("DELETE FROM rooms WHERE id = ?", (room_id,))

    def save_resources(self, state: RoomState, original: RoomState) -> None:
        self.store.save_resources(self.connection, state, original)

    def insert_message(self, room_id: str, message: Message) -> None:
        self.store.insert_message(self.connection, room_id, message)

    def clear_queue(
        self,
        room_id: str,
        *,
        topic_id: str | None,
        member_id: str | None,
        deleted_at: datetime,
    ) -> int:
        clauses, args = self.queries.message_scope_in(
            self.connection, room_id, topic_id=topic_id, member_id=member_id
        )
        criteria = (
            "room_id = ? AND deleted_at IS NULL "
            "AND status IN ('pending', 'submitting', 'queued') "
            f"AND message_id IN (SELECT m.id FROM messages m WHERE {' AND '.join(clauses)})"
        )
        parameters = (room_id, *args)
        events = self.connection.execute(
            f"SELECT id, message_id FROM deliveries WHERE {criteria}", parameters
        ).fetchall()
        self.connection.execute(
            f"UPDATE deliveries SET deleted_at = ?, updated_at = ? WHERE {criteria}",
            (deleted_at.isoformat(), deleted_at.isoformat(), *parameters),
        )
        for event in events:
            self.store.record_event(
                self.connection, RoomChange(room_id, "delivery", event["id"], event["message_id"])
            )
        return len({event["message_id"] for event in events})

    def save_observation(
        self,
        room_id: str,
        member_id: str,
        session_id: str,
        presence: str,
        activity: str,
        observed_at: datetime,
        session_name: str | None,
    ) -> None:
        self.store.save_observation(
            self.connection,
            room_id,
            member_id,
            session_id,
            presence,
            activity,
            observed_at,
            session_name,
        )
