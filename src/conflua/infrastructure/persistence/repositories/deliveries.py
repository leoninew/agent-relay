from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, literal_column, or_, select, update
from sqlalchemy.orm import Session, aliased
from sqlalchemy.orm.util import AliasedClass
from sqlalchemy.sql.dml import Update
from sqlalchemy.sql.elements import ColumnElement

from conflua.application.dto.delivery import (
    ActivationWork,
    ClaimedDelivery,
    QueueHead,
    QueueReceipt,
    ReceivedInput,
)
from conflua.domain.rooms.delivery import (
    INTERRUPTED_SUBMISSION,
    QUEUED_NOTE,
    UNCONFIRMED_DELIVERY_STATUSES,
)
from conflua.domain.rooms.models import Delivery
from conflua.infrastructure.persistence.mappers import delivery_from_model, delivery_values
from conflua.infrastructure.persistence.models import (
    ChannelRecord,
    DeliveryRecord,
    MemberRecord,
    RoomEventRecord,
    RoomRecord,
)
from conflua.infrastructure.persistence.repositories.messages import SQLAlchemyMessageRepository
from conflua.infrastructure.persistence.repositories.rooms import SQLAlchemyRoomRepository
from conflua.infrastructure.persistence.sqlite import insertion_order, time_at_or_before


class SQLAlchemyDeliveryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _update(self, statement: Update) -> int:
        changed = (
            self.session.execute(
                statement.returning(
                    DeliveryRecord.room_id,
                    DeliveryRecord.channel_id,
                    DeliveryRecord.id,
                    DeliveryRecord.message_id,
                ).execution_options(synchronize_session="fetch")
            )
            .tuples()
            .all()
        )
        self.session.add_all(
            RoomEventRecord(
                room_id=room_id,
                channel_id=channel_id,
                kind="delivery",
                entity_id=delivery_id,
                message_id=message_id,
            )
            for room_id, channel_id, delivery_id, message_id in changed
        )
        self.session.flush()
        return len(changed)

    def interrupt_submissions(self) -> None:
        self._update(
            update(DeliveryRecord)
            .where(DeliveryRecord.status == "submitting", DeliveryRecord.deleted_at.is_(None))
            .values(
                status=INTERRUPTED_SUBMISSION.status,
                updated_at=datetime.now(UTC),
                error=INTERRUPTED_SUBMISSION.error,
            )
        )

    def _dispatchable(
        self, delivery: type[DeliveryRecord] | AliasedClass[DeliveryRecord]
    ) -> ColumnElement[bool]:
        return (
            select(MemberRecord.id)
            .join(
                ChannelRecord,
                (ChannelRecord.room_id == MemberRecord.room_id)
                & (ChannelRecord.id == MemberRecord.channel_id),
            )
            .join(RoomRecord, RoomRecord.id == MemberRecord.room_id)
            .where(
                MemberRecord.room_id == delivery.room_id,
                MemberRecord.channel_id == delivery.channel_id,
                MemberRecord.id == delivery.target_member_id,
                MemberRecord.session_id == delivery.target_session_id,
                MemberRecord.kind == "agent",
                MemberRecord.deleted_at.is_(None),
                ChannelRecord.archived_at.is_(None),
                RoomRecord.archived_at.is_(None),
            )
            .correlate(delivery)
            .exists()
        )

    def claim_delivery(
        self, excluded_sessions: frozenset[str], now: datetime
    ) -> ClaimedDelivery | None:
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
        earlier = aliased(DeliveryRecord, name="earlier")
        waiting = (
            select(earlier.id)
            .where(
                earlier.target_session_id == DeliveryRecord.target_session_id,
                or_(
                    earlier.status == "pending",
                    and_(earlier.status == "unknown", earlier.attempt_count > 0),
                ),
                earlier.deleted_at.is_(None),
                self._dispatchable(earlier),
                literal_column("earlier.rowid") < insertion_order("deliveries"),
            )
            .exists()
        )
        candidate = self.session.scalar(
            select(DeliveryRecord)
            .where(
                DeliveryRecord.status == "pending",
                DeliveryRecord.deleted_at.is_(None),
                self._dispatchable(DeliveryRecord),
                DeliveryRecord.target_session_id.not_in(excluded_sessions),
                or_(
                    DeliveryRecord.next_attempt_at.is_(None),
                    time_at_or_before(DeliveryRecord.next_attempt_at, now),
                ),
                ~busy,
                ~waiting,
            )
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
            .values(
                status="submitting",
                updated_at=now,
                attempt_count=DeliveryRecord.attempt_count + 1,
                next_attempt_at=None,
            )
        )
        if changed != 1:
            return None
        return ClaimedDelivery(
            candidate.room_id,
            SQLAlchemyRoomRepository(self.session, candidate.channel_id).room(candidate.room_id),
            SQLAlchemyMessageRepository(self.session, candidate.channel_id).message(
                candidate.room_id, candidate.message_id
            ),
            delivery_from_model(candidate),
            candidate.channel_id,
            SQLAlchemyRoomRepository(self.session, candidate.channel_id).working_path(
                candidate.room_id
            ),
            self.session.execute(
                select(MemberRecord.name).where(
                    MemberRecord.room_id == candidate.room_id,
                    MemberRecord.channel_id == candidate.channel_id,
                    MemberRecord.id == candidate.target_member_id,
                )
            ).scalar_one(),
            attempt_count=candidate.attempt_count,
        )

    def defer_delivery(self, work: ClaimedDelivery, reason: str, next_attempt_at: datetime) -> bool:
        return (
            self._update(
                update(DeliveryRecord)
                .where(
                    DeliveryRecord.room_id == work.room_id,
                    DeliveryRecord.id == work.delivery.id,
                    DeliveryRecord.status == "submitting",
                    DeliveryRecord.deleted_at.is_(None),
                    DeliveryRecord.client_message_id == work.delivery.client_message_id,
                    DeliveryRecord.attempt_count == work.attempt_count,
                )
                .values(
                    status="pending",
                    updated_at=datetime.now(UTC),
                    next_attempt_at=next_attempt_at,
                    note=reason,
                    error=None,
                )
            )
            == 1
        )

    def finish_delivery(self, room_id: str, delivery: Delivery) -> bool:
        values = delivery_values(delivery)
        for field in ("id", "target_member_id", "target_session_id", "client_message_id"):
            del values[field]
        values["next_attempt_at"] = (
            datetime.now(UTC)
            if delivery.status == "queued" and delivery.submission_method == "queue"
            else None
        )
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

    def claim_activation_work(
        self, excluded_sessions: frozenset[str], now: datetime
    ) -> ActivationWork | None:
        busy = aliased(DeliveryRecord)
        candidate = self.session.scalar(
            select(DeliveryRecord)
            .where(
                DeliveryRecord.status == "queued",
                DeliveryRecord.submission_method == "queue",
                DeliveryRecord.attempt_count > 0,
                DeliveryRecord.queued_submission_id.is_not(None),
                DeliveryRecord.receipt_metadata.is_not(None),
                DeliveryRecord.activation_attempted_at.is_(None),
                DeliveryRecord.deleted_at.is_(None),
                DeliveryRecord.next_attempt_at.is_not(None),
                time_at_or_before(DeliveryRecord.next_attempt_at, now),
                DeliveryRecord.target_session_id.not_in(excluded_sessions),
                self._dispatchable(DeliveryRecord),
                ~select(busy.id)
                .where(
                    busy.target_session_id == DeliveryRecord.target_session_id,
                    busy.status == "submitting",
                    busy.deleted_at.is_(None),
                )
                .exists(),
            )
            .order_by(DeliveryRecord.next_attempt_at, insertion_order("deliveries"))
            .limit(1)
        )
        if candidate is None or candidate.queued_submission_id is None:
            return None
        candidate.next_attempt_at = now + timedelta(seconds=2)
        return ActivationWork(
            candidate.target_session_id, candidate.client_message_id, candidate.queued_submission_id
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
                    DeliveryRecord.submission_method.is_distinct_from("steer"),
                    DeliveryRecord.deleted_at.is_(None),
                    DeliveryRecord.queued_submission_id == head.id,
                    DeliveryRecord.client_message_id == head.client_message_id,
                    DeliveryRecord.activation_attempted_at.is_(None),
                    select(MemberRecord.id)
                    .where(
                        MemberRecord.room_id == DeliveryRecord.room_id,
                        MemberRecord.channel_id == DeliveryRecord.channel_id,
                        MemberRecord.id == DeliveryRecord.target_member_id,
                        MemberRecord.session_id == session_id,
                        MemberRecord.deleted_at.is_(None),
                    )
                    .exists(),
                    select(ChannelRecord.id)
                    .where(
                        ChannelRecord.room_id == DeliveryRecord.room_id,
                        ChannelRecord.id == DeliveryRecord.channel_id,
                        ChannelRecord.archived_at.is_(None),
                    )
                    .exists(),
                )
                .values(activation_attempted_at=datetime.now(UTC), next_attempt_at=None)
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
                DeliveryRecord.status.in_(UNCONFIRMED_DELIVERY_STATUSES),
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
                DeliveryRecord.status.in_(UNCONFIRMED_DELIVERY_STATUSES),
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

    def confirm_queue(self, session_id: str, client_message_id: str, receipt: QueueReceipt) -> None:
        if (
            receipt.metadata.get("id") != receipt.id
            or receipt.metadata.get("clientUserMessageId") != client_message_id
        ):
            raise ValueError("Queue evidence does not match the original request")
        now = datetime.now(UTC)
        self._update(
            update(DeliveryRecord)
            .where(
                DeliveryRecord.target_session_id == session_id,
                DeliveryRecord.client_message_id == client_message_id,
                DeliveryRecord.status == "unknown",
                DeliveryRecord.attempt_count > 0,
                DeliveryRecord.submission_method.is_distinct_from("steer"),
                DeliveryRecord.deleted_at.is_(None),
            )
            .values(
                status="queued",
                submission_method="queue",
                queued_submission_id=receipt.id,
                receipt_metadata={
                    key: value
                    for key, value in receipt.metadata.items()
                    if key not in {"id", "clientUserMessageId"}
                },
                queued_at=now,
                updated_at=now,
                note=QUEUED_NOTE,
                error=None,
                next_attempt_at=now,
            )
        )
