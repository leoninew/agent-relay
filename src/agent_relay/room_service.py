from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import PurePosixPath, PureWindowsPath
from threading import Lock
from uuid import uuid4

from agent_relay.room_models import (
    CreateMember,
    CreateMessage,
    CreateRoom,
    CreateTopic,
    Delivery,
    Member,
    Message,
    Room,
    RoomSnapshot,
    RoomSummary,
    Session,
    Topic,
    UpdateMember,
)


class RoomNotFoundError(LookupError):
    pass


class RoomInputError(ValueError):
    pass


class RoomConflictError(ValueError):
    pass


@dataclass
class RoomState:
    room: Room
    topics: list[Topic]
    members: list[Member] = field(default_factory=list)
    messages: list[Message] = field(default_factory=list)
    sessions: list[Session] = field(default_factory=list)


class RoomService:
    def __init__(self) -> None:
        self._lock = Lock()
        self._rooms: dict[str, RoomState] = {}
        self._seed_rooms()

    def list_rooms(self) -> list[Room]:
        with self._lock:
            return [state.room.model_copy(deep=True) for state in self._rooms.values()]

    def create_room(self, request: CreateRoom) -> Room:
        with self._lock:
            project_path = self._normalize_project_path(request.project_path)
            if any(state.room.project_path == project_path for state in self._rooms.values()):
                raise RoomConflictError("该项目已有聊天室，请直接打开")
            room = Room(
                id=f"room-{uuid4().hex[:12]}",
                name=request.name,
                project_path=project_path,
                description="",
            )
            self._rooms[room.id] = RoomState(
                room=room,
                topics=[],
                sessions=self._project_sessions(room),
            )
            return room.model_copy(deep=True)

    def add_member(self, room_id: str, request: CreateMember) -> Member:
        with self._lock:
            state = self._get_room(room_id)
            session = next(
                (session for session in state.sessions if session.id == request.session_id), None
            )
            if session is None:
                raise RoomInputError("所选会话不属于当前项目")
            if any(member.session_id == session.id for member in state.members):
                raise RoomConflictError("该会话已加入聊天室")
            self._validate_member(state, request)
            member = Member(
                id=f"member-{uuid4().hex[:12]}",
                session_id=session.id,
                name=request.name,
                role=request.role,
                initials=request.name[:2].upper(),
                presence=session.presence,
                activity="可接收消息",
                topic_ids=list(dict.fromkeys(request.topic_ids)),
            )
            state.members.append(member)
            return member.model_copy(deep=True)

    def update_member(self, room_id: str, member_id: str, request: UpdateMember) -> Member:
        with self._lock:
            state = self._get_room(room_id)
            member = next((member for member in state.members if member.id == member_id), None)
            if member is None:
                raise RoomNotFoundError("成员不存在")
            self._validate_member(state, request, member_id)
            member.name = request.name
            member.role = request.role
            member.initials = request.name[:2].upper()
            member.topic_ids = list(dict.fromkeys(request.topic_ids))
            return member.model_copy(deep=True)

    @staticmethod
    def _validate_member(
        state: RoomState, request: UpdateMember, member_id: str | None = None
    ) -> None:
        if any(member.name == request.name and member.id != member_id for member in state.members):
            raise RoomConflictError("房间中已有同名成员")
        if not set(request.topic_ids) <= {topic.id for topic in state.topics}:
            raise RoomInputError("成员关注的主题不存在")

    def list_available_sessions(self, room_id: str) -> list[Session]:
        with self._lock:
            state = self._get_room(room_id)
            joined = {member.session_id for member in state.members}
            return [
                session.model_copy(deep=True)
                for session in state.sessions
                if session.id not in joined
            ]

    @staticmethod
    def _project_sessions(room: Room) -> list[Session]:
        return [
            Session(
                id=f"{room.id}-session-{index}",
                name=name,
                provider="Codex",
                project_path=room.project_path,
                presence="available",
            )
            for index, name in enumerate(["开发会话", "审查会话", "测试会话"], start=1)
        ]

    def add_topic(self, room_id: str, request: CreateTopic) -> Topic:
        with self._lock:
            state = self._get_room(room_id)
            if any(topic.name == request.name for topic in state.topics):
                raise RoomConflictError("房间中已有同名主题")
            topic = Topic(
                id=f"topic-{uuid4().hex[:12]}",
                name=request.name,
                description=request.description.strip(),
            )
            state.topics.append(topic)
            return topic.model_copy(deep=True)

    def _get_room(self, room_id: str) -> RoomState:
        state = self._rooms.get(room_id)
        if state is None:
            raise RoomNotFoundError("聊天室不存在")
        return state

    @staticmethod
    def _normalize_project_path(value: str) -> str:
        windows_path = PureWindowsPath(value)
        if windows_path.drive:
            if not windows_path.is_absolute():
                raise RoomInputError("请输入项目的绝对路径")
            return windows_path.as_posix().casefold()
        posix_path = PurePosixPath(value)
        if not posix_path.is_absolute():
            raise RoomInputError("请输入项目的绝对路径")
        return posix_path.as_posix()

    def _seed_rooms(self) -> None:
        room = Room(
            id="agent-relay",
            name="Agent Relay 开发室",
            project_path="d:/sourcecodes/mywork/agent-relay",
            description="聊天室界面与消息路由开发",
        )
        topics = [
            Topic(id="summary", name="汇总", description="协作约定、关键决策与跨主题同步"),
            Topic(id="frontend", name="前端", description="聊天室界面、交互与可视化"),
            Topic(id="backend", name="后端", description="接口契约、消息路由与投递"),
        ]
        members = [
            Member(
                id="coordinator",
                session_id="agent-relay-coordinator",
                name="主会话",
                role="协调",
                initials="CO",
                presence="available",
                activity="可接收协作消息",
                topic_ids=["summary", "frontend", "backend"],
            ),
            Member(
                id="frontend-worker",
                session_id="agent-relay-frontend",
                name="前端 Worker",
                role="前端开发",
                initials="FE",
                presence="busy",
                activity="正在处理消息 · 新投递将排队",
                topic_ids=["frontend", "summary"],
            ),
            Member(
                id="backend-worker",
                session_id="agent-relay-backend",
                name="后端 Worker",
                role="后端开发",
                initials="BE",
                presence="available",
                activity="可接收接口与路由讨论",
                topic_ids=["backend", "summary"],
            ),
            Member(
                id="test-worker",
                session_id="agent-relay-test",
                name="测试 Worker",
                role="集成测试",
                initials="QA",
                presence="available",
                activity="同时关注前后端，按需查阅",
                topic_ids=["frontend", "backend", "summary"],
            ),
        ]
        state = RoomState(
            room=room,
            topics=topics,
            members=members,
            sessions=self._project_sessions(room)
            + [
                Session(
                    id=member.session_id,
                    name=member.name,
                    provider="Codex",
                    project_path=room.project_path,
                    presence=member.presence,
                )
                for member in members
            ],
        )
        self._rooms[room.id] = state
        self._seed_messages(state)
        self._rooms["housekeeper"] = RoomState(
            room=Room(
                id="housekeeper",
                name="Housekeeper",
                project_path="d:/sourcecodes/mywork/housekeeper",
                description="CLI 工具开发",
            ),
            topics=[],
        )
        housekeeper = self._rooms["housekeeper"]
        housekeeper.sessions = self._project_sessions(housekeeper.room)

    def snapshot(self, room_id: str, topic_id: str | None = None) -> RoomSnapshot:
        with self._lock:
            state = self._get_room(room_id)
            if topic_id is not None and topic_id not in {topic.id for topic in state.topics}:
                raise RoomNotFoundError("主题不存在")
            deliveries = [delivery for message in state.messages for delivery in message.deliveries]
            return RoomSnapshot(
                room=state.room.model_copy(deep=True),
                topics=[
                    topic.model_copy(
                        update={
                            "message_count": sum(
                                topic.id in message.topic_ids for message in state.messages
                            )
                        },
                        deep=True,
                    )
                    for topic in state.topics
                ],
                members=[member.model_copy(deep=True) for member in state.members],
                messages=[
                    message.model_copy(deep=True)
                    for message in state.messages
                    if topic_id is None or topic_id in message.topic_ids
                ],
                summary=RoomSummary(
                    total_messages=len(state.messages),
                    delivered_count=sum(delivery.status == "delivered" for delivery in deliveries),
                    queued_count=sum(delivery.status == "queued" for delivery in deliveries),
                ),
            )

    def post_message(self, room_id: str, request: CreateMessage) -> Message:
        with self._lock:
            state = self._get_room(room_id)
            topic_ids = list(dict.fromkeys(request.topic_ids))
            mentioned_member_ids = list(dict.fromkeys(request.mentioned_member_ids))
            if request.reply_to_message_id is not None and not any(
                message.id == request.reply_to_message_id for message in state.messages
            ):
                raise RoomInputError("引用的消息不存在")
            message = self._append_message(
                state,
                content=request.content,
                topic_ids=topic_ids,
                mentioned_member_ids=mentioned_member_ids,
                sender_id=None,
                sender_name="控制台",
                created_at=datetime.now(UTC),
                reply_to_message_id=request.reply_to_message_id,
            )
            return message.model_copy(deep=True)

    @staticmethod
    def _resolve_recipient_ids(
        state: RoomState, topic_ids: list[str], mentioned_member_ids: list[str]
    ) -> list[str]:
        topics = set(topic_ids)
        mentions = set(mentioned_member_ids)
        if not topics <= {topic.id for topic in state.topics}:
            raise RoomInputError("消息包含不存在的话题")
        if not mentions <= {member.id for member in state.members}:
            raise RoomInputError("@ 成员不存在")
        recipient_ids = [
            member.id
            for member in state.members
            if member.id in mentions or topics.intersection(member.topic_ids)
        ]
        if not recipient_ids:
            raise RoomInputError("所选话题暂无成员，请选择其他话题或 @ 成员")
        return recipient_ids

    def _append_message(
        self,
        state: RoomState,
        *,
        content: str,
        topic_ids: list[str],
        mentioned_member_ids: list[str],
        sender_id: str | None,
        sender_name: str,
        created_at: datetime,
        reply_to_message_id: str | None = None,
    ) -> Message:
        recipient_ids = self._resolve_recipient_ids(state, topic_ids, mentioned_member_ids)
        seq = len(state.messages) + 1
        message_id = f"{state.room.id}-msg-{seq:04d}"
        members = {member.id: member for member in state.members}
        message = Message(
            id=message_id,
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
                    id=f"{message_id}:{recipient_id}",
                    target_member_id=recipient_id,
                    status="delivered"
                    if members[recipient_id].presence == "available"
                    else "queued",
                    updated_at=created_at,
                )
                for recipient_id in recipient_ids
            ],
        )
        state.messages.append(message)
        return message

    def _seed_messages(self, state: RoomState) -> None:
        started_at = datetime.now(UTC) - timedelta(minutes=18)
        examples = [
            (
                "coordinator",
                ["summary"],
                [],
                "本轮开发聊天室页面与消息接口。界面问题放在前端主题，接口问题放在后端主题，"
                "联调问题同时关联两个主题。",
            ),
            (
                "coordinator",
                [],
                ["frontend-worker"],
                "请把聊天室分成主题导航、讨论时间线和成员面板。"
                "发送时需要能选择多个话题，也要看得到成员的分发状态。",
            ),
            (
                "backend-worker",
                ["backend"],
                [],
                "发消息可以只选话题，也可以只 @ 成员，或两者同时选择。重复匹配的成员只投递一次。",
            ),
            (
                "coordinator",
                ["frontend", "backend"],
                ["test-worker"],
                "请关注前后端的消息契约：同一条跨主题消息即使命中两个订阅，也只能向同一成员投递一次。",
            ),
            (
                "test-worker",
                ["frontend", "backend"],
                [],
                "联调重点：跨主题消息去重、忙碌成员排队，以及发送失败后保留草稿。",
            ),
            (
                "coordinator",
                ["frontend", "backend"],
                ["frontend-worker", "backend-worker", "test-worker"],
                "登录流程的前后端改造已合并，请一起核对提交失败与重试路径。",
            ),
        ]
        members = {member.id: member for member in state.members}
        for index, (sender_id, topic_ids, mentioned_member_ids, content) in enumerate(examples):
            self._append_message(
                state,
                content=content,
                topic_ids=topic_ids,
                mentioned_member_ids=mentioned_member_ids,
                sender_id=sender_id,
                sender_name=members[sender_id].name,
                created_at=started_at + timedelta(minutes=index * 3),
                reply_to_message_id=f"{state.room.id}-msg-0004" if index == 4 else None,
            )
