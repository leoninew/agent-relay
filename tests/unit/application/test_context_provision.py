from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest

from agent_relay.application.context.contracts import ContextMessage, ContextQuery
from agent_relay.application.context.ports import ContextRepository
from agent_relay.application.context.service import ContextService
from agent_relay.application.rooms.views import TopicPosition
from agent_relay.domain.rooms.context import VisibilityScope
from agent_relay.domain.rooms.errors import RoomNotFoundError


@dataclass
class MemoryContextRepository:
    messages: list[ContextMessage] = field(default_factory=list)
    more: bool = False
    fail_result: bool = False
    visibility: VisibilityScope | None = None
    records: list[tuple[str, list[str], dict[str, int], datetime]] = field(default_factory=list)

    def subscriptions(self, room_id: str, member_id: str) -> set[str]:
        return {"frontend", "backend"}

    def select_messages(
        self, room_id: str, request: ContextQuery, scope: VisibilityScope
    ) -> tuple[list[ContextMessage], bool]:
        self.visibility = scope
        return self.messages, self.more

    def record_provision(
        self,
        room_id: str,
        member_id: str,
        request: ContextQuery,
        messages: list[ContextMessage],
        updates: dict[str, int],
        query_id: str,
        provided_at: datetime,
    ) -> None:
        self.records.append((query_id, [message.id for message in messages], updates, provided_at))

    def load_positions(self, room_id: str, member_id: str) -> list[TopicPosition]:
        if self.fail_result:
            raise RuntimeError("result unavailable")
        return []


class MemoryContextScope:
    def __init__(self, repository: MemoryContextRepository) -> None:
        self.repository = repository

    @contextmanager
    def read(self) -> Iterator[ContextRepository]:
        yield self.repository

    @contextmanager
    def write(self) -> Iterator[ContextRepository]:
        previous = list(self.repository.records)
        try:
            yield self.repository
        except BaseException:
            self.repository.records = previous
            raise


def message(seq: int, topics: list[str]) -> ContextMessage:
    return ContextMessage(
        id=f"message-{seq}",
        seq=seq,
        sender_id="sender",
        sender_name="Sender",
        content="Context",
        topic_ids=topics,
        mentioned_member_ids=[],
        reply_to_message_id=None,
        created_at=datetime.now(UTC),
    )


@pytest.mark.parametrize("forward", [False, True])
def test_provision_records_only_returned_messages_and_subscribed_topic_maxima(
    forward: bool,
) -> None:
    repository = MemoryContextRepository(
        messages=[message(3, ["frontend", "private"]), message(7, ["frontend", "backend"])],
        more=True,
    )
    request = ContextQuery(after_seq=0) if forward else ContextQuery()
    before = datetime.now(UTC)
    result = ContextService(MemoryContextScope(repository)).provide("room", "member", request)
    assert result.query_id is not None and len(repository.records) == 1
    query_id, provided, updates, provided_at = repository.records[0]
    assert query_id == result.query_id and provided == ["message-3", "message-7"]
    assert updates == {"frontend": 7, "backend": 7}
    assert before <= provided_at <= datetime.now(UTC)
    assert repository.visibility == VisibilityScope.for_member("member", {"frontend", "backend"})
    assert result.next_before_seq == (None if forward else 3)
    assert result.next_after_seq == (7 if forward else None)


def test_empty_provision_does_not_create_audit_or_positions() -> None:
    repository = MemoryContextRepository()
    result = ContextService(MemoryContextScope(repository)).provide(
        "room", "member", ContextQuery()
    )
    assert result.query_id is None and result.messages == [] and not repository.records
    assert result.next_before_seq is None and result.next_after_seq is None


def test_unsubscribed_topic_is_rejected_before_message_selection() -> None:
    repository = MemoryContextRepository()
    with pytest.raises(RoomNotFoundError):
        ContextService(MemoryContextScope(repository)).provide(
            "room", "member", ContextQuery(topic_id="private")
        )
    assert repository.visibility is None and not repository.records


def test_failed_result_rolls_back_the_whole_provision() -> None:
    repository = MemoryContextRepository(messages=[message(7, ["frontend"])], fail_result=True)
    with pytest.raises(RuntimeError, match="result unavailable"):
        ContextService(MemoryContextScope(repository)).provide("room", "member", ContextQuery())
    assert not repository.records
