import logging
from threading import Event, Thread

from agent_relay.application.members.service import MemberService


class MemberPresenceRunner:
    def __init__(self, members: MemberService, logger: logging.Logger, interval: float = 5) -> None:
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
        self.members.refresh_presence(self.logger, self.stop.is_set)
