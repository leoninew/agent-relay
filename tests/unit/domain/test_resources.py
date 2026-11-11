from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from support.fakes.rooms import sample_room

from agent_relay.domain.rooms.errors import RoomConflictError, RoomInputError
from agent_relay.domain.rooms.members import rename_member, retire_member
from agent_relay.domain.rooms.models import Member
from agent_relay.domain.rooms.resources import (
    DEFAULT_TOPIC_NAMES,
    new_room_state,
    retire_topic,
    validate_topic_name,
)


def test_initial_resources_are_a_business_value_with_a_fixed_human() -> None:
    room = sample_room().room
    now = datetime.now(UTC)
    state = new_room_state(room, now)
    assert [topic.name for topic in state.topics] == list(DEFAULT_TOPIC_NAMES)
    assert all(topic.created_at == now for topic in state.topics)
    assert len(state.members) == 1
    assert state.members[0].id == "user"
    assert state.members[0].kind == "human"
    assert state.members[0].session_id is None


def test_retiring_a_topic_removes_subscriptions_and_allows_reusing_its_name() -> None:
    state = sample_room()
    topic = state.topics[0]
    with pytest.raises(RoomConflictError):
        validate_topic_name(state, topic.name)
    validate_topic_name(state, topic.name, topic.id)
    now = datetime.now(UTC)
    retired = retire_topic(state, topic.id, now)
    assert retired.deleted_at == now
    assert all(topic.id not in member.topic_ids for member in state.members)
    validate_topic_name(state, topic.name)


def test_fixed_user_cannot_be_bound_renamed_or_retired() -> None:
    state = sample_room()
    user = next(member for member in state.members if member.id == "user")
    with pytest.raises(ValidationError, match="Human members cannot bind"):
        Member.model_validate({**user.model_dump(), "session_id": "session"})
    with pytest.raises(RoomInputError):
        rename_member(state, "user", "Changed", [])
    with pytest.raises(RoomInputError):
        retire_member(state, "user", datetime.now(UTC))
