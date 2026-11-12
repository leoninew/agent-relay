from datetime import datetime

from agent_relay.domain.rooms.models.base import RoomModel
from agent_relay.domain.rooms.models.capabilities import CapabilityReference
from agent_relay.domain.rooms.models.delivery import Delivery


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
