from agent_relay.drivers.codex import SessionInfo


class FakeSessionDriver:
    """Metadata only: no method can create, resume or mutate a Codex thread."""

    def __init__(self, sessions: list[SessionInfo] | None = None) -> None:
        self.sessions = {info.id: info for info in sessions or []}
        self.inspected: list[str] = []
        self.listed = 0
        self.error: Exception | None = None

    def list_sessions(self) -> list[SessionInfo]:
        self.listed += 1
        if self.error:
            raise self.error
        return list(self.sessions.values())

    def inspect(self, thread_id: str) -> SessionInfo:
        self.inspected.append(thread_id)
        if self.error:
            raise self.error
        return self.sessions[thread_id]
