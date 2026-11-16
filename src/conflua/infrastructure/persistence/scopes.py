from collections.abc import Callable, Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session

from conflua.infrastructure.persistence.database import Database
from conflua.infrastructure.persistence.transaction import SQLAlchemyTransaction


class SQLAlchemyScope[RepositoryT]:
    def __init__(
        self,
        source: Database | Session,
        factory: Callable[[Session], RepositoryT],
        transaction: SQLAlchemyTransaction | None = None,
    ) -> None:
        if isinstance(source, Session) and transaction is not None:
            raise ValueError("Bind repositories to a session or a request transaction")
        self.source = source
        self.factory = factory
        self.transaction = transaction

    @contextmanager
    def read(self) -> Iterator[RepositoryT]:
        if isinstance(self.source, Session):
            yield self.factory(self.source)
        else:
            with self.source.read(self.transaction) as session:
                yield self.factory(session)

    @contextmanager
    def write(self) -> Iterator[RepositoryT]:
        if isinstance(self.source, Session):
            yield self.factory(self.source)
        else:
            with self.source.write(self.transaction) as session:
                yield self.factory(session)
