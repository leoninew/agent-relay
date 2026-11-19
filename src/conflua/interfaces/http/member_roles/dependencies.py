from typing import Annotated, cast

from fastapi import Depends, Request

from conflua.application.member_roles.service import MemberRoleService
from conflua.interfaces.http.dependencies import get_http_dependencies
from conflua.interfaces.http.transactions import RequestTransaction


def get_member_role_service(request: Request) -> MemberRoleService:
    transaction = cast(RequestTransaction, request.state.database_transaction)
    return get_http_dependencies(request).request_member_role_service(transaction)


MemberRoleServiceDependency = Annotated[MemberRoleService, Depends(get_member_role_service)]
