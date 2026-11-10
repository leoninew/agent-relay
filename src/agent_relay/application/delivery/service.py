from __future__ import annotations

import logging
from datetime import UTC, datetime

from agent_relay.application.delivery.ports import (
    ActivationRejected,
    ClaimedDelivery,
    DeliveryStore,
    QueueDriver,
    QueueRejected,
)


class DeliveryService:
    def __init__(
        self,
        store: DeliveryStore,
        driver: QueueDriver,
        logger: logging.Logger,
    ) -> None:
        self.store = store
        self.driver = driver
        self.logger = logger
        self.history_cursors: dict[str, str | None] = {}

    def submit(self, work: ClaimedDelivery) -> None:
        try:
            self._submit(work)
        except Exception:
            self.logger.exception("Delivery processing failed delivery=%s", work.delivery.id)
            delivery = work.delivery.model_copy(deep=True)
            delivery.status = "unknown"
            delivery.error = "本次投递处理失败，无法确认入队结果；不会自动重发"
            delivery.updated_at = datetime.now(UTC)
            # Only an unfinished submission can change. A saved queue receipt or
            # received input must survive an error in the later activation step.
            self.store.finish_delivery(work.room_id, delivery)

    def _submit(self, work: ClaimedDelivery) -> None:
        delivery = work.delivery.model_copy(deep=True)
        sender = f"{work.message.sender_name}（{work.message.sender_id}）"
        text = f"roomId: {work.room_id}\n发送者: {sender}\n\n{work.message.content}"
        try:
            receipt = self.driver.enqueue(
                delivery.target_session_id,
                delivery.client_message_id,
                text,
            )
            delivery.status = "queued"
            delivery.queued_at = datetime.now(UTC)
            delivery.note = "已入队，等待原会话消费；如已中断，请在原 Codex 会话继续"
            delivery.queued_submission_id = receipt.id
            delivery.receipt = receipt.metadata
        except QueueRejected:
            delivery.status = "rejected"
            delivery.error = "Codex 明确拒绝本次入队"
            self.logger.exception("Queue rejected delivery=%s", delivery.id)
        except Exception:
            delivery.status = "unknown"
            delivery.error = "无法确认入队结果；不会自动重发"
            self.logger.exception("Queue result unknown delivery=%s", delivery.id)
        delivery.updated_at = datetime.now(UTC)
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
                    "已入队，等待原会话消费；如已中断，请在原 Codex 会话继续",
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
