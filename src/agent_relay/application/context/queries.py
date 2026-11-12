from agent_relay.application.context.ports import ContextReadRepository
from agent_relay.application.dto.context import MemberCatalog
from agent_relay.application.dto.positions import TopicPosition
from agent_relay.application.transactions import RepositoryScope


class ContextReader:
    def __init__(self, repositories: RepositoryScope[ContextReadRepository]) -> None:
        self.repositories = repositories

    def catalog(self, room_id: str, member_id: str) -> MemberCatalog:
        with self.repositories.read() as repository:
            return repository.catalog(room_id, member_id)

    def positions(self, room_id: str, member_id: str) -> list[TopicPosition]:
        with self.repositories.read() as repository:
            repository.subscriptions(room_id, member_id)
            return repository.load_positions(room_id, member_id)
