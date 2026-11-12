from typing import Annotated

from fastapi import Depends
from starlette.requests import HTTPConnection

from agent_relay.application.members.service import MemberService
from agent_relay.application.members.sessions import SessionDriver
from agent_relay.interfaces.http.dependencies import get_http_dependencies
from agent_relay.interfaces.http.persistence import IndependentRoomStoreDependency


def get_session_driver(connection: HTTPConnection) -> SessionDriver:
    return get_http_dependencies(connection).session_driver


SessionDriverDependency = Annotated[SessionDriver, Depends(get_session_driver)]


def get_member_service(
    store: IndependentRoomStoreDependency, driver: SessionDriverDependency
) -> MemberService:
    return MemberService(store, driver)


MemberServiceDependency = Annotated[MemberService, Depends(get_member_service)]
