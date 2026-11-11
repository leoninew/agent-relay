from agent_relay.application.members.context import ContextQuery, ContextResult, MemberCatalog
from agent_relay.domain.rooms.models import TopicPosition
from agent_relay.infrastructure.persistence.database import Database
from agent_relay.infrastructure.persistence.repositories.context import SQLAlchemyContextRepository


class SQLAlchemyMemberContext:
    def __init__(self, database: Database) -> None:
        self.database = database

    def catalog(self, room_id: str, member_id: str) -> MemberCatalog:
        with self.database.read() as session:
            return SQLAlchemyContextRepository(session).catalog(room_id, member_id)

    def positions(self, room_id: str, member_id: str) -> list[TopicPosition]:
        with self.database.read() as session:
            return SQLAlchemyContextRepository(session).positions(room_id, member_id)

    def query(self, room_id: str, member_id: str, request: ContextQuery) -> ContextResult:
        with self.database.write() as session:
            return SQLAlchemyContextRepository(session).query(room_id, member_id, request)
