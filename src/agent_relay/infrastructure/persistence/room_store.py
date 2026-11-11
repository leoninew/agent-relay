from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session

from agent_relay.infrastructure.persistence.database import Database
from agent_relay.infrastructure.persistence.repositories.messages import SQLAlchemyMessageRepository
from agent_relay.infrastructure.persistence.repositories.rooms import SQLAlchemyRoomRepository
from agent_relay.infrastructure.persistence.room_queries import SQLAlchemyRoomQueries
from agent_relay.infrastructure.persistence.transaction import SQLAlchemyTransaction


class SQLAlchemyRoomData(SQLAlchemyRoomRepository, SQLAlchemyMessageRepository):
    def __init__(self, session: Session) -> None:
        SQLAlchemyRoomRepository.__init__(self, session)
        SQLAlchemyMessageRepository.__init__(self, session)


class SQLAlchemyRoomStore:
    def __init__(
        self, database: Database, transaction: SQLAlchemyTransaction | None = None
    ) -> None:
        self.database = database
        self.transaction = transaction

    @property
    def queries(self) -> SQLAlchemyRoomQueries:
        return SQLAlchemyRoomQueries(self.database, self.transaction)

    @contextmanager
    def read_rooms(self) -> Iterator[SQLAlchemyRoomData]:
        with self.database.read(self.transaction) as session:
            yield SQLAlchemyRoomData(session)

    @contextmanager
    def write_rooms(self) -> Iterator[SQLAlchemyRoomData]:
        with self.database.write(self.transaction) as session:
            yield SQLAlchemyRoomData(session)
