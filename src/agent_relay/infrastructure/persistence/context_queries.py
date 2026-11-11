from sqlalchemy.orm import Session

from agent_relay.application.context.contracts import MemberCatalog
from agent_relay.application.rooms.views import TopicPosition
from agent_relay.infrastructure.persistence.database import Database
from agent_relay.infrastructure.persistence.repositories.context import SQLAlchemyContextRepository
from agent_relay.infrastructure.persistence.scopes import SQLAlchemyScope


class SQLAlchemyContextQueries:
    def __init__(self, source: Database | Session) -> None:
        self.repositories = SQLAlchemyScope(source, SQLAlchemyContextRepository)

    def catalog(self, room_id: str, member_id: str) -> MemberCatalog:
        with self.repositories.read() as repository:
            return repository.catalog(room_id, member_id)

    def positions(self, room_id: str, member_id: str) -> list[TopicPosition]:
        with self.repositories.read() as repository:
            repository.subscriptions(room_id, member_id)
            return repository.load_positions(room_id, member_id)
