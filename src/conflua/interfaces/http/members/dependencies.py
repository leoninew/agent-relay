from typing import Annotated

from fastapi import Depends
from starlette.requests import HTTPConnection

from conflua.application.members.service import MemberService
from conflua.application.members.sessions import SessionDriver
from conflua.interfaces.http.dependencies import get_http_dependencies
from conflua.interfaces.http.persistence import IndependentRoomStoreDependency, RoomStoreDependency


def get_session_driver(connection: HTTPConnection) -> SessionDriver:
    return get_http_dependencies(connection).session_driver


SessionDriverDependency = Annotated[SessionDriver, Depends(get_session_driver)]


def get_member_service(
    store: IndependentRoomStoreDependency, driver: SessionDriverDependency
) -> MemberService:
    return MemberService(store, driver)


MemberServiceDependency = Annotated[MemberService, Depends(get_member_service)]


def get_member_creation_service(
    store: RoomStoreDependency, driver: SessionDriverDependency
) -> MemberService:
    return MemberService(store, driver)


MemberCreationServiceDependency = Annotated[MemberService, Depends(get_member_creation_service)]
