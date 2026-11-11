from datetime import datetime
from pathlib import PurePosixPath, PureWindowsPath
from uuid import uuid4

from agent_relay.domain.rooms.errors import RoomConflictError, RoomInputError
from agent_relay.domain.rooms.models import USER_MEMBER_ID, Delivery, Member, Message
from agent_relay.domain.rooms.state import RoomState


def normalize_project_path(value: str) -> str:
    windows_path = PureWindowsPath(value)
    if windows_path.drive:
        if not windows_path.is_absolute():
            raise RoomInputError("请输入项目的绝对路径")
        return windows_path.as_posix().casefold()
    posix_path = PurePosixPath(value)
    if not posix_path.is_absolute():
        raise RoomInputError("请输入项目的绝对路径")
    return posix_path.as_posix()


def validate_member(
    state: RoomState, name: str, topic_ids: list[str], member_id: str | None = None
) -> None:
    if any(
        not member.deleted_at and member.name == name and member.id != member_id
        for member in state.members
    ):
        raise RoomConflictError("房间中已有同名成员")
    if not set(topic_ids) <= {topic.id for topic in state.topics if not topic.deleted_at}:
        raise RoomInputError("成员订阅的话题不存在")


def resolve_recipient_ids(
    state: RoomState,
    topic_ids: list[str],
    mentioned_member_ids: list[str],
    *,
    sender_id: str,
) -> list[str]:
    topics = set(topic_ids)
    mentions = set(mentioned_member_ids)
    if not topics <= {topic.id for topic in state.topics if not topic.deleted_at}:
        raise RoomInputError("消息包含不存在的话题")
    if not mentions <= {member.id for member in state.members if not member.deleted_at}:
        raise RoomInputError("@ 成员不存在")
    recipients = [
        member.id
        for member in state.members
        if not member.deleted_at
        and member.id != sender_id
        and (member.id in mentions or topics.intersection(member.topic_ids))
    ]
    if not recipients:
        if sender_id != USER_MEMBER_ID:
            raise RoomInputError("排除发布成员后没有实际接收人，请选择其他话题或 @ 其他成员")
        raise RoomInputError("所选话题暂无成员，请选择其他话题或 @ 成员")
    return recipients


def validate_sender_targets(sender: Member, mentioned_member_ids: list[str]) -> None:
    if sender.kind == "human" and USER_MEMBER_ID in mentioned_member_ids:
        raise RoomInputError("不能将消息发送给自己")


def validate_publication_replay(
    existing: Message,
    *,
    content: str,
    topic_ids: list[str],
    mentions: list[str],
    reply_to_message_id: str | None,
) -> None:
    if (
        existing.content != content
        or set(existing.topic_ids) != set(topic_ids)
        or set(existing.mentioned_member_ids) != set(mentions)
        or existing.reply_to_message_id != reply_to_message_id
    ):
        raise RoomConflictError("发布编号已用于另一条消息")


def build_message(
    state: RoomState,
    *,
    content: str,
    topic_ids: list[str],
    mentioned_member_ids: list[str],
    sender_id: str,
    sender_name: str,
    created_at: datetime,
    seq: int,
    reply_to_message_id: str | None = None,
    publication_id: str | None = None,
) -> Message:
    recipient_ids = resolve_recipient_ids(
        state, topic_ids, mentioned_member_ids, sender_id=sender_id
    )
    message_id = f"{state.room.id}-msg-{seq:04d}"
    return Message(
        id=message_id,
        publication_id=publication_id,
        seq=seq,
        sender_id=sender_id,
        sender_name=sender_name,
        content=content,
        topic_ids=topic_ids,
        mentioned_member_ids=mentioned_member_ids,
        recipient_ids=recipient_ids,
        reply_to_message_id=reply_to_message_id,
        created_at=created_at,
        deliveries=[
            Delivery(
                id=f"{message_id}:{member.id}",
                target_member_id=member.id,
                target_session_id=member.session_id,
                client_message_id=str(uuid4()),
                status="pending",
                updated_at=created_at,
            )
            for recipient_id in recipient_ids
            for member in state.members
            if member.id == recipient_id
            and member.kind == "agent"
            and member.session_id is not None
        ],
    )
