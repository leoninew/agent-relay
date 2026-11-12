from collections import defaultdict
from datetime import datetime

from sqlalchemy import select

from agent_relay.application.desktop.ports import DesktopExitNotificationQueries
from agent_relay.application.dto.desktop import ShutdownNotificationTarget
from agent_relay.domain.rooms.models import USER_MEMBER_ID
from agent_relay.infrastructure.persistence.database import Database
from agent_relay.infrastructure.persistence.models import MemberRecord, MessageRecord


class SQLAlchemyDesktopExitNotificationQueries(DesktopExitNotificationQueries):
    def __init__(self, database: Database) -> None:
        self.database = database

    def notification_targets(self, started_at: datetime) -> list[ShutdownNotificationTarget]:
        with self.database.read() as session:
            rows = session.execute(
                select(MessageRecord.room_id, MemberRecord.id)
                .join(
                    MemberRecord,
                    (MemberRecord.room_id == MessageRecord.room_id)
                    & (MemberRecord.kind == "agent")
                    & MemberRecord.deleted_at.is_(None)
                    & MemberRecord.session_id.is_not(None),
                )
                .where(
                    MessageRecord.publisher_id == USER_MEMBER_ID,
                    MessageRecord.created_at >= started_at,
                )
                .distinct()
                .order_by(MessageRecord.room_id, MemberRecord.id)
            ).tuples()
            grouped: dict[str, list[str]] = defaultdict(list)
            for room_id, member_id in rows:
                grouped[room_id].append(member_id)
        return [
            ShutdownNotificationTarget(room_id, tuple(member_ids))
            for room_id, member_ids in grouped.items()
        ]
