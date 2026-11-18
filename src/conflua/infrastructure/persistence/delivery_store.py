from datetime import UTC, datetime

from conflua.application.dto.delivery import (
    ActivationWork,
    ClaimedDelivery,
    QueueHead,
    QueueReceipt,
    ReceivedInput,
)
from conflua.domain.rooms.models import Delivery
from conflua.infrastructure.persistence.database import Database
from conflua.infrastructure.persistence.models import ChannelRecord, RoomRecord
from conflua.infrastructure.persistence.repositories.deliveries import (
    SQLAlchemyDeliveryRepository,
)


class SQLAlchemyDeliveryStore:
    def __init__(self, database: Database) -> None:
        self.database = database

    def delivery_available(self, work: ClaimedDelivery) -> bool:
        with self.database.read() as session:
            channel = session.get(ChannelRecord, (work.room_id, work.channel_id))
            room = session.get(RoomRecord, work.room_id)
            return (
                room is not None
                and room.archived_at is None
                and channel is not None
                and (channel.archived_at is None or channel.status == "archived")
            )

    def interrupt_submissions(self) -> None:
        with self.database.write() as session:
            SQLAlchemyDeliveryRepository(session).interrupt_submissions()

    def claim_delivery(
        self, excluded_sessions: frozenset[str] = frozenset()
    ) -> ClaimedDelivery | None:
        with self.database.write() as session:
            return SQLAlchemyDeliveryRepository(session).claim_delivery(
                excluded_sessions, datetime.now(UTC)
            )

    def defer_delivery(self, work: ClaimedDelivery, reason: str, next_attempt_at: datetime) -> bool:
        with self.database.write() as session:
            return SQLAlchemyDeliveryRepository(session).defer_delivery(
                work, reason, next_attempt_at
            )

    def claim_activation_work(self, excluded_sessions: frozenset[str]) -> ActivationWork | None:
        with self.database.write() as session:
            return SQLAlchemyDeliveryRepository(session).claim_activation_work(
                excluded_sessions, datetime.now(UTC)
            )

    def finish_delivery(self, room_id: str, delivery: Delivery) -> bool:
        with self.database.write() as session:
            return SQLAlchemyDeliveryRepository(session).finish_delivery(room_id, delivery)

    def claim_activation(self, session_id: str, head: QueueHead) -> bool:
        if head.client_message_id is None:
            return False
        with self.database.write() as session:
            return SQLAlchemyDeliveryRepository(session).claim_activation(session_id, head)

    def delivery_note(self, session_id: str, client_message_id: str, note: str) -> None:
        with self.database.write() as session:
            SQLAlchemyDeliveryRepository(session).delivery_note(session_id, client_message_id, note)

    def unconfirmed_inputs(self) -> dict[str, set[str]]:
        with self.database.read() as session:
            return SQLAlchemyDeliveryRepository(session).unconfirmed_inputs()

    def confirm_input(self, session_id: str, received: ReceivedInput) -> bool:
        with self.database.write() as session:
            return SQLAlchemyDeliveryRepository(session).confirm_input(session_id, received)

    def confirm_queue(self, session_id: str, client_message_id: str, receipt: QueueReceipt) -> None:
        with self.database.write() as session:
            SQLAlchemyDeliveryRepository(session).confirm_queue(
                session_id, client_message_id, receipt
            )
