from datetime import datetime

from agent_relay.domain.rooms.models import RoomModel


class TopicPosition(RoomModel):
    member_id: str
    topic_id: str
    seq: int
    updated_at: datetime | None
    later_count: int
