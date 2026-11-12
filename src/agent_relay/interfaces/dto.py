from collections.abc import Callable
from dataclasses import dataclass

from agent_relay.application.capabilities.ports import CapabilityDriver
from agent_relay.application.context.ports import ContextData
from agent_relay.application.delivery.ports import QueueDriver
from agent_relay.application.members.sessions import SessionDriver
from agent_relay.application.rooms.ports import RoomStore
from agent_relay.application.transactions import RepositoryScope
from agent_relay.interfaces.http.transactions import RequestTransaction


@dataclass(frozen=True)
class HttpLogging:
    body_limit: int
    request_begin: str
    request_body: str
    request_end: str
    request_failed: str
    response_body: str


@dataclass(frozen=True)
class HttpDependencies:
    request_room_store: Callable[[RequestTransaction], RoomStore]
    room_store: RoomStore
    context_scope: RepositoryScope[ContextData]
    session_driver: SessionDriver
    queue_driver: QueueDriver
    capability_driver: CapabilityDriver
    logging: HttpLogging


@dataclass(frozen=True)
class ApiResult:
    data: object
    request_id: str | None
