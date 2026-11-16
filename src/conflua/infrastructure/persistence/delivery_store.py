from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import select

from conflua.application.dto.delivery import ClaimedDelivery, QueueHead, ReceivedInput
from conflua.domain.rooms.errors import RoomConflictError
from conflua.domain.rooms.models import Delivery
from conflua.infrastructure.persistence.channel_guard import room_operation
from conflua.infrastructure.persistence.database import Database
from conflua.infrastructure.persistence.models import ChannelRecord, DeliveryRecord, RoomRecord
from conflua.infrastructure.persistence.repositories.deliveries import (
    SQLAlchemyDeliveryRepository,
)


class SQLAlchemyDeliveryStore:
    def __init__(self, database: Database) -> None:
        self.database = database

    @contextmanager
    def operation(self, work: ClaimedDelivery) -> Iterator[None]:
        with room_operation(self.database.path, work.room_id):
            with self.database.read() as session:
                channel = session.get(ChannelRecord, (work.room_id, work.channel_id))
                room = session.get(RoomRecord, work.room_id)
                if (
                    room is None
                    or room.archived_at is not None
                    or channel is None
                    or channel.archived_at is not None
                ):
                    raise RoomConflictError("频道当前不可用", code="channel_unavailable")
            yield

    @contextmanager
    def activation_operation(self, session_id: str, head: QueueHead) -> Iterator[None]:
        with self.database.read() as session:
            record = session.scalar(
                select(DeliveryRecord).where(
                    DeliveryRecord.target_session_id == session_id,
                    DeliveryRecord.client_message_id == head.client_message_id,
                )
            )
            room_id = record.room_id if record is not None else None
        if room_id is None:
            raise RoomConflictError("队列首项不属于 Conflua", code="queue_head_not_found")
        with room_operation(self.database.path, room_id):
            yield

    def interrupt_submissions(self) -> None:
        with self.database.write() as session:
            SQLAlchemyDeliveryRepository(session).interrupt_submissions()

    def claim_delivery(self) -> ClaimedDelivery | None:
        with self.database.write() as session:
            return SQLAlchemyDeliveryRepository(session).claim_delivery()

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

    def confirm_input(self, session_id: str, received: ReceivedInput) -> None:
        with self.database.write() as session:
            SQLAlchemyDeliveryRepository(session).confirm_input(session_id, received)
