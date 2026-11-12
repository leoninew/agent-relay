from __future__ import annotations

import logging
from datetime import UTC, datetime

from agent_relay.application.delivery.ports import (
    ActivationRejected,
    ClaimedDelivery,
    DeliveryRepository,
    QueueDriver,
    QueueRejected,
    QueueRequest,
)
from agent_relay.domain.rooms.delivery import (
    PROCESSING_FAILURE,
    QUEUED_NOTE,
    REJECTED_SUBMISSION,
    UNCERTAIN_SUBMISSION,
    queue_accepted,
    submission_failed,
)


class DeliveryService:
    def __init__(
        self,
        store: DeliveryRepository,
        driver: QueueDriver,
        logger: logging.Logger,
    ) -> None:
        self.store = store
        self.driver = driver
        self.logger = logger
        self.history_cursors: dict[str, str | None] = {}

    def recover(self) -> None:
        self.store.interrupt_submissions()

    def submit(self, work: ClaimedDelivery) -> None:
        try:
            self._submit(work)
        except Exception:
            self.logger.exception("Delivery processing failed delivery=%s", work.delivery.id)
            delivery = submission_failed(work.delivery, PROCESSING_FAILURE, datetime.now(UTC))
            self.store.finish_delivery(work.room_id, delivery)

    def _submit(self, work: ClaimedDelivery) -> None:
        delivery = work.delivery
        sender = f"{work.message.sender_name}（{work.message.sender_id}）"
        created_at = work.message.model_dump(mode="json", by_alias=True)["createdAt"]
        text = (
            f"roomId: {work.room_id}\n"
            f"messageId: {work.message.id}\n"
            f"seq: {work.message.seq}\n"
            f"createdAt: {created_at}\n"
            f"sender: {sender}\n\n"
            f"{work.message.content}"
        )
        try:
            receipt = self.driver.enqueue(
                delivery.target_session_id,
                delivery.client_message_id,
                QueueRequest(text, work.room.project_path, work.message.capabilities),
            )
            delivery = queue_accepted(delivery, receipt.id, receipt.metadata, datetime.now(UTC))
        except QueueRejected:
            delivery = submission_failed(delivery, REJECTED_SUBMISSION, datetime.now(UTC))
            self.logger.exception("Queue rejected delivery=%s", delivery.id)
        except Exception:
            delivery = submission_failed(delivery, UNCERTAIN_SUBMISSION, datetime.now(UTC))
            self.logger.exception("Queue result unknown delivery=%s", delivery.id)
        saved = self.store.finish_delivery(work.room_id, delivery)
        if saved and delivery.status == "queued":
            self.activate_after_submission(delivery.target_session_id, delivery.client_message_id)

    def activate_after_submission(self, session_id: str, client_message_id: str) -> None:
        """Only a new submission can trigger one guarded start of an existing FIFO head."""
        try:
            head = self.driver.activation_candidate(session_id)
            if head is None or not self.store.claim_activation(session_id, head):
                self.store.delivery_note(
                    session_id,
                    client_message_id,
                    QUEUED_NOTE,
                )
                return
            self.driver.activate(session_id, head.id)
            self.store.delivery_note(
                session_id,
                head.client_message_id or client_message_id,
                "已请求启动原队列首项，等待接收确认",
            )
        except ActivationRejected:
            # A competing consumer may already have taken this exact item. Never
            # start another item or repeat add in response to the rejection.
            self.store.delivery_note(
                session_id,
                client_message_id,
                "已入队；启动请求未被接受，继续核验原会话输入",
            )
            self.logger.info("Queue activation rejected session=%s", session_id)
        except Exception:
            self.store.delivery_note(
                session_id,
                client_message_id,
                "已入队；无法确认队列启动结果，不重复启动或提交",
            )
            self.logger.exception("Queue activation outcome unknown session=%s", session_id)

    def observe(self, session_id: str, client_message_ids: set[str]) -> None:
        try:
            latest = self.driver.read_input_page(session_id)
            inputs = list(latest.inputs)
            cursor = self.history_cursors.get(session_id)
            if cursor is not None:
                older = self.driver.read_input_page(session_id, cursor)
                inputs.extend(older.inputs)
                self.history_cursors[session_id] = older.next_cursor
            else:
                self.history_cursors[session_id] = latest.next_cursor
            for received in inputs:
                if received.client_message_id in client_message_ids:
                    self.store.confirm_input(session_id, received)
        except Exception:
            # A missing or unreadable history page never proves rejection or
            # receipt and never causes a new queue/add or queue/start.
            self.logger.exception("Input receipt observation unavailable session=%s", session_id)
