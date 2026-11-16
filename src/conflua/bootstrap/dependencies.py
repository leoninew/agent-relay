from typing import cast

from conflua.application.capabilities.ports import CapabilityDriver
from conflua.application.channels.service import ChannelService
from conflua.application.delivery.ports import QueueDriver
from conflua.application.members.sessions import SessionDriver
from conflua.application.rooms.ports import RoomStore
from conflua.bootstrap.settings import LoggingSettings
from conflua.domain.rooms.models import DEFAULT_CHANNEL_ID
from conflua.infrastructure.git.worktrees import GitWorktrees
from conflua.infrastructure.images.files import FileImageStore
from conflua.infrastructure.persistence.channel_store import SQLAlchemyChannelStore
from conflua.infrastructure.persistence.database import Database
from conflua.infrastructure.persistence.dependencies import (
    create_room_store,
)
from conflua.infrastructure.persistence.repositories.context import SQLAlchemyContextRepository
from conflua.infrastructure.persistence.scopes import SQLAlchemyScope
from conflua.infrastructure.persistence.transaction import SQLAlchemyTransaction
from conflua.interfaces.dto import HttpDependencies, HttpLogging
from conflua.interfaces.http.transactions import RequestTransaction


def create_http_dependencies(
    database: Database,
    sessions: SessionDriver,
    queue: QueueDriver,
    capabilities: CapabilityDriver,
    logging: LoggingSettings,
) -> HttpDependencies:
    def request_room_store(transaction: RequestTransaction) -> RoomStore:
        return create_room_store(database, cast(SQLAlchemyTransaction, transaction))

    def request_channel_service(transaction: RequestTransaction) -> ChannelService:
        return ChannelService(
            SQLAlchemyChannelStore(database, cast(SQLAlchemyTransaction, transaction)),
            GitWorktrees(),
            database.path.parent / "worktrees",
        )

    return HttpDependencies(
        request_room_store=request_room_store,
        request_channel_service=request_channel_service,
        room_store=create_room_store(database),
        session_driver=sessions,
        queue_driver=queue,
        capability_driver=capabilities,
        image_store=FileImageStore(database.path.parent / "rooms", DEFAULT_CHANNEL_ID),
        context_for_channel=lambda channel_id: SQLAlchemyScope(
            database, lambda session: SQLAlchemyContextRepository(session, channel_id)
        ),
        logging=HttpLogging(
            body_limit=logging.body.limit,
            request_begin=logging.request.begin,
            request_body=logging.request.body,
            request_end=logging.request.end,
            request_failed=logging.request.failed,
            response_body=logging.response.body,
        ),
    )
