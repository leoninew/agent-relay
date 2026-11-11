"""Explicit demo data for room tests; never loaded by the application."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from agent_relay.application.members.service import MemberSessions
from agent_relay.application.rooms.service import RoomService
from agent_relay.domain.rooms.models import Member, Message, Room, Session, Topic
from agent_relay.domain.rooms.rules import build_message
from agent_relay.domain.rooms.state import RoomState
from agent_relay.infrastructure.persistence.database import Database
from agent_relay.infrastructure.persistence.delivery_store import SQLAlchemyDeliveryStore
from agent_relay.infrastructure.persistence.migrations import run_migrations
from agent_relay.infrastructure.persistence.room_store import SQLAlchemyRoomStore


class RoomTestStore(SQLAlchemyRoomStore, SQLAlchemyDeliveryStore):
    @property
    def path(self) -> Path:
        return self.database.path


def open_room_store(path: Path) -> RoomTestStore:
    return RoomTestStore(Database(path))


def create_room_store(path: Path) -> RoomTestStore:
    run_migrations(path)
    return open_room_store(path)


class StoredRoomService(RoomService):
    store: RoomTestStore


class StoredMemberSessions(MemberSessions):
    store: RoomTestStore


class DemoRoomService(StoredRoomService):
    def __init__(self, store: RoomTestStore) -> None:
        super().__init__(store)
        with store.write_rooms() as repository:
            for state in self._seed_rooms():
                repository.insert_room(state.room)
                repository.save_resources(state, RoomState(room=state.room))
                if state.room.id == "agent-relay":
                    for message in self._seed_messages(state):
                        repository.insert_message(state.room.id, message)

    def _seed_rooms(self) -> list[RoomState]:
        room = Room(
            id="agent-relay",
            name="Agent Relay 开发室",
            project_path="d:/sourcecodes/mywork/agent-relay",
            description="聊天室界面与消息路由开发",
        )
        topics = [
            Topic(id="summary", name="汇总", description="协作约定、关键决策与跨话题同步"),
            Topic(id="frontend", name="前端", description="聊天室界面、交互与可视化"),
            Topic(id="backend", name="后端", description="接口契约、消息路由与投递"),
        ]
        members = [
            Member(
                id="coordinator",
                session_id="agent-relay-coordinator",
                name="主会话",
                initials="CO",
                presence="available",
                activity="可接收协作消息",
                topic_ids=["summary", "frontend", "backend"],
            ),
            Member(
                id="frontend-worker",
                session_id="agent-relay-frontend",
                name="前端 Worker",
                initials="FE",
                presence="busy",
                activity="正在处理消息 · 新投递将排队",
                topic_ids=["frontend", "summary"],
            ),
            Member(
                id="backend-worker",
                session_id="agent-relay-backend",
                name="后端 Worker",
                initials="BE",
                presence="available",
                activity="可接收接口与路由讨论",
                topic_ids=["backend", "summary"],
            ),
            Member(
                id="test-worker",
                session_id="agent-relay-test",
                name="测试 Worker",
                initials="QA",
                presence="available",
                activity="同时订阅前后端，按需查阅",
                topic_ids=["frontend", "backend", "summary"],
            ),
        ]
        state = RoomState(
            room=room,
            topics=topics,
            members=members,
            sessions=[
                Session(
                    id=member.session_id,
                    name=member.name,
                    provider="Codex",
                    project_path=room.project_path,
                    presence=member.presence,
                )
                for member in members
                if member.session_id is not None
            ],
        )
        other = RoomState(
            room=Room(
                id="housekeeper",
                name="Housekeeper",
                project_path="d:/sourcecodes/mywork/housekeeper",
                description="CLI 工具开发",
            ),
            topics=[],
        )
        return [state, other]

    def _seed_messages(self, state: RoomState) -> list[Message]:
        started_at = datetime.now(UTC) - timedelta(minutes=18)
        examples = [
            (
                "coordinator",
                ["summary"],
                [],
                "本轮开发聊天室页面与消息接口。界面问题放在前端话题，接口问题放在后端话题，"
                "联调问题同时关联两个话题。",
            ),
            (
                "coordinator",
                [],
                ["frontend-worker"],
                "请把聊天室分成话题导航、讨论时间线和成员面板。"
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
                "请核对前后端的消息契约：同一条跨话题消息即使命中两个订阅，也只能向同一成员投递一次。",
            ),
            (
                "test-worker",
                ["frontend", "backend"],
                [],
                "联调重点：跨话题消息去重、忙碌成员排队，以及发送失败后保留草稿。",
            ),
            (
                "coordinator",
                ["frontend", "backend"],
                ["frontend-worker", "backend-worker", "test-worker"],
                "登录流程的前后端改造已合并，请一起核对提交失败与重试路径。",
            ),
        ]
        members = {member.id: member for member in state.members}
        messages = []
        for index, (sender_id, topic_ids, mentioned_member_ids, content) in enumerate(examples):
            message = build_message(
                state,
                seq=index + 1,
                content=content,
                topic_ids=topic_ids,
                mentioned_member_ids=mentioned_member_ids,
                sender_id=sender_id,
                sender_name=members[sender_id].name,
                created_at=started_at + timedelta(minutes=index * 3),
                reply_to_message_id=f"{state.room.id}-msg-0004" if index == 4 else None,
            )
            messages.append(message)
        return messages
