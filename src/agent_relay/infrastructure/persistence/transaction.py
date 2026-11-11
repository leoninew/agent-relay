from collections.abc import Callable

from sqlalchemy.orm import Session


class SQLAlchemyTransaction:
    """A lazy session owned and finished by one inbound request."""

    def __init__(self, open_session: Callable[[], Session]) -> None:
        self._open_session = open_session
        self.session: Session | None = None
        self._finished = False

    def ensure_open(self) -> None:
        if self._finished:
            raise RuntimeError("Request transaction has already finished")

    def begin(self) -> Session:
        self.ensure_open()
        if self.session is None:
            self.session = self._open_session()
        return self.session

    def finish(self, *, commit: bool) -> None:
        if self._finished:
            return
        self._finished = True
        session, self.session = self.session, None
        if session is None:
            return
        try:
            if commit:
                session.commit()
            else:
                session.rollback()
        except BaseException:
            session.rollback()
            raise
        finally:
            session.close()
