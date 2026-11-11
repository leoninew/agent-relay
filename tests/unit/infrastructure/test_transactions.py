from unittest.mock import Mock

import pytest
from sqlalchemy.orm import Session

from agent_relay.infrastructure.persistence.transaction import SQLAlchemyTransaction


def test_transaction_opens_once_and_finishes_once() -> None:
    session = Mock(spec=Session)
    open_session = Mock(return_value=session)
    transaction = SQLAlchemyTransaction(open_session)
    open_session.assert_not_called()
    assert transaction.begin() is transaction.begin() is session
    open_session.assert_called_once_with()
    transaction.finish(commit=True)
    transaction.finish(commit=False)
    session.commit.assert_called_once_with()
    session.rollback.assert_not_called()
    session.close.assert_called_once_with()


def test_failed_commit_rolls_back_and_releases_the_session() -> None:
    session = Mock(spec=Session)
    session.commit.side_effect = RuntimeError("commit failed")
    transaction = SQLAlchemyTransaction(lambda: session)
    transaction.begin()
    with pytest.raises(RuntimeError, match="commit failed"):
        transaction.finish(commit=True)
    session.rollback.assert_called_once_with()
    session.close.assert_called_once_with()
    assert transaction.session is None
