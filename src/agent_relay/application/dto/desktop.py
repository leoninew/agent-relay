from dataclasses import dataclass


@dataclass(frozen=True)
class ShutdownNotificationTarget:
    room_id: str
    agent_member_ids: tuple[str, ...]
