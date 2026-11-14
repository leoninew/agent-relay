from typing import Annotated, cast

from fastapi import Depends, Request
from starlette.requests import HTTPConnection

from agent_relay.application.context.ports import ContextQueries
from agent_relay.application.context.queries import ContextReader
from agent_relay.application.context.service import ContextService
from agent_relay.application.rooms.ports import RoomStore
from agent_relay.interfaces.http.dependencies import get_http_dependencies
from agent_relay.interfaces.http.transactions import RequestTransaction


def validate_caller(connection: HTTPConnection, store: RoomStore) -> None:
    session_id = connection.headers.get("X-Agent-Relay-Session-Id")
    room_id = connection.path_params.get("room_id")
    if session_id and room_id:
        store.queries.member_for_session(room_id, session_id)


def get_independent_room_store(connection: HTTPConnection) -> RoomStore:
    store = get_http_dependencies(connection).room_store
    scoped = store.for_channel(connection.path_params["channel_id"])
    validate_caller(connection, scoped)
    return scoped


IndependentRoomStoreDependency = Annotated[RoomStore, Depends(get_independent_room_store)]


def get_room_store(request: Request) -> RoomStore:
    transaction = cast(RequestTransaction, request.state.database_transaction)
    store = get_http_dependencies(request).request_room_store(transaction)
    channel_id = request.path_params.get("channel_id")
    scoped = store.for_channel(channel_id) if channel_id else store
    if channel_id:
        validate_caller(request, scoped)
    return scoped


RoomStoreDependency = Annotated[RoomStore, Depends(get_room_store)]


def get_context_service(connection: HTTPConnection) -> ContextService:
    get_independent_room_store(connection)
    dependencies = get_http_dependencies(connection)
    scope = dependencies.context_for_channel(connection.path_params["channel_id"])
    return ContextService(scope)


ContextServiceDependency = Annotated[ContextService, Depends(get_context_service)]


def get_context_queries(connection: HTTPConnection) -> ContextQueries:
    get_independent_room_store(connection)
    dependencies = get_http_dependencies(connection)
    scope = dependencies.context_for_channel(connection.path_params["channel_id"])
    return ContextReader(scope)


ContextQueriesDependency = Annotated[ContextQueries, Depends(get_context_queries)]
