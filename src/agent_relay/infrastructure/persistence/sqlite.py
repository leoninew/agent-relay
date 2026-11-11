from datetime import datetime
from pathlib import Path
from typing import Literal, Protocol

from sqlalchemy import Integer, SQLColumnExpression, create_engine, event, func, literal_column
from sqlalchemy.engine import URL, Connection, Engine
from sqlalchemy.pool import ConnectionPoolEntry
from sqlalchemy.sql.elements import ColumnElement


class _Cursor(Protocol):
    def execute(self, statement: str) -> object: ...
    def close(self) -> None: ...


class _Connection(Protocol):
    isolation_level: str | None

    def cursor(self) -> _Cursor: ...


def _configure_connection(connection: _Connection, record: ConnectionPoolEntry) -> None:
    connection.isolation_level = None
    cursor = connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA busy_timeout = 5000")
    finally:
        cursor.close()


def _begin(connection: Connection) -> None:
    mode = connection.get_execution_options().get("sqlite_transaction_mode", "DEFERRED")
    if mode not in {"DEFERRED", "IMMEDIATE"}:
        raise ValueError(f"Unsupported SQLite transaction mode: {mode!r}")
    connection.exec_driver_sql("BEGIN IMMEDIATE" if mode == "IMMEDIATE" else "BEGIN")


def create_sqlite_engine(path: Path | URL) -> Engine:
    engine = create_engine(
        path if isinstance(path, URL) else URL.create("sqlite", database=str(path)),
        connect_args={"timeout": 5.0, "check_same_thread": False},
    )
    event.listen(engine, "connect", _configure_connection)
    event.listen(engine, "begin", _begin)
    return engine


def insertion_order(
    table: Literal["rooms", "topics", "sessions", "members", "messages", "deliveries"],
) -> ColumnElement[int]:
    if table not in {"rooms", "topics", "sessions", "members", "messages", "deliveries"}:
        raise ValueError(f"Unsupported insertion-order table: {table!r}")
    return literal_column(f"{table}.rowid", Integer)


def literal_contains(value: ColumnElement[str], keyword: str) -> ColumnElement[bool]:
    return func.instr(value, keyword) > 0


def time_at_or_before(
    value: SQLColumnExpression[datetime | None], cutoff: datetime
) -> ColumnElement[bool]:
    return func.julianday(value) <= func.julianday(cutoff.isoformat())
