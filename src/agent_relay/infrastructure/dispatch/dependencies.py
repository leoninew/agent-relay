import logging

from agent_relay.application.delivery.ports import QueueDriver
from agent_relay.application.delivery.service import DeliveryService
from agent_relay.application.members.service import MemberSessions
from agent_relay.application.members.sessions import SessionDriver
from agent_relay.infrastructure.dispatch.delivery import DeliveryRunner
from agent_relay.infrastructure.dispatch.lock import SubmitterLock
from agent_relay.infrastructure.dispatch.presence import MemberPresenceRunner
from agent_relay.infrastructure.persistence.store import SQLiteRoomStore


def create_delivery_runner(
    store: SQLiteRoomStore, driver: QueueDriver, logger: logging.Logger, concurrency: int
) -> DeliveryRunner:
    return DeliveryRunner(
        store,
        DeliveryService(store, driver, logger),
        SubmitterLock(store.path),
        logger,
        concurrency,
    )


def create_presence_runner(
    store: SQLiteRoomStore, driver: SessionDriver, logger: logging.Logger
) -> MemberPresenceRunner:
    return MemberPresenceRunner(MemberSessions(store, driver), logger)
