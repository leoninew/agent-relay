from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from agent_relay.application.rooms.contracts import (
    MessagePage,
    MessageQueuePage,
    RoomEventPage,
    RoomMetadata,
    RoomSnapshot,
)
from agent_relay.domain.rooms.models import Member, Message, Room
from agent_relay.domain.rooms.state import RoomState


@dataclass(frozen=True)
class CodexQueueTarget:
    session_id: str
    submission_id: str | None


class RoomRepository(Protocol):
    def room(self, room_id: str) -> Room: ...
    def resources(self, room_id: str) -> RoomState: ...
    def metadata(self, room_id: str) -> RoomMetadata: ...
    def project_exists(self, project_path: str) -> bool: ...
    def publisher(self, room_id: str, member_id: str | None) -> Member: ...
    def joined_members(self, room_id: str) -> dict[str, str]: ...
    def bindings(self) -> list[tuple[str, str]]: ...
    def insert_room(self, room: Room) -> None: ...
    def delete_room(self, room_id: str) -> None: ...
    def save_resources(self, state: RoomState, original: RoomState) -> None: ...
    def save_observation(
        self,
        room_id: str,
        member_id: str,
        session_id: str,
        presence: str,
        activity: str,
        observed_at: datetime,
        session_name: str | None,
    ) -> None: ...


class MessageRepository(Protocol):
    def publication(
        self, room_id: str, publisher_id: str, publication_id: str
    ) -> Message | None: ...
    def message_exists(self, room_id: str, message_id: str) -> bool: ...
    def next_message_seq(self, room_id: str) -> int: ...
    def insert_message(self, room_id: str, message: Message) -> None: ...
    def clear_queue(
        self,
        room_id: str,
        *,
        topic_id: str | None,
        member_id: str | None,
        deleted_at: datetime,
    ) -> int: ...
    def codex_queue_targets(
        self, room_id: str, *, topic_id: str | None, member_id: str | None
    ) -> list[CodexQueueTarget]: ...


class RoomData(RoomRepository, MessageRepository, Protocol):
    pass


class RoomQueries(Protocol):
    def rooms(self) -> list[Room]: ...
    def member_for_session(self, room_id: str, session_id: str) -> Member: ...
    def metadata(self, room_id: str) -> RoomMetadata: ...
    def snapshot(
        self,
        room_id: str,
        topic_id: str | None = None,
        *,
        member_id: str | None = None,
        keyword: str | None = None,
        before_seq: int | None = None,
        limit: int = 50,
    ) -> RoomSnapshot: ...
    def page(
        self,
        room_id: str,
        *,
        topic_id: str | None = None,
        member_id: str | None = None,
        keyword: str | None = None,
        before_seq: int | None = None,
        limit: int = 50,
    ) -> MessagePage: ...
    def message(self, room_id: str, message_id: str) -> Message: ...
    def queue(
        self,
        room_id: str,
        *,
        topic_id: str | None = None,
        member_id: str | None = None,
        before_seq: int | None = None,
        limit: int = 50,
    ) -> MessageQueuePage: ...
    def events(self, room_id: str, after_event_id: int, limit: int = 200) -> RoomEventPage: ...


class RoomStore(Protocol):
    @property
    def queries(self) -> RoomQueries: ...
    def read_rooms(self) -> AbstractContextManager[RoomData]: ...
    def write_rooms(self) -> AbstractContextManager[RoomData]: ...
