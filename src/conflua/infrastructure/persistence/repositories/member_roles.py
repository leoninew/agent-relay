from sqlite3 import SQLITE_CONSTRAINT_UNIQUE

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from conflua.application.dto.member_roles import MemberRole, MemberRoleInput
from conflua.application.member_roles.ports import MemberRoleNameConflict
from conflua.infrastructure.persistence.models import MemberRoleRecord


def _role(record: MemberRoleRecord) -> MemberRole:
    return MemberRole(id=record.id, name=record.name, prompt=record.prompt)


class SQLAlchemyMemberRoleRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_roles(self) -> list[MemberRole]:
        records = self.session.scalars(
            select(MemberRoleRecord).order_by(MemberRoleRecord.name, MemberRoleRecord.id)
        )
        return [_role(record) for record in records]

    def get(self, role_id: str) -> MemberRole | None:
        record = self.session.get(MemberRoleRecord, role_id)
        return _role(record) if record is not None else None

    def insert(self, role: MemberRole) -> None:
        self.session.add(MemberRoleRecord(id=role.id, name=role.name, prompt=role.prompt))
        self._flush_role()

    def update(self, role_id: str, request: MemberRoleInput) -> MemberRole | None:
        record = self.session.get(MemberRoleRecord, role_id)
        if record is None:
            return None
        record.name = request.name
        record.prompt = request.prompt
        self._flush_role()
        return _role(record)

    def delete(self, role_id: str) -> bool:
        record = self.session.get(MemberRoleRecord, role_id)
        if record is None:
            return False
        self.session.delete(record)
        self.session.flush()
        return True

    def _flush_role(self) -> None:
        try:
            self.session.flush()
        except IntegrityError as exc:
            if getattr(exc.orig, "sqlite_errorcode", None) == SQLITE_CONSTRAINT_UNIQUE:
                raise MemberRoleNameConflict from exc
            raise
