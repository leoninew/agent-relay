import sqlite3
from collections.abc import Callable


class SQLiteTransaction:
    """A lazy transaction owned by one inbound request."""

    def __init__(self, connect: Callable[[], sqlite3.Connection]) -> None:
        self._connect = connect
        self.connection: sqlite3.Connection | None = None
        self._finished = False

    def begin(self) -> sqlite3.Connection:
        if self._finished:
            raise RuntimeError("Request transaction has already finished")
        if self.connection is None:
            connection = self._connect()
            try:
                connection.execute("BEGIN IMMEDIATE")
            except BaseException:
                connection.close()
                raise
            self.connection = connection
        return self.connection

    def finish(self, *, commit: bool) -> None:
        if self._finished:
            return
        self._finished = True
        connection, self.connection = self.connection, None
        if connection is None:
            return
        try:
            if commit:
                connection.commit()
            else:
                connection.rollback()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()
