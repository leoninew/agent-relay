from dataclasses import dataclass

from agent_relay.domain.rooms.models import CapabilityReference, Delivery, Message, Room


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
