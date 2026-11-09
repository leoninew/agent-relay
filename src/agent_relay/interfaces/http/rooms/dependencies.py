from typing import Annotated

from fastapi import Depends

from agent_relay.application.rooms.ports import RoomQueries
from agent_relay.application.rooms.service import RoomService
from agent_relay.interfaces.http.persistence import DatabaseDependency, RoomStoreDependency


def get_room_service(store: RoomStoreDependency) -> RoomService:
    return RoomService(store)


RoomServiceDependency = Annotated[RoomService, Depends(get_room_service)]


def get_room_queries(store: RoomStoreDependency) -> RoomQueries:
    return store.queries


RoomQueriesDependency = Annotated[RoomQueries, Depends(get_room_queries)]


def get_event_queries(database: DatabaseDependency) -> RoomQueries:
    return database.queries


EventQueriesDependency = Annotated[RoomQueries, Depends(get_event_queries)]
