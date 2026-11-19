from datetime import UTC, datetime

from conflua.application.context.ports import ContextRepository
from conflua.application.dto.context import ContextQuery, ContextResult
from conflua.application.transactions import RepositoryScope
from conflua.domain.identifiers import new_tsid
from conflua.domain.rooms.models import VisibilityScope
from conflua.domain.rooms.positions import position_updates, require_subscribed_topic


class ContextService:
    def __init__(self, scope: RepositoryScope[ContextRepository]) -> None:
        self.scope = scope

    def provide(self, room_id: str, member_id: str, request: ContextQuery) -> ContextResult:
        with self.scope.write() as repository:
            subscriptions = repository.subscriptions(room_id, member_id)
            require_subscribed_topic(request.topic_id, subscriptions)
            scope = VisibilityScope.for_member(member_id, subscriptions)
            messages, more = repository.select_messages(room_id, request, scope)
            query_id = None
            if messages:
                query_id = new_tsid()
                updates = position_updates(
                    subscriptions,
                    request.topic_id,
                    ((message.seq, message.topic_ids) for message in messages),
                )
                repository.record_provision(
                    room_id, member_id, request, messages, updates, query_id, datetime.now(UTC)
                )
            forward = request.after_seq is not None
            return ContextResult(
                query_id=query_id,
                messages=messages,
                has_more=more,
                next_before_seq=messages[0].seq if more and not forward else None,
                next_after_seq=messages[-1].seq if more and forward else None,
                positions=repository.load_positions(room_id, member_id),
            )
