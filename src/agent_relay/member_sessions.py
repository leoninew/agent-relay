from collections.abc import Callable
from copy import deepcopy
from datetime import UTC, datetime
from typing import Protocol, TypeVar
from uuid import uuid4

from agent_relay.drivers.codex import SessionInfo
from agent_relay.room_errors import RoomConflictError, RoomInputError
from agent_relay.room_models import CreatedMember, CreateMember, Member, Session, SessionCandidate
from agent_relay.room_queries import RoomQueries
from agent_relay.room_service import RoomService
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
    def _metadata(read: Callable[[], T]) -> T:
        try:
            return read()
        except Exception as exc:
            raise SessionUnavailableError("无法读取 Codex 会话，请刷新后重试") from exc

    def candidates(self, room_id: str) -> list[SessionCandidate]:
        queries = RoomQueries(self.store)
        with self.store.read() as connection:
            cwd = queries.room_in(connection, room_id).project_path
        sessions = self._metadata(self.driver.list_sessions)
        observed_at = datetime.now(UTC)
        self.record_observations(room_id, sessions, observed_at)
        with self.store.read() as connection:
            joined = queries.joined_members_in(connection, room_id)
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
                    usable=info.usable,
                    unavailable_reason=info.unavailable_reason,
                )
            )
        return result

    def record_observations(
        self, room_id: str, sessions: list[SessionInfo], observed_at: datetime
    ) -> None:
        """Update observation fields only; never overwrite names or subscriptions."""
        by_id = {info.id: info for info in sessions}
        queries = RoomQueries(self.store)
        with self.store.write() as connection:
            cwd = queries.room_in(connection, room_id).project_path
            for session_id, member_id in queries.joined_members_in(connection, room_id).items():
                info = by_id.get(session_id)
                valid = info is not None and RoomService._normalize_project_path(info.cwd) == cwd
                presence = info.presence if valid and info is not None else "unknown"
                activity = (
                    self.activity(info)
                    if valid and info is not None
                    else "未能核验原会话的当前接入状态；请使用共享 daemon 打开后刷新"
                )
                self.store.save_observation(
                    connection,
                    room_id,
                    member_id,
                    session_id,
                    presence,
                    activity,
                    observed_at,
                )

    @staticmethod
    def activity(info: SessionInfo) -> str:
        return (
            info.unavailable_reason
            or {
                "idle": "共享 Codex 会话空闲",
                "active": "共享 Codex 会话忙碌，消息可排队",
            }[info.status]
        )

    @staticmethod
    def _validate_add(state: RoomState, request: CreateMember) -> None:
        RoomService._validate_member(state, request)
        if any(
            member.session_id == request.session_id and not member.deleted_at
            for member in state.members
        ):
            raise RoomConflictError("该会话已加入聊天室")

    def add(self, room_id: str, request: CreateMember) -> CreatedMember:
        queries = RoomQueries(self.store)
        with self.store.read() as connection:
            state = queries.resources_in(connection, room_id)
            self._validate_add(state, request)
            cwd = state.room.project_path
        # External metadata reads never hold a SQLite transaction or resume a thread.
        info = self._metadata(lambda: self.driver.inspect(request.session_id))
        if info.id != request.session_id:
            raise SessionUnavailableError("Codex 返回的会话身份不匹配")
        if RoomService._normalize_project_path(info.cwd) != cwd:
            raise RoomInputError("所选 Codex 会话不属于当前聊天室项目目录")
        if not info.usable:
            raise RoomConflictError(info.unavailable_reason or "所选 Codex 会话当前不可用")
        with self.store.write() as connection:
            state = queries.resources_in(connection, room_id)
            self._validate_add(state, request)
            original = deepcopy(state)
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
                activity=self.activity(info),
                activity_source="codex",
                observed_at=now,
                topic_ids=list(dict.fromkeys(request.topic_ids)),
            )
            state.members.append(member)
            self.store.save_resources(connection, state, original)
            return CreatedMember(
                **member.model_dump(),
                session=session.model_copy(deep=True),
                metadata=queries.metadata_in(connection, room_id),
            )
