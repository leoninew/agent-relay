from datetime import datetime
from typing import Protocol

from agent_relay.application.messages.contracts import (
    MessagePage,
    MessageQueuePage,
)
from agent_relay.application.messages.ports import MessageRepository
from agent_relay.application.rooms.contracts import (
    RoomEventPage,
    RoomMetadata,
    RoomSnapshot,
)
from agent_relay.application.transactions import RepositoryScope
from agent_relay.domain.rooms.models import Member, Message, Room
from agent_relay.domain.rooms.state import RoomState


class RoomRepository(Protocol):
    def room(self, room_id: str) -> Room: ...
    def resources(self, room_id: str) -> RoomState: ...
    def metadata(self, room_id: str) -> RoomMetadata: ...
    def project_exists(self, project_path: str) -> bool: ...
    def publisher(self, room_id: str, member_id: str | None) -> Member: ...
    def joined_members(self, room_id: str) -> dict[str, str]: ...
    def bindings(self) -> list[tuple[str, str]]: ...
    def insert_room(self, room: Room, user: Member) -> None: ...
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
        *,
        refresh_cutoff: datetime,
    ) -> None: ...


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


class RoomStore(RepositoryScope[RoomData], Protocol):
    @property
    def queries(self) -> RoomQueries: ...
