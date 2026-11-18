import logging
from threading import Condition, Event, Thread
from time import monotonic

from conflua.application.members.service import MemberService


class MemberPresenceRunner:
    def __init__(self, members: MemberService, logger: logging.Logger, interval: float = 5) -> None:
        self.members = members
        self.logger = logger
        self.interval = interval
        self.stop = Event()
        self.condition = Condition()
        self.pending: set[str] = set()
        self.thread = Thread(target=self._run, name="conflua-member-presence", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def close(self) -> None:
        with self.condition:
            self.stop.set()
            self.condition.notify()
        self.thread.join()

    def request_refresh(self, session_id: str) -> None:
        with self.condition:
            if not self.stop.is_set():
                self.pending.add(session_id)
                self.condition.notify()

    def _run(self) -> None:
        next_scan = monotonic()
        while True:
            with self.condition:
                self.condition.wait_for(
                    lambda: self.stop.is_set() or bool(self.pending),
                    timeout=max(0, next_scan - monotonic()),
                )
                if self.stop.is_set():
                    return
                if monotonic() >= next_scan:
                    self.pending.clear()
                    session_id = None
                else:
                    session_id = self.pending.pop()
            try:
                if session_id is None:
                    self.refresh()
                else:
                    self.members.refresh_session_presence(session_id, self.logger)
            except Exception:
                self.logger.exception("Unable to refresh member presence")
            if session_id is None:
                next_scan = monotonic() + self.interval

    def refresh(self) -> None:
        self.members.refresh_presence(self.logger, self.stop.is_set)
