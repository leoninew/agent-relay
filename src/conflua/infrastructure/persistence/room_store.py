from contextlib import AbstractContextManager

from conflua.application.rooms.queries import RoomReader
from conflua.infrastructure.persistence.channel_guard import room_operation
from conflua.infrastructure.persistence.database import Database
from conflua.infrastructure.persistence.repositories.messages import SQLAlchemyMessageRepository
from conflua.infrastructure.persistence.repositories.rooms import SQLAlchemyRoomRepository
from conflua.infrastructure.persistence.scopes import SQLAlchemyScope
from conflua.infrastructure.persistence.transaction import SQLAlchemyTransaction


class SQLAlchemyRoomData(SQLAlchemyRoomRepository, SQLAlchemyMessageRepository):
    pass


class SQLAlchemyRoomStore(SQLAlchemyScope[SQLAlchemyRoomData]):
    def __init__(
        self,
        database: Database,
        transaction: SQLAlchemyTransaction | None = None,
        *,
        channel_id: str | None = None,
    ) -> None:
        self.database = database
        self.channel_id = channel_id
        super().__init__(
            database, lambda session: SQLAlchemyRoomData(session, channel_id), transaction
        )

    def for_channel(self, channel_id: str) -> "SQLAlchemyRoomStore":
        return SQLAlchemyRoomStore(self.database, self.transaction, channel_id=channel_id)

    def guard(self, room_id: str) -> AbstractContextManager[None]:
        return room_operation(self.database.path, room_id)

    @property
    def queries(self) -> RoomReader:
        return RoomReader(self)
