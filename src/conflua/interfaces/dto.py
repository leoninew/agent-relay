from collections.abc import Callable
from dataclasses import dataclass

from conflua.application.capabilities.ports import CapabilityDriver
from conflua.application.channels.service import ChannelService
from conflua.application.context.ports import ContextData
from conflua.application.delivery.ports import QueueDriver
from conflua.application.images.ports import ImageStore
from conflua.application.member_roles.service import MemberRoleService
from conflua.application.members.sessions import SessionDriver
from conflua.application.rooms.ports import RoomStore
from conflua.application.transactions import RepositoryScope
from conflua.interfaces.http.transactions import RequestTransaction


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
    request_channel_service: Callable[[RequestTransaction], ChannelService]
    request_member_role_service: Callable[[RequestTransaction], MemberRoleService]
    room_store: RoomStore
    context_for_channel: Callable[[str], RepositoryScope[ContextData]]
    session_driver: SessionDriver
    queue_driver: QueueDriver
    capability_driver: CapabilityDriver
    logging: HttpLogging
    image_store: ImageStore | None = None


@dataclass(frozen=True)
class ApiResult:
    data: object
    request_id: str | None
