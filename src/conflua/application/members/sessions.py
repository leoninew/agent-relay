from typing import Protocol

from conflua.application.dto.members import MemberInterruptResult, SessionInfo
from conflua.application.dto.session_models import SessionModelCatalog, UpdateSessionModel


class SessionUnavailableError(RuntimeError):
    def __init__(self, message: str, *, code: str = "service_unavailable") -> None:
        super().__init__(message)
        self.code = code


class SessionInterruptRejected(RuntimeError):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


class SessionDriver(Protocol):
    def list_sessions(self, working_path: str | None = None) -> list[SessionInfo]: ...
    def connected_sessions(self, session_ids: frozenset[str]) -> list[SessionInfo]: ...
    def inspect(self, thread_id: str) -> SessionInfo: ...
    def interrupt(self, thread_id: str) -> MemberInterruptResult: ...
    def model_catalog(self, thread_id: str) -> SessionModelCatalog: ...
    def update_model(self, thread_id: str, request: UpdateSessionModel) -> SessionModelCatalog: ...


class SessionModelRejected(RuntimeError):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code
