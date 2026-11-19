from fastapi import APIRouter

from conflua.application.dto.member_roles import MemberRole, MemberRoleInput
from conflua.interfaces.http.member_roles.dependencies import MemberRoleServiceDependency

router = APIRouter(prefix="/member-role", tags=["member-role"])


@router.get("")
def list_roles(service: MemberRoleServiceDependency) -> list[MemberRole]:
    return service.list_roles()


@router.post("", status_code=201)
def create_role(request: MemberRoleInput, service: MemberRoleServiceDependency) -> MemberRole:
    return service.create(request)


@router.patch("/{role_id}")
def update_role(
    role_id: str, request: MemberRoleInput, service: MemberRoleServiceDependency
) -> MemberRole:
    return service.update(role_id, request)


@router.delete("/{role_id}", status_code=204)
def delete_role(role_id: str, service: MemberRoleServiceDependency) -> None:
    service.delete(role_id)
