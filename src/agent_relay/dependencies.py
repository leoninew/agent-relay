import logging
from typing import Annotated, cast

from fastapi import Depends, FastAPI, Request

from agent_relay.config import Settings
from agent_relay.room_service import RoomService
from agent_relay.service import GreetingService


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


def get_room_service(request: Request) -> RoomService:
    return cast(RoomService, request.app.state.room_service)


RoomServiceDependency = Annotated[RoomService, Depends(get_room_service)]
