from dataclasses import dataclass
from typing import Protocol

from agent_relay.domain.rooms.models import (
    CapabilityReference,
    Delivery,
    Message,
    Room,
    SubmissionMethod,
)


class QueueRejected(RuntimeError):
    pass


class ActivationRejected(RuntimeError):
    pass


class SubmissionRejected(RuntimeError):
    def __init__(self, message: str, method: SubmissionMethod | None = None) -> None:
        super().__init__(message)
        self.method = method


class SubmissionUnknown(RuntimeError):
    def __init__(self, message: str, method: SubmissionMethod | None = None) -> None:
        super().__init__(message)
        self.method = method


@dataclass(frozen=True)
class QueueRequest:
    text: str
    project_path: str
    capabilities: tuple[CapabilityReference, ...] = ()


@dataclass(frozen=True)
class QueueReceipt:
    id: str
    metadata: dict[str, object]
    note: str | None = None


@dataclass(frozen=True)
class SteerReceipt:
    turn_id: str


@dataclass(frozen=True)
class QueueHead:
    id: str
    client_message_id: str | None


@dataclass(frozen=True)
class ReceivedInput:
    client_message_id: str
    item_id: str
    turn_id: str


@dataclass(frozen=True)
class InputPage:
    inputs: tuple[ReceivedInput, ...]
    next_cursor: str | None


@dataclass(frozen=True)
class ClaimedDelivery:
    room_id: str
    room: Room
    message: Message
    delivery: Delivery


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
