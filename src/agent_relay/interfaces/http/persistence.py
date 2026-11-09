from typing import Annotated, cast

from fastapi import Depends, Request
from starlette.requests import HTTPConnection

from agent_relay.application.members.context import MemberContext
from agent_relay.infrastructure.persistence.context import SQLiteMemberContext
from agent_relay.infrastructure.persistence.store import SQLiteRoomStore
from agent_relay.infrastructure.persistence.transaction import SQLiteTransaction


def get_database(connection: HTTPConnection) -> SQLiteRoomStore:
    return cast(SQLiteRoomStore, connection.app.state.database)


DatabaseDependency = Annotated[SQLiteRoomStore, Depends(get_database)]


def get_room_store(request: Request, database: DatabaseDependency) -> SQLiteRoomStore:
    transaction = cast(SQLiteTransaction, request.state.database_transaction)
    return database.for_request(transaction)


RoomStoreDependency = Annotated[SQLiteRoomStore, Depends(get_room_store)]


def get_member_context(store: RoomStoreDependency) -> MemberContext:
    return SQLiteMemberContext(store)


MemberContextDependency = Annotated[MemberContext, Depends(get_member_context)]
