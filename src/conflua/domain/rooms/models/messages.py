from datetime import datetime

from conflua.domain.rooms.models.base import RoomModel
from conflua.domain.rooms.models.capabilities import CapabilityReference
from conflua.domain.rooms.models.delivery import Delivery


class Message(RoomModel):
    id: str
    publication_id: str | None = None
    seq: int
    sender_id: str
    sender_name: str
    content: str
    capabilities: tuple[CapabilityReference, ...] = ()
    topic_ids: list[str]
    mentioned_member_ids: list[str]
    recipient_ids: list[str]
    reply_to_message_id: str | None = None
    created_at: datetime
    deliveries: list[Delivery]
