from agent_relay.application.rooms.queries import RoomReader
from agent_relay.infrastructure.persistence.database import Database
from agent_relay.infrastructure.persistence.repositories.messages import SQLAlchemyMessageRepository
from agent_relay.infrastructure.persistence.repositories.rooms import SQLAlchemyRoomRepository
from agent_relay.infrastructure.persistence.scopes import SQLAlchemyScope
from agent_relay.infrastructure.persistence.transaction import SQLAlchemyTransaction


class SQLAlchemyRoomData(SQLAlchemyRoomRepository, SQLAlchemyMessageRepository):
    pass


class SQLAlchemyRoomStore(SQLAlchemyScope[SQLAlchemyRoomData]):
    def __init__(
        self, database: Database, transaction: SQLAlchemyTransaction | None = None
    ) -> None:
        self.database = database
        super().__init__(database, SQLAlchemyRoomData, transaction)

    @property
    def queries(self) -> RoomReader:
        return RoomReader(self)
