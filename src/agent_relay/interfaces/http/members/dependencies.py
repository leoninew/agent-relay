from typing import Annotated, cast

from fastapi import Depends
from starlette.requests import HTTPConnection

from agent_relay.application.members.service import MemberService
from agent_relay.application.members.sessions import SessionDriver
from agent_relay.infrastructure.persistence.room_store import SQLAlchemyRoomStore
from agent_relay.interfaces.http.persistence import DatabaseDependency


def get_session_driver(connection: HTTPConnection) -> SessionDriver:
    return cast(SessionDriver, connection.app.state.session_driver)


SessionDriverDependency = Annotated[SessionDriver, Depends(get_session_driver)]


def get_member_service(
    database: DatabaseDependency, driver: SessionDriverDependency
) -> MemberService:
    return MemberService(SQLAlchemyRoomStore(database), driver)


MemberServiceDependency = Annotated[MemberService, Depends(get_member_service)]
