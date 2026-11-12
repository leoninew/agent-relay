from pathlib import Path

from agent_relay.application.context.ports import ContextData
from agent_relay.application.delivery.ports import DeliveryRepository
from agent_relay.application.rooms.ports import RoomStore
from agent_relay.application.transactions import RepositoryScope
from agent_relay.infrastructure.persistence.database import Database
from agent_relay.infrastructure.persistence.delivery_store import SQLAlchemyDeliveryStore
from agent_relay.infrastructure.persistence.migrations import run_migrations
from agent_relay.infrastructure.persistence.repositories.context import SQLAlchemyContextRepository
from agent_relay.infrastructure.persistence.room_store import SQLAlchemyRoomStore
from agent_relay.infrastructure.persistence.scopes import SQLAlchemyScope
from agent_relay.infrastructure.persistence.transaction import SQLAlchemyTransaction


def create_database(path: Path, *, migrate_on_startup: bool = False) -> Database:
    if migrate_on_startup:
        run_migrations(path)
    return Database(path)


def create_room_store(
    database: Database, transaction: SQLAlchemyTransaction | None = None
) -> RoomStore:
    return SQLAlchemyRoomStore(database, transaction)


def create_context_scope(database: Database) -> RepositoryScope[ContextData]:
    return SQLAlchemyScope(database, SQLAlchemyContextRepository)


def create_delivery_store(database: Database) -> DeliveryRepository:
    return SQLAlchemyDeliveryStore(database)
