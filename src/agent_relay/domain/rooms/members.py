from datetime import datetime, timedelta

from agent_relay.domain.rooms.errors import RoomConflictError, RoomInputError, RoomNotFoundError
from agent_relay.domain.rooms.models import Member, RoomState
from agent_relay.domain.rooms.rules import validate_member

OBSERVATION_CHECKPOINT = timedelta(seconds=30)


def observation_cutoff(observed_at: datetime) -> datetime:
    return observed_at - OBSERVATION_CHECKPOINT


def validate_join(state: RoomState, name: str, topic_ids: list[str], session_id: str) -> None:
    validate_member(state, name, topic_ids)
    if any(member.session_id == session_id and not member.deleted_at for member in state.members):
        raise RoomConflictError("该会话已加入聊天室", code="session_already_joined")


def editable_member(state: RoomState, member_id: str, *, deleting: bool = False) -> Member:
    for member in state.members:
        if member.id == member_id and not member.deleted_at:
            if member.kind == "human":
                raise RoomInputError(
                    "不能删除固定用户成员" if deleting else "不能编辑固定用户成员",
                    code="human_member_delete_forbidden"
                    if deleting
                    else "human_member_edit_forbidden",
                )
            return member
    raise RoomNotFoundError("成员不存在", code="member_not_found")


def rename_member(state: RoomState, member_id: str, name: str, topic_ids: list[str]) -> Member:
    member = editable_member(state, member_id)
    validate_member(state, name, topic_ids, member_id)
    member.name = name
    member.initials = name[:2].upper()
    member.topic_ids = list(dict.fromkeys(topic_ids))
    return member


def retire_member(state: RoomState, member_id: str, deleted_at: datetime) -> Member:
    member = editable_member(state, member_id, deleting=True)
    member.deleted_at = deleted_at
    member.topic_ids = []
    return member
