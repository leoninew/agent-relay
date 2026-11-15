from typing import Protocol

from agent_relay.application.dto.members import MemberInterruptResult, SessionInfo


class SessionUnavailableError(RuntimeError):
    def __init__(self, message: str, *, code: str = "service_unavailable") -> None:
        super().__init__(message)
        self.code = code


class SessionInterruptRejected(RuntimeError):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


class SessionDriver(Protocol):
    def list_sessions(self) -> list[SessionInfo]: ...
    def inspect(self, thread_id: str) -> SessionInfo: ...
    def interrupt(self, thread_id: str, project_path: str) -> MemberInterruptResult: ...
