import hashlib
import logging
from datetime import datetime

from agent_relay.application.desktop.ports import DesktopExitNotificationQueries
from agent_relay.application.dto.messages import CreateMessage
from agent_relay.application.messages.service import MessageService
from agent_relay.domain.rooms.models import Message

OFFLINE_MESSAGE = "管理端已离线。"


class DesktopExitNotificationService:
    def __init__(
        self,
        queries: DesktopExitNotificationQueries,
        messages: MessageService,
        logger: logging.Logger,
    ) -> None:
        self.queries = queries
        self.messages = messages
        self.logger = logger

    def publish(self, *, started_at: datetime, run_id: str) -> list[tuple[str, Message]]:
        published: list[tuple[str, Message]] = []
        for target in self.queries.notification_targets(started_at):
            if not target.agent_member_ids:
                continue
            room_key = hashlib.sha256(target.room_id.encode("utf-8")).hexdigest()[:12]
            request = CreateMessage(
                publication_id=f"desktop-offline-{run_id}-{room_key}",
                content=OFFLINE_MESSAGE,
                mentioned_member_ids=list(target.agent_member_ids),
            )
            try:
                message = self.messages.post_message(target.room_id, request)
            except Exception:
                self.logger.exception(
                    "Unable to publish desktop offline notification room=%s", target.room_id
                )
                continue
            published.append((target.room_id, message))
        return published
