from datetime import datetime
from typing import Protocol

from agent_relay.application.dto.desktop import ShutdownNotificationTarget


class DesktopExitNotificationQueries(Protocol):
    def notification_targets(self, started_at: datetime) -> list[ShutdownNotificationTarget]: ...
