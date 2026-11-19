from pathlib import Path

from conflua.application.delivery.ports import DeliveryRepository
from conflua.application.rooms.ports import RoomStore
from conflua.infrastructure.persistence.database import Database
from conflua.infrastructure.persistence.delivery_store import SQLAlchemyDeliveryStore
from conflua.infrastructure.persistence.migrations import run_migrations
from conflua.infrastructure.persistence.room_store import SQLAlchemyRoomStore
from conflua.infrastructure.persistence.transaction import SQLAlchemyTransaction


def create_database(path: Path) -> Database:
    run_migrations(path)
    return Database(path)


def create_room_store(
    database: Database, transaction: SQLAlchemyTransaction | None = None
) -> RoomStore:
    return SQLAlchemyRoomStore(database, transaction)


def create_delivery_store(database: Database) -> DeliveryRepository:
    return SQLAlchemyDeliveryStore(database)
