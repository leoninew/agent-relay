from datetime import datetime
from uuid import uuid4

from agent_relay.domain.rooms.errors import RoomConflictError, RoomNotFoundError
from agent_relay.domain.rooms.models import USER_MEMBER_ID, Member, Room, RoomState, Topic

DEFAULT_TOPIC_NAMES = ("产品", "架构", "开发", "测试")


def fixed_user() -> Member:
    return Member(
        id=USER_MEMBER_ID,
        name="你",
        session_id=None,
        kind="human",
        initials="你",
        presence="available",
        activity="",
        activity_source="user",
        topic_ids=[],
    )


def new_room_state(room: Room, created_at: datetime) -> RoomState:
    return RoomState(
        room=room,
        members=[fixed_user()],
        topics=[
            Topic(
                id=f"topic-{uuid4().hex[:12]}",
                name=name,
                description="",
                created_at=created_at,
            )
            for name in DEFAULT_TOPIC_NAMES
        ],
    )


def require_topic(state: RoomState, topic_id: str) -> Topic:
    for topic in state.topics:
        if topic.id == topic_id and not topic.deleted_at:
            return topic
    raise RoomNotFoundError("话题不存在")


def validate_topic_name(state: RoomState, name: str, topic_id: str | None = None) -> None:
    if any(
        topic.id != topic_id and not topic.deleted_at and topic.name == name
        for topic in state.topics
    ):
        raise RoomConflictError("房间中已有同名话题")


def retire_topic(state: RoomState, topic_id: str, deleted_at: datetime) -> Topic:
    topic = require_topic(state, topic_id)
    topic.deleted_at = deleted_at
    for member in state.members:
        member.topic_ids = [candidate for candidate in member.topic_ids if candidate != topic_id]
    return topic
