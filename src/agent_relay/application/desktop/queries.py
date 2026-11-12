from datetime import datetime

from agent_relay.application.dto.desktop import ShutdownNotificationTarget
from agent_relay.application.rooms.ports import RoomRepository
from agent_relay.application.transactions import RepositoryScope


class DesktopExitNotificationReader:
    def __init__(self, repositories: RepositoryScope[RoomRepository]) -> None:
        self.repositories = repositories

    def notification_targets(self, started_at: datetime) -> list[ShutdownNotificationTarget]:
        with self.repositories.read() as repository:
            return repository.notification_targets(started_at)
