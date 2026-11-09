from dataclasses import dataclass
from typing import Literal

RoomChangeKind = Literal["room", "topic", "member", "session", "message", "delivery", "position"]


@dataclass(frozen=True)
class RoomChange:
    room_id: str
    kind: RoomChangeKind
    entity_id: str
    message_id: str | None = None
