from contextlib import AbstractContextManager

from conflua.domain.rooms.models import DEFAULT_CHANNEL_ID
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
            lambda session: SQLAlchemyChannelRepository(session, DEFAULT_CHANNEL_ID),
            transaction,
        )

    def guard(self, room_id: str) -> AbstractContextManager[None]:
        return room_operation(self.database.path, room_id)
