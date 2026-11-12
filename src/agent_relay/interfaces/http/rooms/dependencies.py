from typing import Annotated

from fastapi import Depends
from starlette.requests import HTTPConnection

from agent_relay.application.delivery.ports import QueueDriver
from agent_relay.application.messages.service import MessageService
from agent_relay.application.rooms.ports import RoomQueries
from agent_relay.application.rooms.service import RoomService
from agent_relay.interfaces.http.dependencies import get_http_dependencies
from agent_relay.interfaces.http.persistence import (
    IndependentRoomStoreDependency,
    RoomStoreDependency,
)


def get_room_service(store: RoomStoreDependency) -> RoomService:
    return RoomService(store)


RoomServiceDependency = Annotated[RoomService, Depends(get_room_service)]


def get_room_clear_service(store: IndependentRoomStoreDependency) -> RoomService:
    return RoomService(store)


RoomClearServiceDependency = Annotated[RoomService, Depends(get_room_clear_service)]


def get_message_service(store: RoomStoreDependency) -> MessageService:
    return MessageService(store)


MessageServiceDependency = Annotated[MessageService, Depends(get_message_service)]


def get_queue_clear_service(store: IndependentRoomStoreDependency) -> MessageService:
    return MessageService(store)


QueueClearServiceDependency = Annotated[MessageService, Depends(get_queue_clear_service)]


def get_queue_driver(connection: HTTPConnection) -> QueueDriver:
    return get_http_dependencies(connection).queue_driver


QueueDriverDependency = Annotated[QueueDriver, Depends(get_queue_driver)]


def get_room_queries(store: RoomStoreDependency) -> RoomQueries:
    return store.queries


RoomQueriesDependency = Annotated[RoomQueries, Depends(get_room_queries)]


def get_event_queries(store: IndependentRoomStoreDependency) -> RoomQueries:
    return store.queries


EventQueriesDependency = Annotated[RoomQueries, Depends(get_event_queries)]
