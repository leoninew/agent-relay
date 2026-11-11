from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Text, column, select, table
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from agent_relay.infrastructure.persistence.migrations import MIGRATION_HEAD
from agent_relay.infrastructure.persistence.sqlite import create_sqlite_engine
from agent_relay.infrastructure.persistence.transaction import SQLAlchemyTransaction


class Database:
    """Own the process engine and lend serial, explicitly bounded sessions."""

    def __init__(self, path: Path, *, engine: Engine | None = None) -> None:
        self.path = path.expanduser().resolve()
        if engine is None and not self.path.is_file():
            raise RuntimeError("Room database is missing; run `python -m agent_relay.migrate`")
        self.engine = engine if engine is not None else create_sqlite_engine(self.path)
        self._sessions = sessionmaker(
            self.engine, autoflush=False, expire_on_commit=False, autobegin=False
        )
        try:
            self._check_revision()
        except BaseException:
            self.close()
            raise

    def _check_revision(self) -> None:
        version = table("alembic_version", column("version_num", Text))
        try:
            with self.read() as session:
                revisions = list(session.scalars(select(version.c.version_num)))
        except SQLAlchemyError as exc:
            raise RuntimeError(
                "Room database is not migrated; run `python -m agent_relay.migrate`"
            ) from exc
        if revisions != [MIGRATION_HEAD]:
            raise RuntimeError(
                f"Room database revisions are {revisions!r}; expected {MIGRATION_HEAD!r}. "
                "Run `python -m agent_relay.migrate`"
            )

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
