from datetime import datetime
from typing import Protocol

from agent_relay.application.dto.messages import CodexQueueTarget
from agent_relay.domain.rooms.models import Message


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
        message_id: str | None = None,
    ) -> int: ...
    def codex_queue_targets(
        self, room_id: str, *, topic_id: str | None, member_id: str | None
    ) -> list[CodexQueueTarget]: ...
