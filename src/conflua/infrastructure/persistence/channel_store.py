from contextlib import AbstractContextManager

from conflua.infrastructure.persistence.channel_guard import room_operation
from conflua.infrastructure.persistence.database import Database
from conflua.infrastructure.persistence.repositories.channels import SQLAlchemyChannelRepository
from conflua.infrastructure.persistence.scopes import SQLAlchemyScope
from conflua.infrastructure.persistence.transaction import SQLAlchemyTransaction


class SQLAlchemyChannelStore(SQLAlchemyScope[SQLAlchemyChannelRepository]):
    def __init__(
        self, database: Database, transaction: SQLAlchemyTransaction | None = None
    ) -> None:
        self.database = database
        super().__init__(
            database,
            SQLAlchemyChannelRepository,
            transaction,
        )

    def guard(self, room_id: str) -> AbstractContextManager[None]:
        return room_operation(self.database.path, room_id)
