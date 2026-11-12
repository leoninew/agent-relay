from typing import Protocol

from agent_relay.application.dto.members import SessionInfo


class SessionUnavailableError(RuntimeError):
    pass


class SessionDriver(Protocol):
    def list_sessions(self) -> list[SessionInfo]: ...
    def inspect(self, thread_id: str) -> SessionInfo: ...
