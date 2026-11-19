import logging
from collections.abc import Callable

from conflua.application.delivery.ports import DeliveryDriver
from conflua.application.delivery.service import DeliveryService
from conflua.application.members.service import MemberService
from conflua.application.members.sessions import SessionDriver
from conflua.infrastructure.dispatch.delivery import DeliveryRunner
from conflua.infrastructure.dispatch.lock import SubmitterLock
from conflua.infrastructure.dispatch.presence import MemberPresenceRunner
from conflua.infrastructure.images.files import FileImageStore
from conflua.infrastructure.persistence.database import Database
from conflua.infrastructure.persistence.dependencies import (
    create_delivery_store,
    create_room_store,
)


def create_delivery_runner(
    database: Database,
    driver: DeliveryDriver,
    logger: logging.Logger,
    concurrency: int,
    request_presence: Callable[[str], None],
) -> DeliveryRunner:
    store = create_delivery_store(database)
    return DeliveryRunner(
        store,
        DeliveryService(
            store,
            driver,
            logger,
            FileImageStore(database.path.parent / "rooms"),
            request_presence=request_presence,
        ),
        SubmitterLock(database.path),
        logger,
        concurrency,
    )


def create_presence_runner(
    database: Database, driver: SessionDriver, logger: logging.Logger
) -> MemberPresenceRunner:
    return MemberPresenceRunner(MemberService(create_room_store(database), driver), logger)
