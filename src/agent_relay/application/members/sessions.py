from typing import Protocol

from agent_relay.application.dto.members import SessionInfo


class SessionUnavailableError(RuntimeError):
    def __init__(self, message: str, *, code: str = "service_unavailable") -> None:
        super().__init__(message)
        self.code = code


class SessionDriver(Protocol):
    def list_sessions(self) -> list[SessionInfo]: ...
    def inspect(self, thread_id: str) -> SessionInfo: ...
