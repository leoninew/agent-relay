from agent_relay.domain.rooms.models import RoomModel


class UploadedImage(RoomModel):
    id: str
    url: str
    markdown: str
    media_type: str
    size: int
