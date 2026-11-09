import pytest

from agent_relay.domain.rooms.errors import RoomNotFoundError
from agent_relay.domain.rooms.positions import position_updates, require_subscribed_topic


def test_positions_use_returned_message_sequences_and_current_subscriptions() -> None:
    messages = [(9, ["frontend", "backend"]), (4, ["frontend"]), (12, ["other"])]
    assert position_updates({"frontend", "backend"}, None, messages) == {
        "frontend": 9,
        "backend": 9,
    }
    assert position_updates({"frontend", "backend"}, "frontend", messages) == {"frontend": 9}
    assert position_updates(set(), None, messages) == {}


def test_direct_messages_do_not_grant_a_topic_subscription() -> None:
    with pytest.raises(RoomNotFoundError, match="未订阅"):
        require_subscribed_topic("backend", {"frontend"})
