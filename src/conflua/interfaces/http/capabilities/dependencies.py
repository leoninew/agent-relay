from typing import Annotated

from fastapi import Depends
from starlette.requests import HTTPConnection

from conflua.application.capabilities.ports import CapabilityDriver
from conflua.application.capabilities.service import CapabilityService
from conflua.interfaces.http.dependencies import get_http_dependencies
from conflua.interfaces.http.persistence import IndependentRoomStoreDependency


def get_capability_driver(connection: HTTPConnection) -> CapabilityDriver:
    return get_http_dependencies(connection).capability_driver


CapabilityDriverDependency = Annotated[CapabilityDriver, Depends(get_capability_driver)]


def get_capability_service(
    store: IndependentRoomStoreDependency, driver: CapabilityDriverDependency
) -> CapabilityService:
    return CapabilityService(store, driver)


CapabilityServiceDependency = Annotated[CapabilityService, Depends(get_capability_service)]
