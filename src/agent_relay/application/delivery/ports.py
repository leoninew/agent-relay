from typing import Protocol

from agent_relay.application.dto.delivery import (
    ClaimedDelivery,
    InputPage,
    QueueHead,
    QueueReceipt,
    QueueRequest,
    ReceivedInput,
    SteerReceipt,
)
from agent_relay.domain.rooms.models import Delivery, SubmissionMethod


class QueueRejected(RuntimeError):
    pass


class ActivationRejected(RuntimeError):
    pass


class InputHistoryUnavailable(RuntimeError):
    pass


class SubmissionRejected(RuntimeError):
    def __init__(self, message: str, method: SubmissionMethod | None = None) -> None:
        super().__init__(message)
        self.method = method


class SubmissionUnknown(RuntimeError):
    def __init__(self, message: str, method: SubmissionMethod | None = None) -> None:
        super().__init__(message)
        self.method = method


class QueueDriver(Protocol):
    def enqueue(
        self, thread_id: str, client_message_id: str, request: QueueRequest
    ) -> QueueReceipt: ...
    def delete(self, thread_id: str, queued_submission_id: str) -> bool: ...
    def activation_candidate(self, thread_id: str) -> QueueHead | None: ...
    def activate(self, thread_id: str, queued_submission_id: str) -> str: ...
    def read_input_page(self, thread_id: str, cursor: str | None = None) -> InputPage: ...


class DeliveryDriver(QueueDriver, Protocol):
    def submit(
        self, thread_id: str, client_message_id: str, request: QueueRequest
    ) -> QueueReceipt | SteerReceipt: ...


class DeliveryRepository(Protocol):
    def interrupt_submissions(self) -> None: ...
    def claim_delivery(self) -> ClaimedDelivery | None: ...
    def finish_delivery(self, room_id: str, delivery: Delivery) -> bool: ...
    def claim_activation(self, session_id: str, head: QueueHead) -> bool: ...
    def delivery_note(self, session_id: str, client_message_id: str, note: str) -> None: ...
    def unconfirmed_inputs(self) -> dict[str, set[str]]: ...
    def confirm_input(self, session_id: str, received: ReceivedInput) -> None: ...
