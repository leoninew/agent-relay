from sqlalchemy import select, true
from sqlalchemy.orm import Session

from conflua.domain.rooms.errors import RoomNotFoundError
from conflua.infrastructure.persistence.models import ChannelRecord


class SQLAlchemyChannelScope:
    def __init__(self, session: Session, channel_id: str | None = None) -> None:
        self.session = session
        self.channel_id = channel_id
        self._defaults: dict[str, str] = {}

    def channel_id_for(self, room_id: str) -> str:
        if self.channel_id is not None:
            return self.channel_id
        if room_id not in self._defaults:
            channel_id = self.session.scalar(
                select(ChannelRecord.id).where(
                    ChannelRecord.room_id == room_id,
                    ChannelRecord.is_default == true(),
                )
            )
            if channel_id is None:
                raise RoomNotFoundError("频道不存在", code="channel_not_found")
            self._defaults[room_id] = channel_id
        return self._defaults[room_id]
