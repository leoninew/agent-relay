import logging
from typing import Annotated, cast

from fastapi import Depends, FastAPI, Request

from agent_relay.config import Settings
from agent_relay.member_context import MemberContext
from agent_relay.member_sessions import MemberSessions
from agent_relay.room_queries import RoomQueries
from agent_relay.room_service import RoomService
from agent_relay.room_store import SQLiteRoomStore
from agent_relay.service import GreetingService
from agent_relay.sqlite_transaction import SQLiteTransaction


def get_settings(request: Request) -> Settings:
    return application_settings(request.app)


def get_logger(request: Request) -> logging.Logger:
    return cast(logging.Logger, request.app.state.logger)


def application_settings(app: FastAPI) -> Settings:
    return cast(Settings, app.state.settings)


SettingsDependency = Annotated[Settings, Depends(get_settings)]


def get_greeting_service(settings: SettingsDependency) -> GreetingService:
    return GreetingService(settings.greeting.prefix)


GreetingServiceDependency = Annotated[GreetingService, Depends(get_greeting_service)]


def get_room_store(request: Request) -> SQLiteRoomStore:
    root = cast(RoomService, request.app.state.room_service).store
    transaction = cast(SQLiteTransaction, request.state.database_transaction)
    return root.for_request(transaction)


RoomStoreDependency = Annotated[SQLiteRoomStore, Depends(get_room_store)]


def get_room_service(store: RoomStoreDependency) -> RoomService:
    return RoomService(store)


RoomServiceDependency = Annotated[RoomService, Depends(get_room_service)]


def get_room_queries(store: RoomStoreDependency) -> RoomQueries:
    return RoomQueries(store)


RoomQueriesDependency = Annotated[RoomQueries, Depends(get_room_queries)]


def get_member_sessions(request: Request, store: RoomStoreDependency) -> MemberSessions:
    root = cast(MemberSessions, request.app.state.member_sessions)
    return MemberSessions(store, root.driver)


MemberSessionsDependency = Annotated[MemberSessions, Depends(get_member_sessions)]


def get_member_context(store: RoomStoreDependency) -> MemberContext:
    return MemberContext(store)


MemberContextDependency = Annotated[MemberContext, Depends(get_member_context)]
