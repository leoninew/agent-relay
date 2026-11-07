from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol, TypeVar
from uuid import uuid4

from agent_relay.drivers.codex import SessionInfo
from agent_relay.room_models import CreatedMember, CreateMember, Member, Session, SessionCandidate
from agent_relay.room_service import (
    RoomConflictError,
    RoomInputError,
    RoomNotFoundError,
    RoomService,
)
from agent_relay.room_state import RoomState
from agent_relay.room_store import SQLiteRoomStore


class SessionUnavailableError(RuntimeError):
    """Codex metadata could not be verified; the cause is for server logs only."""


class SessionDriver(Protocol):
    def list_sessions(self) -> list[SessionInfo]: ...
    def inspect(self, thread_id: str) -> SessionInfo: ...


T = TypeVar("T")


class MemberSessions:
    def __init__(self, store: SQLiteRoomStore, driver: SessionDriver) -> None:
        self.store = store
        self.driver = driver

    @staticmethod
    def _room(rooms: dict[str, RoomState], room_id: str) -> RoomState:
        if room_id not in rooms:
            raise RoomNotFoundError("聊天室不存在")
        return rooms[room_id]

    @staticmethod
    def _metadata(read: Callable[[], T]) -> T:
        try:
            return read()
        except Exception as exc:
            raise SessionUnavailableError("无法读取 Codex 会话，请刷新后重试") from exc

    def candidates(self, room_id: str) -> list[SessionCandidate]:
        with self.store.transaction(write=False) as rooms:
            cwd = self._room(rooms, room_id).room.project_path
        sessions = self._metadata(self.driver.list_sessions)
        observed_at = datetime.now(UTC)
        with self.store.transaction(write=False) as rooms:
            state = self._room(rooms, room_id)
            joined = {
                member.session_id: member.id for member in state.members if not member.deleted_at
            }
        result: list[SessionCandidate] = []
        for info in sessions:
            if RoomService._normalize_project_path(info.cwd) != cwd:
                continue
            result.append(
                SessionCandidate(
                    id=info.id,
                    name=info.name,
                    provider=info.provider,
                    project_path=info.cwd,
                    presence=info.presence,
                    archived=info.archived,
                    observed_at=observed_at,
                    member_id=joined.get(info.id),
                )
            )
        return result

    @staticmethod
    def _validate_add(state: RoomState, request: CreateMember) -> None:
        RoomService._validate_member(state, request)
        if any(
            member.session_id == request.session_id and not member.deleted_at
            for member in state.members
        ):
            raise RoomConflictError("该会话已加入聊天室")

    def add(self, room_id: str, request: CreateMember) -> CreatedMember:
        with self.store.transaction(write=False) as rooms:
            state = self._room(rooms, room_id)
            self._validate_add(state, request)
            cwd = state.room.project_path
        # External metadata reads never hold a SQLite transaction or resume a thread.
        info = self._metadata(lambda: self.driver.inspect(request.session_id))
        if info.id != request.session_id:
            raise SessionUnavailableError("Codex 返回的会话身份不匹配")
        if RoomService._normalize_project_path(info.cwd) != cwd:
            raise RoomInputError("所选 Codex 会话不属于当前聊天室项目目录")
        with self.store.transaction(write=True) as rooms:
            state = self._room(rooms, room_id)
            self._validate_add(state, request)
            now = datetime.now(UTC)
            session = Session(
                id=info.id,
                name=info.name,
                provider=info.provider,
                project_path=info.cwd,
                presence=info.presence,
                observed_at=now,
            )
            # A stored session is metadata; only a Member makes it a routing target.
            state.sessions = [saved for saved in state.sessions if saved.id != info.id]
            state.sessions.append(session)
            member = Member(
                id=f"member-{uuid4().hex[:12]}",
                session_id=info.id,
                name=request.name,
                initials=request.name[:2].upper(),
                presence=info.presence,
                activity={
                    "idle": "会话空闲",
                    "active": "会话运行中",
                    "notLoaded": "会话未加载",
                    "systemError": "会话状态异常",
                }[info.status],
                activity_source="codex",
                observed_at=now,
                topic_ids=list(dict.fromkeys(request.topic_ids)),
            )
            state.members.append(member)
            return CreatedMember(**member.model_dump(), session=session.model_copy(deep=True))
