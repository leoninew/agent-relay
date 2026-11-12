import logging

from agent_relay.application.delivery.ports import DeliveryDriver
from agent_relay.application.delivery.service import DeliveryService
from agent_relay.application.members.service import MemberService
from agent_relay.application.members.sessions import SessionDriver
from agent_relay.infrastructure.dispatch.delivery import DeliveryRunner
from agent_relay.infrastructure.dispatch.lock import SubmitterLock
from agent_relay.infrastructure.dispatch.presence import MemberPresenceRunner
from agent_relay.infrastructure.persistence.database import Database
from agent_relay.infrastructure.persistence.delivery_store import SQLAlchemyDeliveryStore
from agent_relay.infrastructure.persistence.room_store import SQLAlchemyRoomStore


def create_delivery_runner(
    database: Database, driver: DeliveryDriver, logger: logging.Logger, concurrency: int
) -> DeliveryRunner:
    store = SQLAlchemyDeliveryStore(database)
    return DeliveryRunner(
        store,
        DeliveryService(store, driver, logger),
        SubmitterLock(database.path),
        logger,
        concurrency,
    )


def create_presence_runner(
    database: Database, driver: SessionDriver, logger: logging.Logger
) -> MemberPresenceRunner:
    return MemberPresenceRunner(MemberService(SQLAlchemyRoomStore(database), driver), logger)
