from typing import Annotated, cast

from fastapi import Depends, Request
from starlette.requests import HTTPConnection

from agent_relay.application.context.ports import ContextQueries
from agent_relay.application.context.service import ContextService
from agent_relay.infrastructure.persistence.context_queries import SQLAlchemyContextQueries
from agent_relay.infrastructure.persistence.database import Database
from agent_relay.infrastructure.persistence.repositories.context import SQLAlchemyContextRepository
from agent_relay.infrastructure.persistence.room_store import SQLAlchemyRoomStore
from agent_relay.infrastructure.persistence.scopes import SQLAlchemyScope
from agent_relay.infrastructure.persistence.transaction import SQLAlchemyTransaction


def get_database(connection: HTTPConnection) -> Database:
    return cast(Database, connection.app.state.database)


DatabaseDependency = Annotated[Database, Depends(get_database)]


def get_room_store(request: Request, database: DatabaseDependency) -> SQLAlchemyRoomStore:
    transaction = cast(SQLAlchemyTransaction, request.state.database_transaction)
    return SQLAlchemyRoomStore(database, transaction)


RoomStoreDependency = Annotated[SQLAlchemyRoomStore, Depends(get_room_store)]


def get_context_service(database: DatabaseDependency) -> ContextService:
    return ContextService(SQLAlchemyScope(database, SQLAlchemyContextRepository))


ContextServiceDependency = Annotated[ContextService, Depends(get_context_service)]


def get_context_queries(database: DatabaseDependency) -> ContextQueries:
    return SQLAlchemyContextQueries(database)


ContextQueriesDependency = Annotated[ContextQueries, Depends(get_context_queries)]
