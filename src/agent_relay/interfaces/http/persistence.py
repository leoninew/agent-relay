from typing import Annotated, cast

from fastapi import Depends, Request
from starlette.requests import HTTPConnection

from agent_relay.application.context.ports import ContextQueries
from agent_relay.application.context.queries import ContextReader
from agent_relay.application.context.service import ContextService
from agent_relay.application.rooms.ports import RoomStore
from agent_relay.interfaces.http.dependencies import get_http_dependencies
from agent_relay.interfaces.http.transactions import RequestTransaction


def get_independent_room_store(connection: HTTPConnection) -> RoomStore:
    return get_http_dependencies(connection).room_store


IndependentRoomStoreDependency = Annotated[RoomStore, Depends(get_independent_room_store)]


def get_room_store(request: Request) -> RoomStore:
    transaction = cast(RequestTransaction, request.state.database_transaction)
    return get_http_dependencies(request).request_room_store(transaction)


RoomStoreDependency = Annotated[RoomStore, Depends(get_room_store)]


def get_context_service(connection: HTTPConnection) -> ContextService:
    return ContextService(get_http_dependencies(connection).context_scope)


ContextServiceDependency = Annotated[ContextService, Depends(get_context_service)]


def get_context_queries(connection: HTTPConnection) -> ContextQueries:
    return ContextReader(get_http_dependencies(connection).context_scope)


ContextQueriesDependency = Annotated[ContextQueries, Depends(get_context_queries)]
