import logging
from datetime import UTC, datetime
from threading import Event, Thread

from agent_relay.drivers.codex import SessionInfo
from agent_relay.member_sessions import MemberSessions, SessionUnavailableError


class MemberPresenceService:
    def __init__(
        self, members: MemberSessions, logger: logging.Logger, interval: float = 5
    ) -> None:
        self.members = members
        self.logger = logger
        self.interval = interval
        self.stop = Event()
        self.thread = Thread(target=self._run, name="relay-member-presence", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def close(self) -> None:
        self.stop.set()
        self.thread.join()

    def _run(self) -> None:
        while not self.stop.is_set():
            try:
                self.refresh()
            except Exception:
                self.logger.exception("Unable to refresh member presence")
            self.stop.wait(self.interval)

    def refresh(self) -> None:
        with self.members.store.read() as connection:
            bindings = connection.execute(
                "SELECT room_id, session_id FROM members WHERE deleted_at IS NULL "
                "AND session_id IS NOT NULL AND json_extract(payload, '$.kind') = 'agent'"
            ).fetchall()
        sessions: list[SessionInfo] = []
        for session_id in dict.fromkeys(row["session_id"] for row in bindings):
            if self.stop.is_set():
                return
            try:
                info = self.members.driver.inspect(session_id)
                if info.id != session_id:
                    raise SessionUnavailableError("Codex 返回的会话身份不匹配")
                sessions.append(info)
            except Exception:
                self.logger.exception("Member presence unavailable session=%s", session_id)
        observed_at = datetime.now(UTC)
        for room_id in dict.fromkeys(row["room_id"] for row in bindings):
            self.members.record_observations(room_id, sessions, observed_at)
