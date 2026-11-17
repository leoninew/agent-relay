import logging
from collections.abc import Callable
from copy import deepcopy
from datetime import UTC, datetime
from typing import TypeVar
from uuid import uuid4

from conflua.application.dto.members import (
    ChangedMember,
    CreatedMember,
    CreateMember,
    MemberInterruptResult,
    SessionCandidate,
    SessionInfo,
    UpdateMember,
)
from conflua.application.dto.session_models import SessionModelCatalog, UpdateSessionModel
from conflua.application.members.sessions import (
    SessionDriver,
    SessionInterruptRejected,
    SessionModelRejected,
    SessionUnavailableError,
)
from conflua.application.rooms.ports import RoomStore
from conflua.domain.rooms.errors import RoomConflictError
from conflua.domain.rooms.members import (
    observation_cutoff,
    rename_member,
    retire_member,
    validate_join,
)
from conflua.domain.rooms.models import Member, RoomState, Session

T = TypeVar("T")


class MemberService:
    def __init__(self, store: RoomStore, driver: SessionDriver) -> None:
        self.store = store
        self.driver = driver
        self.unavailable_presence_sessions: set[str] = set()

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
            working_path = rooms.working_path(room_id)
        sessions = self._metadata(lambda: self.driver.list_sessions(working_path))
        observed_at = datetime.now(UTC)
        self.record_observations(room_id, sessions, observed_at)
        sessions = [info for info in sessions if not info.archived]
        with self.store.read() as rooms:
            joined = rooms.joined_members(room_id)
            joined_channels = rooms.joined_channels(room_id)
        result: list[SessionCandidate] = []
        for info in sessions:
            result.append(
                SessionCandidate(
                    id=info.id,
                    name=info.name,
                    provider=info.provider,
                    presence=info.presence,
                    archived=info.archived,
                    observed_at=observed_at,
                    member_id=joined.get(info.id),
                    joined_channels=joined_channels.get(info.id, []),
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
            for member_id, session_id in rooms.active_bindings(room_id).items():
                info = by_id.get(session_id)
                presence = info.presence if info is not None else "unknown"
                activity = (
                    self.activity(info)
                    if info is not None
                    else "未能核验原会话的当前接入状态；请使用共享 daemon 打开后刷新"
                )
                rooms.save_observation(
                    room_id,
                    member_id,
                    session_id,
                    presence,
                    activity,
                    observed_at,
                    info.name if info is not None else None,
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

    def interrupt(self, room_id: str, member_id: str) -> MemberInterruptResult:
        with self.store.read() as rooms:
            member = rooms.member(room_id, member_id)
            if member.kind != "agent" or not member.session_id:
                raise RoomConflictError("该成员不支持打断", code="member_interrupt_unsupported")
            session_id = member.session_id
        try:
            return self.driver.interrupt(session_id)
        except SessionInterruptRejected as exc:
            raise RoomConflictError(str(exc), code=exc.code) from exc

    def _model_target(self, room_id: str, member_id: str) -> str:
        with self.store.read() as rooms:
            member = rooms.member(room_id, member_id)
            if member.kind != "agent" or not member.session_id:
                raise RoomConflictError("该成员不支持模型切换", code="member_model_unsupported")
            return member.session_id

    def model_catalog(self, room_id: str, member_id: str) -> SessionModelCatalog:
        session_id = self._model_target(room_id, member_id)
        try:
            return self.driver.model_catalog(session_id)
        except SessionModelRejected as exc:
            raise RoomConflictError(str(exc), code=exc.code) from exc

    def update_model(
        self, room_id: str, member_id: str, request: UpdateSessionModel
    ) -> SessionModelCatalog:
        session_id = self._model_target(room_id, member_id)
        if session_id != request.session_id:
            raise RoomConflictError("成员会话已变化，请重新选择", code="session_binding_changed")
        try:
            return self.driver.update_model(session_id, request)
        except SessionModelRejected as exc:
            raise RoomConflictError(str(exc), code=exc.code) from exc

    def add(self, room_id: str, request: CreateMember) -> CreatedMember:
        with self.store.read() as rooms:
            state = rooms.resources(room_id)
            self._validate_add(state, request)
        # External metadata reads never hold a SQLite transaction or resume a thread.
        info = self._metadata(lambda: self.driver.inspect(request.session_id))
        if info.id != request.session_id:
            raise SessionUnavailableError(
                "Codex 返回的会话身份不匹配", code="session_identity_mismatch"
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
        for session_id in dict.fromkeys(session_id for _, _, session_id in bindings):
            if cancelled():
                return
            try:
                info = self.driver.inspect(session_id)
                if info.id != session_id:
                    raise SessionUnavailableError(
                        "Codex 返回的会话身份不匹配", code="session_identity_mismatch"
                    )
                sessions.append(info)
                self.unavailable_presence_sessions.discard(session_id)
            except Exception as exc:
                if session_id not in self.unavailable_presence_sessions:
                    logger.warning(
                        "Member presence unavailable session=%s reason=%s", session_id, exc
                    )
                    self.unavailable_presence_sessions.add(session_id)
        observed_at = datetime.now(UTC)
        for room_id, channel_id in dict.fromkeys(
            (room_id, channel_id) for room_id, channel_id, _ in bindings
        ):
            MemberService(self.store.for_channel(channel_id), self.driver).record_observations(
                room_id, sessions, observed_at
            )
