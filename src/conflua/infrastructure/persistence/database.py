from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from conflua.infrastructure.persistence.migrations import check_database_revision
from conflua.infrastructure.persistence.sqlite import create_sqlite_engine
from conflua.infrastructure.persistence.transaction import SQLAlchemyTransaction


class Database:
    """Own the process engine and lend serial, explicitly bounded sessions."""

    def __init__(self, path: Path, *, engine: Engine | None = None) -> None:
        self.path = path.expanduser().resolve()
        if engine is None and not self.path.is_file():
            raise RuntimeError("Room database is missing; run `python -m conflua.migrate`")
        self.engine = engine if engine is not None else create_sqlite_engine(self.path)
        self._sessions = sessionmaker(
            self.engine, autoflush=False, expire_on_commit=False, autobegin=False
        )
        try:
            with self.read() as session:
                check_database_revision(session.connection())
        except BaseException:
            self.close()
            raise

    def _open_session(self, *, write: bool) -> Session:
        session = self._sessions()
        try:
            session.begin()
            session.connection(
                execution_options={"sqlite_transaction_mode": "IMMEDIATE" if write else "DEFERRED"}
            )
        except BaseException:
            session.close()
            raise
        return session

    def request_transaction(self) -> SQLAlchemyTransaction:
        return SQLAlchemyTransaction(lambda: self._open_session(write=True))

    @contextmanager
    def read(self, transaction: SQLAlchemyTransaction | None = None) -> Iterator[Session]:
        if transaction is not None:
            transaction.ensure_open()
            if transaction.session is not None:
                yield transaction.session
                return
        session = self._open_session(write=False)
        try:
            yield session
        finally:
            session.close()

    @contextmanager
    def write(self, transaction: SQLAlchemyTransaction | None = None) -> Iterator[Session]:
        if transaction is not None:
            yield transaction.begin()
            return
        session = self._open_session(write=True)
        try:
            yield session
            session.commit()
        except BaseException:
            session.rollback()
            raise
        finally:
            session.close()

    def close(self) -> None:
        self.engine.dispose()
