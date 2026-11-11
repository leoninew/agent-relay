from typing import Annotated, cast

from fastapi import Depends, Request
from starlette.requests import HTTPConnection

from agent_relay.application.members.context import MemberContext
from agent_relay.infrastructure.persistence.database import Database
from agent_relay.infrastructure.persistence.member_context import SQLAlchemyMemberContext
from agent_relay.infrastructure.persistence.room_store import SQLAlchemyRoomStore
from agent_relay.infrastructure.persistence.transaction import SQLAlchemyTransaction


def get_database(connection: HTTPConnection) -> Database:
    return cast(Database, connection.app.state.database)


DatabaseDependency = Annotated[Database, Depends(get_database)]


def get_room_store(request: Request, database: DatabaseDependency) -> SQLAlchemyRoomStore:
    transaction = cast(SQLAlchemyTransaction, request.state.database_transaction)
    return SQLAlchemyRoomStore(database, transaction)


RoomStoreDependency = Annotated[SQLAlchemyRoomStore, Depends(get_room_store)]


def get_member_context(database: DatabaseDependency) -> MemberContext:
    return SQLAlchemyMemberContext(database)


MemberContextDependency = Annotated[MemberContext, Depends(get_member_context)]
