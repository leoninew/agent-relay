from typing import Annotated, cast

from fastapi import Depends
from starlette.requests import HTTPConnection

from agent_relay.application.capabilities.ports import CapabilityDriver
from agent_relay.application.capabilities.service import CapabilityService
from agent_relay.infrastructure.persistence.room_store import SQLAlchemyRoomStore
from agent_relay.interfaces.http.persistence import DatabaseDependency


def get_capability_driver(connection: HTTPConnection) -> CapabilityDriver:
    return cast(CapabilityDriver, connection.app.state.capability_driver)


CapabilityDriverDependency = Annotated[CapabilityDriver, Depends(get_capability_driver)]


def get_capability_service(
    database: DatabaseDependency, driver: CapabilityDriverDependency
) -> CapabilityService:
    return CapabilityService(SQLAlchemyRoomStore(database), driver)


CapabilityServiceDependency = Annotated[CapabilityService, Depends(get_capability_service)]
