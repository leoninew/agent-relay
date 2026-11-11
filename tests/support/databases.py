from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.engine import URL, Connection, Engine
from sqlalchemy.exc import OperationalError

from agent_relay.infrastructure.persistence.database import Database
from agent_relay.infrastructure.persistence.migrations import run_migrations
from agent_relay.infrastructure.persistence.sqlite import create_sqlite_engine
from support.room_fixtures import RoomTestStore


def assert_reader_is_blocked(database: Database) -> None:
    with database.read() as session:
        connection = session.connection()
        connection.exec_driver_sql("PRAGMA busy_timeout = 0")
        try:
            with pytest.raises(OperationalError, match="database is locked"):
                connection.exec_driver_sql("SELECT count(*) FROM rooms").all()
        finally:
            connection.exec_driver_sql("PRAGMA busy_timeout = 5000")


class MemoryDatabases:
    def __init__(self) -> None:
        self.urls: dict[Path, URL] = {}
        self.engines: list[Engine] = []
        self.keepers: list[Connection] = []

    def engine(self, path: Path) -> Engine:
        key = path.resolve()
        if key not in self.urls:
            url = URL.create(
                "sqlite",
                database=f"file:/{uuid4().hex}",
                query={"vfs": "memdb", "uri": "true"},
            )
            self.urls[key] = url
            keeper = create_sqlite_engine(url)
            self.engines.append(keeper)
            self.keepers.append(keeper.connect())
        engine = create_sqlite_engine(self.urls[key])
        self.engines.append(engine)
        return engine

    def migrate(self, path: Path) -> None:
        with self.engine(path).begin() as connection:
            run_migrations(path, connection=connection)

    def open(self, path: Path) -> Database:
        return Database(path, engine=self.engine(path))

    def create(self, path: Path) -> Database:
        self.migrate(path)
        return self.open(path)

    def store(self, path: Path) -> RoomTestStore:
        return RoomTestStore(self.create(path))

    def open_store(self, path: Path) -> RoomTestStore:
        return RoomTestStore(self.open(path))

    def close(self) -> None:
        for connection in self.keepers:
            connection.close()
        for engine in self.engines:
            engine.dispose()
