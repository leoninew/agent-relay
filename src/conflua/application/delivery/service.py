from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from conflua.application.delivery.ports import (
    ActivationRejected,
    DeliveryDriver,
    DeliveryRepository,
    InputHistoryUnavailable,
    SubmissionDeferred,
    SubmissionRejected,
    SubmissionUnknown,
)
from conflua.application.dto.delivery import (
    ActivationWork,
    ClaimedDelivery,
    DeliveryOutcome,
    QueueHead,
    QueueRequest,
    SteerReceipt,
)
from conflua.application.images.message_text import ImageMessageText
from conflua.application.images.ports import ImageStore
from conflua.domain.rooms.delivery import (
    QUEUED_NOTE,
    REJECTED_SUBMISSION,
    UNCERTAIN_SUBMISSION,
    queue_accepted,
    steer_accepted,
    submission_failed,
)
from conflua.domain.rooms.inline_skills import message_text
from conflua.domain.rooms.models import SubmissionFailure

RETRY_BASE_SECONDS = 1
RETRY_MAX_SECONDS = 30


class DeliveryService:
    def __init__(
        self,
        store: DeliveryRepository,
        driver: DeliveryDriver,
        logger: logging.Logger,
        images: ImageStore | None = None,
        *,
        request_presence: Callable[[str], None] | None = None,
    ) -> None:
        self.store = store
        self.driver = driver
        self.logger = logger
        self.images = images
        self.request_presence = request_presence
        self.history_cursors: dict[str, str | None] = {}
        self.unavailable_history_sessions: set[str] = set()
        self.queue_cursors: dict[str, str | None] = {}
        self.unavailable_queue_sessions: set[str] = set()

    def recover(self) -> None:
        self.store.interrupt_submissions()

    def submit(self, work: ClaimedDelivery) -> DeliveryOutcome | None:
        try:
            available = self.store.delivery_available(work)
        except Exception:
            self.logger.exception("Unable to check delivery target delivery=%s", work.delivery.id)
            return self.complete(
                DeliveryOutcome(work, retry_reason="暂时无法读取投递目标，稍后重试")
            )
        if not available:
            delivery = submission_failed(
                work.delivery,
                SubmissionFailure("rejected", "投递目标频道当前不可用"),
                datetime.now(UTC),
            )
            return self.complete(DeliveryOutcome(work, delivery))
        try:
            request = self._request(work)
        except Exception:
            self.logger.exception("Unable to prepare delivery delivery=%s", work.delivery.id)
            delivery = submission_failed(
                work.delivery,
                SubmissionFailure("rejected", "无法准备消息内容，未提交外部输入"),
                datetime.now(UTC),
            )
            return self.complete(DeliveryOutcome(work, delivery))
        return self.complete(self._submit(work, request))

    def _request(self, work: ClaimedDelivery) -> QueueRequest:
        sender = f"{work.message.sender_name}（{work.message.sender_id}）"
        recipient = f"{work.target_member_name}（{work.delivery.target_member_id}）"
        created_at = work.message.model_dump(mode="json", by_alias=True)["createdAt"]
        refer_to = (
            f"referTo: {work.message.reply_to_message_id}\n"
            if work.message.reply_to_message_id
            else ""
        )
        text_output = ImageMessageText(
            self.images.for_channel(work.channel_id) if self.images else None, work.channel_id
        )
        content = text_output.text(
            work.room_id, message_text(work.message.content, work.message.capabilities)
        )
        text = (
            f"roomId: {work.room_id}\n"
            f"channelId: {work.channel_id}\n"
            f"messageId: {work.message.id}\n"
            f"seq: {work.message.seq}\n"
            f"createdAt: {created_at}\n"
            f"sender: {sender}\n"
            f"recipient: {recipient}\n"
            f"{refer_to}\n"
            f"{content}"
        )
        return QueueRequest(text, work.working_path, work.message.capabilities)

    def _submit(self, work: ClaimedDelivery, request: QueueRequest) -> DeliveryOutcome:
        delivery = work.delivery
        try:
            receipt = self.driver.submit(
                delivery.target_session_id,
                delivery.client_message_id,
                request,
            )
            if isinstance(receipt, SteerReceipt):
                delivery = steer_accepted(delivery, receipt.turn_id, datetime.now(UTC))
            else:
                delivery = queue_accepted(delivery, receipt.id, receipt.metadata, datetime.now(UTC))
                if receipt.note:
                    delivery.note = receipt.note
        except SubmissionDeferred as exc:
            self.logger.info("Submission deferred delivery=%s reason=%s", delivery.id, exc)
            return DeliveryOutcome(work, retry_reason=str(exc))
        except SubmissionRejected as exc:
            delivery = submission_failed(
                delivery,
                SubmissionFailure("rejected", str(exc) or REJECTED_SUBMISSION.error),
                datetime.now(UTC),
                exc.method,
            )
            self.logger.exception("Submission rejected delivery=%s", delivery.id)
        except SubmissionUnknown as exc:
            delivery = submission_failed(
                delivery, UNCERTAIN_SUBMISSION, datetime.now(UTC), exc.method
            )
            self.logger.exception("Submission result unknown delivery=%s", delivery.id)
        except Exception:
            delivery = submission_failed(delivery, UNCERTAIN_SUBMISSION, datetime.now(UTC))
            self.logger.exception("Submission result unknown delivery=%s", delivery.id)
        return DeliveryOutcome(work, delivery)

    def complete(self, outcome: DeliveryOutcome) -> DeliveryOutcome | None:
        work = outcome.work
        delivery = outcome.delivery
        try:
            if delivery is None:
                delay = min(
                    RETRY_MAX_SECONDS,
                    RETRY_BASE_SECONDS * 2 ** min(max(0, work.attempt_count - 1), 6),
                )
                self.store.defer_delivery(
                    work,
                    outcome.retry_reason or "投递暂时不可用，稍后重试",
                    datetime.now(UTC) + timedelta(seconds=delay),
                )
                return None
            saved = self.store.finish_delivery(work.room_id, delivery)
        except Exception:
            self.logger.exception("Unable to save delivery outcome delivery=%s", work.delivery.id)
            return outcome
        if saved and delivery.status == "queued" and delivery.submission_method == "queue":
            self.activate_after_submission(
                delivery.target_session_id, delivery.client_message_id, delivery.note
            )
        return None

    def activate_after_submission(
        self,
        session_id: str,
        client_message_id: str,
        submission_note: str | None = None,
        expected_head: QueueHead | None = None,
    ) -> None:
        """Start a saved FIFO head only after its one-time activation claim."""
        prefix = f"{submission_note}；" if submission_note else ""
        try:
            head = self.driver.activation_candidate(session_id)
            if head is None or (expected_head is not None and head != expected_head):
                self.store.delivery_note(
                    session_id,
                    client_message_id,
                    submission_note or QUEUED_NOTE,
                )
                return
            if not self.store.claim_activation(session_id, head):
                self.store.delivery_note(
                    session_id, client_message_id, submission_note or QUEUED_NOTE
                )
                return
            self.driver.activate(session_id, head.id)
            self.store.delivery_note(
                session_id,
                head.client_message_id or client_message_id,
                prefix + "已请求启动原队列首项，等待接收确认",
            )
        except ActivationRejected:
            # A competing consumer may already have taken this exact item. Never
            # start another item or repeat add in response to the rejection.
            self.store.delivery_note(
                session_id,
                client_message_id,
                prefix + "已入队；启动请求未被接受，继续核验原会话输入",
            )
            self.logger.info("Queue activation rejected session=%s", session_id)
        except Exception:
            self.store.delivery_note(
                session_id,
                client_message_id,
                prefix + "已入队；无法确认队列启动结果，不重复启动或提交",
            )
            self.logger.exception("Queue activation outcome unknown session=%s", session_id)

    def check_activation(self, work: ActivationWork) -> None:
        self.activate_after_submission(
            work.session_id,
            work.client_message_id,
            expected_head=QueueHead(work.queued_submission_id, work.client_message_id),
        )

    def observe(self, session_id: str, client_message_ids: set[str]) -> None:
        self._observe_queue(session_id, client_message_ids)
        confirmed = False
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
            self.unavailable_history_sessions.discard(session_id)
            for received in inputs:
                if received.client_message_id in client_message_ids and self.store.confirm_input(
                    session_id, received
                ):
                    confirmed = True
        except InputHistoryUnavailable as exc:
            if session_id not in self.unavailable_history_sessions:
                self.logger.info(
                    "Input receipt observation unavailable session=%s reason=%s", session_id, exc
                )
                self.unavailable_history_sessions.add(session_id)

        except Exception as exc:
            if session_id not in self.unavailable_history_sessions:
                self.logger.warning(
                    "Input receipt observation unavailable session=%s reason=%s",
                    session_id,
                    exc,
                )
                self.unavailable_history_sessions.add(session_id)

        if confirmed and self.request_presence is not None:
            try:
                self.request_presence(session_id)
            except Exception:
                self.logger.exception("Unable to request member presence session=%s", session_id)

    def _observe_queue(self, session_id: str, client_message_ids: set[str]) -> None:
        try:
            latest = self.driver.read_queue_page(session_id)
            inputs = list(latest.inputs)
            cursor = self.queue_cursors.get(session_id)
            if cursor is not None:
                older = self.driver.read_queue_page(session_id, cursor)
                inputs.extend(older.inputs)
                self.queue_cursors[session_id] = older.next_cursor
            else:
                self.queue_cursors[session_id] = latest.next_cursor
            self.unavailable_queue_sessions.discard(session_id)
            for queued in inputs:
                if queued.client_message_id in client_message_ids:
                    self.store.confirm_queue(session_id, queued.client_message_id, queued.receipt)
        except Exception as exc:
            if session_id not in self.unavailable_queue_sessions:
                self.logger.warning(
                    "Queue receipt observation unavailable session=%s reason=%s", session_id, exc
                )
                self.unavailable_queue_sessions.add(session_id)
