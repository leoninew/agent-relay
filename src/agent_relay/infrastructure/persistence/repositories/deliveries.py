from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session, aliased
from sqlalchemy.sql.dml import Update

from agent_relay.application.delivery.ports import ClaimedDelivery, QueueHead, ReceivedInput
from agent_relay.domain.rooms.models import Delivery
from agent_relay.infrastructure.persistence.mappers import delivery_from_model, delivery_values
from agent_relay.infrastructure.persistence.message_queries import MessageQueries
from agent_relay.infrastructure.persistence.models import (
    DeliveryRecord,
    MemberRecord,
    RoomEventRecord,
)
from agent_relay.infrastructure.persistence.resource_queries import ResourceQueries
from agent_relay.infrastructure.persistence.sqlite import insertion_order


class SQLAlchemyDeliveryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _update(self, statement: Update) -> int:
        changed = (
            self.session.execute(
                statement.returning(
                    DeliveryRecord.room_id, DeliveryRecord.id, DeliveryRecord.message_id
                ).execution_options(synchronize_session="fetch")
            )
            .tuples()
            .all()
        )
        self.session.add_all(
            RoomEventRecord(
                room_id=room_id, kind="delivery", entity_id=delivery_id, message_id=message_id
            )
            for room_id, delivery_id, message_id in changed
        )
        self.session.flush()
        return len(changed)

    def interrupt_submissions(self) -> None:
        self._update(
            update(DeliveryRecord)
            .where(DeliveryRecord.status == "submitting", DeliveryRecord.deleted_at.is_(None))
            .values(
                status="unknown",
                updated_at=datetime.now(UTC),
                error="提交中断，入队结果未知；不会自动重发",
            )
        )

    def claim_delivery(self) -> ClaimedDelivery | None:
        active = aliased(DeliveryRecord)
        busy = (
            select(active.id)
            .where(
                active.target_session_id == DeliveryRecord.target_session_id,
                active.status == "submitting",
                active.deleted_at.is_(None),
            )
            .exists()
        )
        candidate = self.session.scalar(
            select(DeliveryRecord)
            .join(
                MemberRecord,
                (MemberRecord.room_id == DeliveryRecord.room_id)
                & (MemberRecord.id == DeliveryRecord.target_member_id)
                & (MemberRecord.session_id == DeliveryRecord.target_session_id)
                & (MemberRecord.kind == "agent"),
            )
            .where(DeliveryRecord.status == "pending", DeliveryRecord.deleted_at.is_(None), ~busy)
            .order_by(insertion_order("deliveries"))
            .limit(1)
        )
        if candidate is None:
            return None
        changed = self._update(
            update(DeliveryRecord)
            .where(
                DeliveryRecord.room_id == candidate.room_id,
                DeliveryRecord.id == candidate.id,
                DeliveryRecord.status == "pending",
                DeliveryRecord.deleted_at.is_(None),
            )
            .values(status="submitting", updated_at=datetime.now(UTC))
        )
        if changed != 1:
            return None
        return ClaimedDelivery(
            candidate.room_id,
            ResourceQueries(self.session).room(candidate.room_id),
            MessageQueries(self.session).message(candidate.room_id, candidate.message_id),
            delivery_from_model(candidate),
        )

    def finish_delivery(self, room_id: str, delivery: Delivery) -> bool:
        values = delivery_values(delivery)
        for field in ("id", "target_member_id", "target_session_id", "client_message_id"):
            del values[field]
        return (
            self._update(
                update(DeliveryRecord)
                .where(
                    DeliveryRecord.room_id == room_id,
                    DeliveryRecord.id == delivery.id,
                    DeliveryRecord.status == "submitting",
                    DeliveryRecord.deleted_at.is_(None),
                    DeliveryRecord.client_message_id == delivery.client_message_id,
                )
                .values(**values)
            )
            == 1
        )

    def claim_activation(self, session_id: str, head: QueueHead) -> bool:
        if head.client_message_id is None:
            return False
        return (
            self._update(
                update(DeliveryRecord)
                .where(
                    DeliveryRecord.target_session_id == session_id,
                    DeliveryRecord.status == "queued",
                    DeliveryRecord.deleted_at.is_(None),
                    DeliveryRecord.queued_submission_id == head.id,
                    DeliveryRecord.client_message_id == head.client_message_id,
                    DeliveryRecord.activation_attempted_at.is_(None),
                )
                .values(activation_attempted_at=datetime.now(UTC))
            )
            == 1
        )

    def delivery_note(self, session_id: str, client_message_id: str, note: str) -> None:
        self._update(
            update(DeliveryRecord)
            .where(
                DeliveryRecord.target_session_id == session_id,
                DeliveryRecord.status == "queued",
                DeliveryRecord.deleted_at.is_(None),
                DeliveryRecord.client_message_id == client_message_id,
            )
            .values(note=note)
        )

    def unconfirmed_inputs(self) -> dict[str, set[str]]:
        result: dict[str, set[str]] = {}
        rows = self.session.execute(
            select(DeliveryRecord.target_session_id, DeliveryRecord.client_message_id)
            .where(
                DeliveryRecord.status.in_(("queued", "unknown")),
                DeliveryRecord.deleted_at.is_(None),
            )
            .order_by(insertion_order("deliveries"))
        )
        for session_id, client_message_id in rows:
            result.setdefault(session_id, set()).add(client_message_id)
        return result

    def confirm_input(self, session_id: str, received: ReceivedInput) -> None:
        now = datetime.now(UTC)
        self._update(
            update(DeliveryRecord)
            .where(
                DeliveryRecord.target_session_id == session_id,
                DeliveryRecord.status.in_(("queued", "unknown")),
                DeliveryRecord.deleted_at.is_(None),
                DeliveryRecord.client_message_id == received.client_message_id,
            )
            .values(
                status="received",
                updated_at=now,
                received_at=now,
                received_item_id=received.item_id,
                received_turn_id=received.turn_id,
                note=None,
                error=None,
            )
        )
