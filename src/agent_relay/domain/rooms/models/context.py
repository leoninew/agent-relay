from dataclasses import dataclass


@dataclass(frozen=True)
class VisibilityScope:
    publisher_id: str
    delivery_member_id: str
    topic_ids: frozenset[str]

    @classmethod
    def for_member(cls, member_id: str, subscriptions: set[str]) -> "VisibilityScope":
        return cls(member_id, member_id, frozenset(subscriptions))
