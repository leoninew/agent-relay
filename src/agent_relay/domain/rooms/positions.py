from collections.abc import Iterable

from agent_relay.domain.rooms.errors import RoomNotFoundError


def require_subscribed_topic(topic_id: str | None, subscriptions: set[str]) -> None:
    if topic_id is not None and topic_id not in subscriptions:
        raise RoomNotFoundError("话题不存在或未订阅", code="topic_not_subscribed")


def position_updates(
    subscriptions: set[str], topic_id: str | None, messages: Iterable[tuple[int, list[str]]]
) -> dict[str, int]:
    positions: dict[str, int] = {}
    for seq, topic_ids in messages:
        for candidate in subscriptions.intersection(topic_ids):
            if topic_id is None or candidate == topic_id:
                positions[candidate] = max(positions.get(candidate, 0), seq)
    return positions
