from typing import cast

from agent_relay.application.capabilities.ports import CapabilityDriver
from agent_relay.application.delivery.ports import QueueDriver
from agent_relay.application.members.sessions import SessionDriver
from agent_relay.application.rooms.ports import RoomStore
from agent_relay.bootstrap.settings import LoggingSettings
from agent_relay.infrastructure.persistence.database import Database
from agent_relay.infrastructure.persistence.dependencies import (
    create_context_scope,
    create_room_store,
)
from agent_relay.infrastructure.persistence.transaction import SQLAlchemyTransaction
from agent_relay.interfaces.dto import HttpDependencies, HttpLogging
from agent_relay.interfaces.http.transactions import RequestTransaction


def create_http_dependencies(
    database: Database,
    sessions: SessionDriver,
    queue: QueueDriver,
    capabilities: CapabilityDriver,
    logging: LoggingSettings,
) -> HttpDependencies:
    def request_room_store(transaction: RequestTransaction) -> RoomStore:
        return create_room_store(database, cast(SQLAlchemyTransaction, transaction))

    return HttpDependencies(
        request_room_store=request_room_store,
        room_store=create_room_store(database),
        context_scope=create_context_scope(database),
        session_driver=sessions,
        queue_driver=queue,
        capability_driver=capabilities,
        logging=HttpLogging(
            body_limit=logging.body.limit,
            request_begin=logging.request.begin,
            request_body=logging.request.body,
            request_end=logging.request.end,
            request_failed=logging.request.failed,
            response_body=logging.response.body,
        ),
    )
