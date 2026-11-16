from datetime import datetime
from typing import Protocol

from conflua.application.dto.desktop import ShutdownNotificationTarget


class DesktopExitNotificationQueries(Protocol):
    def notification_targets(self, started_at: datetime) -> list[ShutdownNotificationTarget]: ...
