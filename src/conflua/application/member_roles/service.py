from uuid import uuid4

from conflua.application.dto.member_roles import MemberRole, MemberRoleInput
from conflua.application.member_roles.ports import MemberRoleData, MemberRoleNameConflict
from conflua.application.transactions import RepositoryScope
from conflua.domain.rooms.errors import RoomConflictError, RoomNotFoundError


def _not_found() -> RoomNotFoundError:
    return RoomNotFoundError("角色不存在", code="member_role_not_found")


def _name_conflict() -> RoomConflictError:
    return RoomConflictError("角色名称已存在", code="member_role_name_conflict")


class MemberRoleService:
    def __init__(self, store: RepositoryScope[MemberRoleData]) -> None:
        self.store = store

    def list_roles(self) -> list[MemberRole]:
        with self.store.read() as roles:
            return roles.list_roles()

    def get(self, role_id: str) -> MemberRole:
        with self.store.read() as roles:
            role = roles.get(role_id)
            if role is None:
                raise _not_found()
            return role

    def create(self, request: MemberRoleInput) -> MemberRole:
        role = MemberRole(id=f"role-{uuid4().hex}", name=request.name, prompt=request.prompt)
        with self.store.write() as roles:
            try:
                roles.insert(role)
            except MemberRoleNameConflict as exc:
                raise _name_conflict() from exc
        return role

    def update(self, role_id: str, request: MemberRoleInput) -> MemberRole:
        with self.store.write() as roles:
            try:
                role = roles.update(role_id, request)
            except MemberRoleNameConflict as exc:
                raise _name_conflict() from exc
            if role is None:
                raise _not_found()
            return role

    def delete(self, role_id: str) -> None:
        with self.store.write() as roles:
            if not roles.delete(role_id):
                raise _not_found()
