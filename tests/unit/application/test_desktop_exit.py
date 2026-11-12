import hashlib
from datetime import UTC, datetime
from logging import getLogger
from unittest.mock import Mock

from agent_relay.application.desktop.service import (
    OFFLINE_MESSAGE,
    DesktopExitNotificationService,
)
from agent_relay.application.dto.desktop import ShutdownNotificationTarget
from agent_relay.application.messages.service import MessageService


def test_exit_notifications_are_directed_once_per_active_target_room(
    room_repository: Mock, room_store: Mock
) -> None:
    queries = Mock()
    queries.notification_targets.return_value = [
        ShutdownNotificationTarget("agent-relay", ("coordinator", "test-worker")),
        ShutdownNotificationTarget("empty-room", ()),
    ]
    service = DesktopExitNotificationService(
        queries,
        MessageService(room_store),
        getLogger("tests.desktop-exit"),
    )
    started_at = datetime(2026, 11, 12, tzinfo=UTC)

    published = service.publish(started_at=started_at, run_id="run-2026-11-12")

    queries.notification_targets.assert_called_once_with(started_at)
    assert len(published) == 1
    assert published[0][0] == "agent-relay"
    saved_message = room_repository.insert_message.call_args.args[1]
    assert saved_message.content == OFFLINE_MESSAGE
    assert saved_message.topic_ids == []
    assert saved_message.mentioned_member_ids == ["coordinator", "test-worker"]
    request = room_repository.publication.call_args
    room_key = hashlib.sha256(b"agent-relay").hexdigest()[:12]
    assert request.args == (
        "agent-relay",
        "user",
        f"desktop-offline-run-2026-11-12-{room_key}",
    )


def test_exit_notification_failure_does_not_skip_other_rooms() -> None:
    queries = Mock()
    queries.notification_targets.return_value = [
        ShutdownNotificationTarget("first-room", ("agent-one",)),
        ShutdownNotificationTarget("second-room", ("agent-two",)),
    ]
    messages = Mock()
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


def test_exit_notification_is_idempotent_for_the_same_run(
    room_repository: Mock, room_store: Mock
) -> None:
    queries = Mock()
    queries.notification_targets.return_value = [
        ShutdownNotificationTarget("agent-relay", ("coordinator",)),
    ]
    service = DesktopExitNotificationService(
        queries,
        MessageService(room_store),
        getLogger("tests.desktop-exit"),
    )
    started_at = datetime(2026, 11, 12, tzinfo=UTC)

    service.publish(started_at=started_at, run_id="run-1")
    first_publication_id = room_repository.publication.call_args.args[2]
    service.publish(started_at=started_at, run_id="run-1")

    assert room_repository.publication.call_args.args[2] == first_publication_id
