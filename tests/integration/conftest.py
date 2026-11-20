from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.engine import URL, Engine

from conflua.infrastructure.persistence.database import Database
from conflua.infrastructure.persistence.models import Base
from conflua.infrastructure.persistence.sqlite import create_sqlite_engine


def _database(path: Path, engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[Database]:
    try:
        Base.metadata.create_all(engine)
        with monkeypatch.context() as patch:
            patch.setattr(
                "conflua.infrastructure.persistence.database.check_database_revision",
                lambda _: None,
            )
            active = Database(path, engine=engine)
        yield active
    finally:
        engine.dispose()


@pytest.fixture
def database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Database]:
    path = tmp_path / "integration.sqlite3"
    url = URL.create(
        "sqlite", database=f"file:/conflua-{uuid4().hex}", query={"vfs": "memdb", "uri": "true"}
    )
    yield from _database(path, create_sqlite_engine(url), monkeypatch)


@pytest.fixture
def file_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Database]:
    path = tmp_path / "integration.sqlite3"
    yield from _database(path, create_sqlite_engine(path), monkeypatch)
