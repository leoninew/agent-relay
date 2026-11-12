from datetime import datetime
from typing import Protocol

from agent_relay.application.dto.context import (
    ContextMessage,
    ContextQuery,
    MemberCatalog,
)
from agent_relay.application.dto.positions import TopicPosition
from agent_relay.domain.rooms.models import VisibilityScope


class ContextQueries(Protocol):
    def catalog(self, room_id: str, member_id: str) -> MemberCatalog: ...
    def positions(self, room_id: str, member_id: str) -> list[TopicPosition]: ...


class ContextReadRepository(Protocol):
    def catalog(self, room_id: str, member_id: str) -> MemberCatalog: ...
    def subscriptions(self, room_id: str, member_id: str) -> set[str]: ...
    def load_positions(self, room_id: str, member_id: str) -> list[TopicPosition]: ...


class ContextRepository(Protocol):
    def subscriptions(self, room_id: str, member_id: str) -> set[str]: ...
    def load_positions(self, room_id: str, member_id: str) -> list[TopicPosition]: ...
    def select_messages(
        self, room_id: str, request: ContextQuery, scope: VisibilityScope
    ) -> tuple[list[ContextMessage], bool]: ...
    def record_provision(
        self,
        room_id: str,
        member_id: str,
        request: ContextQuery,
        messages: list[ContextMessage],
        updates: dict[str, int],
        query_id: str,
        provided_at: datetime,
    ) -> None: ...


class ContextData(ContextReadRepository, ContextRepository, Protocol):
    pass
