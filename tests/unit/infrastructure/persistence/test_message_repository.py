from unittest.mock import Mock

import pytest
from sqlalchemy import Select
from sqlalchemy.dialects import sqlite
from sqlalchemy.orm import Session

from agent_relay.domain.rooms.errors import RoomNotFoundError
from agent_relay.infrastructure.persistence.repositories.messages import SQLAlchemyMessageRepository


@pytest.mark.parametrize("read", ["message", "page", "queue", "message_exists"])
def test_message_reads_exclude_cleared_history(read: str) -> None:
    session = Mock(spec=Session)
    session.execute.return_value.tuples.return_value.all.return_value = []
    session.scalar.return_value = None
    repository = SQLAlchemyMessageRepository(session)

    if read == "message":
        with pytest.raises(RoomNotFoundError):
            repository.message("room", "cleared-message")
    elif read == "page":
        assert repository.page("room").messages == []
    elif read == "queue":
        assert repository.queue("room").messages == []
    else:
        assert not repository.message_exists("room", "cleared-message")

    calls = session.execute.call_args_list + session.scalar.call_args_list
    for query_call in calls:
        statement = query_call.args[0]
        assert isinstance(statement, Select)
        assert "messages.deleted_at IS NULL" in str(statement.compile(dialect=sqlite.dialect()))


def test_message_sequence_and_publication_identity_include_cleared_history() -> None:
    session = Mock(spec=Session)
    session.scalar.return_value = 164
    repository = SQLAlchemyMessageRepository(session)

    assert repository.next_message_seq("room") == 164
    sequence_sql = str(session.scalar.call_args.args[0].compile(dialect=sqlite.dialect()))
    assert "max(messages.seq)" in sequence_sql and "deleted_at IS NULL" not in sequence_sql

    session.execute.return_value.tuples.return_value.all.return_value = []
    assert repository.publication("room", "user", "cleared-publication") is None
    statement = session.execute.call_args.args[0].compile(dialect=sqlite.dialect())
    assert "deleted_at IS NULL" not in str(statement)
    assert "cleared-publication" in statement.params.values()
