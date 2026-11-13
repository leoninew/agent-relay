import logging
from collections.abc import Callable
from copy import deepcopy
from datetime import UTC, datetime
from typing import TypeVar
from uuid import uuid4

from agent_relay.application.dto.members import (
    ChangedMember,
    CreatedMember,
    CreateMember,
    SessionCandidate,
    SessionInfo,
    UpdateMember,
)
from agent_relay.application.members.sessions import (
    SessionDriver,
    SessionUnavailableError,
)
from agent_relay.application.rooms.ports import RoomStore
from agent_relay.domain.rooms.errors import RoomConflictError, RoomInputError
from agent_relay.domain.rooms.members import (
    observation_cutoff,
    rename_member,
    retire_member,
    validate_join,
)
from agent_relay.domain.rooms.models import Member, RoomState, Session
from agent_relay.domain.rooms.rules import normalize_project_path

T = TypeVar("T")


class MemberService:
    def __init__(self, store: RoomStore, driver: SessionDriver) -> None:
        self.store = store
        self.driver = driver

    @staticmethod
    def _metadata(read: Callable[[], T]) -> T:
        try:
            return read()
        except Exception as exc:
            raise SessionUnavailableError(
                "无法读取 Codex 会话，请刷新后重试", code="session_metadata_unavailable"
            ) from exc

    def candidates(self, room_id: str) -> list[SessionCandidate]:
        with self.store.read() as rooms:
            cwd = rooms.room(room_id).project_path
        sessions = self._metadata(self.driver.list_sessions)
        observed_at = datetime.now(UTC)
        self.record_observations(room_id, sessions, observed_at)
        with self.store.read() as rooms:
            joined = rooms.joined_members(room_id)
        result: list[SessionCandidate] = []
        for info in sessions:
            if normalize_project_path(info.cwd) != cwd:
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
                    unavailable_reason_code=info.unavailable_reason_code,
                )
            )
        return result

    def record_observations(
        self, room_id: str, sessions: list[SessionInfo], observed_at: datetime
    ) -> None:
        """Refresh session metadata without changing member names or subscriptions."""
        by_id = {info.id: info for info in sessions}
        with self.store.write() as rooms:
            cwd = rooms.room(room_id).project_path
            for session_id, member_id in rooms.joined_members(room_id).items():
                info = by_id.get(session_id)
                valid = info is not None and normalize_project_path(info.cwd) == cwd
                presence = info.presence if valid and info is not None else "unknown"
                activity = (
                    self.activity(info)
                    if valid and info is not None
                    else "未能核验原会话的当前接入状态；请使用共享 daemon 打开后刷新"
                )
                rooms.save_observation(
                    room_id,
                    member_id,
                    session_id,
                    presence,
                    activity,
                    observed_at,
                    info.name if valid and info is not None else None,
                    refresh_cutoff=observation_cutoff(observed_at),
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
        validate_join(state, request.name, request.topic_ids, request.session_id)

    def update_member(self, room_id: str, member_id: str, request: UpdateMember) -> ChangedMember:
        with self.store.write() as rooms:
            state = rooms.resources(room_id)
            original = deepcopy(state)
            member = rename_member(state, member_id, request.name, request.topic_ids)
            rooms.save_resources(state, original)
            return ChangedMember(**member.model_dump(), metadata=rooms.metadata(room_id))

    def delete_member(self, room_id: str, member_id: str) -> ChangedMember:
        with self.store.write() as rooms:
            state = rooms.resources(room_id)
            original = deepcopy(state)
            member = retire_member(state, member_id, datetime.now(UTC))
            rooms.save_resources(state, original)
            return ChangedMember(**member.model_dump(), metadata=rooms.metadata(room_id))

    def add(self, room_id: str, request: CreateMember) -> CreatedMember:
        with self.store.read() as rooms:
            state = rooms.resources(room_id)
            self._validate_add(state, request)
            cwd = state.room.project_path
        # External metadata reads never hold a SQLite transaction or resume a thread.
        info = self._metadata(lambda: self.driver.inspect(request.session_id))
        if info.id != request.session_id:
            raise SessionUnavailableError(
                "Codex 返回的会话身份不匹配", code="session_identity_mismatch"
            )
        if normalize_project_path(info.cwd) != cwd:
            raise RoomInputError(
                "所选 Codex 会话不属于当前聊天室项目目录", code="session_project_mismatch"
            )
        if not info.usable:
            raise RoomConflictError(
                info.unavailable_reason or "所选 Codex 会话当前不可用",
                code=info.unavailable_reason_code or "session_unavailable",
            )
        with self.store.write() as rooms:
            state = rooms.resources(room_id)
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
            rooms.save_resources(state, original)
            return CreatedMember(
                **member.model_dump(),
                session=session.model_copy(deep=True),
                metadata=rooms.metadata(room_id),
            )

    def refresh_presence(self, logger: logging.Logger, cancelled: Callable[[], bool]) -> None:
        with self.store.read() as rooms:
            bindings = rooms.bindings()
        sessions: list[SessionInfo] = []
        for session_id in dict.fromkeys(session_id for _, session_id in bindings):
            if cancelled():
                return
            try:
                info = self.driver.inspect(session_id)
                if info.id != session_id:
                    raise SessionUnavailableError(
                        "Codex 返回的会话身份不匹配", code="session_identity_mismatch"
                    )
                sessions.append(info)
            except Exception:
                logger.exception("Member presence unavailable session=%s", session_id)
        observed_at = datetime.now(UTC)
        for room_id in dict.fromkeys(room_id for room_id, _ in bindings):
            self.record_observations(room_id, sessions, observed_at)
