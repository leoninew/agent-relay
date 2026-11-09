from dataclasses import dataclass, field

from agent_relay.domain.rooms.models import Member, Room, Session, Topic


@dataclass
class RoomState:
    room: Room
    topics: list[Topic] = field(default_factory=list)
    members: list[Member] = field(default_factory=list)
    sessions: list[Session] = field(default_factory=list)
