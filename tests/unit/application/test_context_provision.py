from datetime import UTC, datetime
from unittest.mock import MagicMock, Mock

import pytest

from agent_relay.application.context.ports import ContextRepository
from agent_relay.application.context.service import ContextService
from agent_relay.application.dto.context import ContextMessage, ContextQuery
from agent_relay.application.transactions import RepositoryScope
from agent_relay.domain.rooms.errors import RoomNotFoundError
from agent_relay.domain.rooms.models import VisibilityScope


@pytest.fixture
def repository() -> Mock:
    repository = Mock(spec=ContextRepository)
    repository.subscriptions.return_value = {"frontend", "backend"}
    repository.select_messages.return_value = ([], False)
    repository.load_positions.return_value = []
    return repository


@pytest.fixture
def scope(repository: Mock) -> MagicMock:
    scope = MagicMock(spec=RepositoryScope)
    scope.write.return_value.__enter__.return_value = repository
    return scope


def message(seq: int) -> ContextMessage:
    return ContextMessage(
        id=f"message-{seq}",
        seq=seq,
        sender_id="sender",
        sender_name="Sender",
        content="Context",
        topic_ids=["frontend"],
        mentioned_member_ids=[],
        reply_to_message_id=None,
        created_at=datetime.now(UTC),
    )


@pytest.mark.parametrize("forward", [False, True])
def test_provision_records_returned_messages_and_builds_the_requested_cursor(
    forward: bool, repository: Mock, scope: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    messages = [message(3), message(7)]
    repository.select_messages.return_value = (messages, True)
    updates = {"frontend": 7}
    position_updates = Mock(return_value=updates)
    monkeypatch.setattr(
        "agent_relay.application.context.service.position_updates", position_updates
    )
    request = ContextQuery(after_seq=0) if forward else ContextQuery()
    before = datetime.now(UTC)

    result = ContextService(scope).provide("room", "member", request)

    repository.select_messages.assert_called_once_with(
        "room", request, VisibilityScope.for_member("member", {"frontend", "backend"})
    )
    position_updates.assert_called_once()
    subscriptions, topic_id, position_messages = position_updates.call_args.args
    assert subscriptions == {"frontend", "backend"} and topic_id is None
    assert list(position_messages) == [(3, ["frontend"]), (7, ["frontend"])]
    repository.record_provision.assert_called_once()
    room_id, member_id, recorded_request, recorded, positions, query_id, provided_at = (
        repository.record_provision.call_args.args
    )
    assert (room_id, member_id, recorded_request, recorded) == ("room", "member", request, messages)
    assert query_id == result.query_id and query_id is not None
    assert positions is updates and before <= provided_at <= datetime.now(UTC)
    assert result.messages == messages and result.has_more
    assert result.next_before_seq == (None if forward else 3)
    assert result.next_after_seq == (7 if forward else None)
    scope.write.return_value.__exit__.assert_called_once_with(None, None, None)


def test_empty_provision_does_not_create_audit_or_positions(
    repository: Mock, scope: MagicMock
) -> None:
    result = ContextService(scope).provide("room", "member", ContextQuery())

    assert result.query_id is None and result.messages == []
    assert result.next_before_seq is None and result.next_after_seq is None
    repository.record_provision.assert_not_called()


def test_rejected_topic_stops_before_message_selection(
    repository: Mock, scope: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    validation = Mock(side_effect=RoomNotFoundError("未订阅"))
    monkeypatch.setattr(
        "agent_relay.application.context.service.require_subscribed_topic", validation
    )

    with pytest.raises(RoomNotFoundError):
        ContextService(scope).provide("room", "member", ContextQuery(topic_id="private"))

    validation.assert_called_once_with("private", {"frontend", "backend"})
    repository.select_messages.assert_not_called()
    repository.record_provision.assert_not_called()
