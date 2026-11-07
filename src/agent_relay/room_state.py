from dataclasses import dataclass, field

from agent_relay.room_models import Member, Message, Room, Session, Topic


@dataclass
class RoomState:
    room: Room
    topics: list[Topic] = field(default_factory=list)
    members: list[Member] = field(default_factory=list)
    messages: list[Message] = field(default_factory=list)
    sessions: list[Session] = field(default_factory=list)
