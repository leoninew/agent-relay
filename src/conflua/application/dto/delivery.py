from dataclasses import dataclass

from conflua.domain.rooms.models import (
    CapabilityReference,
    Delivery,
    Message,
    Room,
)


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
class QueuedInput:
    client_message_id: str
    receipt: QueueReceipt


@dataclass(frozen=True)
class QueuePage:
    inputs: tuple[QueuedInput, ...]
    next_cursor: str | None


@dataclass(frozen=True)
class ClaimedDelivery:
    room_id: str
    room: Room
    message: Message
    delivery: Delivery
    channel_id: str
    working_path: str
    attempt_count: int = 1


@dataclass(frozen=True)
class DeliveryOutcome:
    work: ClaimedDelivery
    delivery: Delivery | None = None
    retry_reason: str | None = None


@dataclass(frozen=True)
class ActivationWork:
    session_id: str
    client_message_id: str
    queued_submission_id: str
