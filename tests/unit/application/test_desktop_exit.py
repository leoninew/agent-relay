import hashlib
from datetime import UTC, datetime
from logging import getLogger
from unittest.mock import Mock

from agent_relay.application.desktop.ports import DesktopExitNotificationQueries
from agent_relay.application.desktop.service import (
    OFFLINE_MESSAGE,
    DesktopExitNotificationService,
)
from agent_relay.application.dto.desktop import ShutdownNotificationTarget
from agent_relay.application.messages.service import MessageService


def test_exit_notifications_build_direct_requests_with_stable_publication_ids() -> None:
    queries = Mock(spec=DesktopExitNotificationQueries)
    queries.notification_targets.return_value = [
        ShutdownNotificationTarget("agent-relay", ("coordinator", "test-worker")),
        ShutdownNotificationTarget("empty-room", ()),
    ]
    messages = Mock(spec=MessageService)
    service = DesktopExitNotificationService(queries, messages, getLogger("tests.desktop-exit"))
    started_at = datetime(2026, 11, 12, tzinfo=UTC)

    published = service.publish(started_at=started_at, run_id="run-2026-11-12")

    queries.notification_targets.assert_called_once_with(started_at)
    assert len(published) == 1
    assert published[0][0] == "agent-relay"
    messages.post_message.assert_called_once()
    room_id, request = messages.post_message.call_args.args
    assert room_id == "agent-relay"
    assert published[0][1] is messages.post_message.return_value
    assert request.content == OFFLINE_MESSAGE and request.topic_ids == []
    assert request.mentioned_member_ids == ["coordinator", "test-worker"]
    room_key = hashlib.sha256(b"agent-relay").hexdigest()[:12]
    assert request.publication_id == f"desktop-offline-run-2026-11-12-{room_key}"
    service.publish(started_at=started_at, run_id="run-2026-11-12")
    assert messages.post_message.call_args.args[1].publication_id == request.publication_id


def test_exit_notification_failure_does_not_skip_other_rooms() -> None:
    queries = Mock(spec=DesktopExitNotificationQueries)
    queries.notification_targets.return_value = [
        ShutdownNotificationTarget("first-room", ("agent-one",)),
        ShutdownNotificationTarget("second-room", ("agent-two",)),
    ]
    messages = Mock(spec=MessageService)
    messages.post_message.side_effect = [RuntimeError("temporary failure"), Mock()]
    service = DesktopExitNotificationService(
        queries,
        messages,
        getLogger("tests.desktop-exit"),
    )

    published = service.publish(started_at=datetime(2026, 11, 12, tzinfo=UTC), run_id="run-1")

    assert len(published) == 1
    assert published[0][0] == "second-room"
    assert [call.args[0] for call in messages.post_message.call_args_list] == [
        "first-room",
        "second-room",
    ]
