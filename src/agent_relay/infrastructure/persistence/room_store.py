from sqlalchemy.orm import Session

from agent_relay.infrastructure.persistence.database import Database
from agent_relay.infrastructure.persistence.repositories.messages import SQLAlchemyMessageRepository
from agent_relay.infrastructure.persistence.repositories.rooms import SQLAlchemyRoomRepository
from agent_relay.infrastructure.persistence.room_queries import SQLAlchemyRoomQueries
from agent_relay.infrastructure.persistence.scopes import SQLAlchemyScope
from agent_relay.infrastructure.persistence.transaction import SQLAlchemyTransaction


class SQLAlchemyRoomData(SQLAlchemyRoomRepository, SQLAlchemyMessageRepository):
    def __init__(self, session: Session) -> None:
        SQLAlchemyRoomRepository.__init__(self, session)
        SQLAlchemyMessageRepository.__init__(self, session)


class SQLAlchemyRoomStore(SQLAlchemyScope[SQLAlchemyRoomData]):
    def __init__(
        self, database: Database, transaction: SQLAlchemyTransaction | None = None
    ) -> None:
        self.database = database
        super().__init__(database, SQLAlchemyRoomData, transaction)

    @property
    def queries(self) -> SQLAlchemyRoomQueries:
        return SQLAlchemyRoomQueries(self.database, self.transaction)
