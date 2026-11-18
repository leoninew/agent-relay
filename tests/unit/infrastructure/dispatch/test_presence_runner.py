import logging
from threading import Event
from unittest.mock import Mock

from conflua.application.members.service import MemberService
from conflua.infrastructure.dispatch.presence import MemberPresenceRunner


def test_receipts_during_scan_coalesce_and_wake_targeted_refresh() -> None:
    members = Mock(spec=MemberService)
    logger = logging.getLogger("tests.member-presence")
    runner = MemberPresenceRunner(members, logger, interval=300)
    scanning = Event()
    release = Event()
    inspected = Event()

    def scan(*_: object) -> None:
        scanning.set()
        release.wait(5)

    members.refresh_presence.side_effect = scan
    members.refresh_session_presence.side_effect = lambda *_: inspected.set()
    runner.start()
    try:
        assert scanning.wait(5)
        runner.request_refresh("target")
        runner.request_refresh("target")
        release.set()
        assert inspected.wait(5)
    finally:
        release.set()
        runner.close()
    members.refresh_presence.assert_called_once()
    members.refresh_session_presence.assert_called_once_with("target", logger)
