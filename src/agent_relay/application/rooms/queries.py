from agent_relay.application.dto.messages import MessagePage, MessageQueuePage
from agent_relay.application.dto.rooms import RoomEventPage, RoomMetadata, RoomSnapshot
from agent_relay.application.rooms.ports import RoomData
from agent_relay.application.transactions import RepositoryScope
from agent_relay.domain.rooms.models import Member, Message, Room


class RoomReader:
    def __init__(self, repositories: RepositoryScope[RoomData]) -> None:
        self.repositories = repositories

    def rooms(self) -> list[Room]:
        with self.repositories.read() as repository:
            return repository.rooms()

    def member_for_session(self, room_id: str, session_id: str) -> Member:
        with self.repositories.read() as repository:
            return repository.member_for_session(room_id, session_id)

    def metadata(self, room_id: str) -> RoomMetadata:
        with self.repositories.read() as repository:
            return repository.metadata(room_id)

    def snapshot(
        self,
        room_id: str,
        topic_id: str | None = None,
        *,
        member_id: str | None = None,
        keyword: str | None = None,
        before_seq: int | None = None,
        limit: int = 50,
    ) -> RoomSnapshot:
        with self.repositories.read() as repository:
            metadata = repository.metadata(room_id)
            page = repository.page(
                room_id,
                topic_id=topic_id,
                member_id=member_id,
                keyword=keyword,
                before_seq=before_seq,
                limit=limit,
            )
            return RoomSnapshot(**metadata.model_dump(), **page.model_dump())

    def page(
        self,
        room_id: str,
        *,
        topic_id: str | None = None,
        member_id: str | None = None,
        keyword: str | None = None,
        before_seq: int | None = None,
        limit: int = 50,
    ) -> MessagePage:
        with self.repositories.read() as repository:
            repository.room(room_id)
            return repository.page(
                room_id,
                topic_id=topic_id,
                member_id=member_id,
                keyword=keyword,
                before_seq=before_seq,
                limit=limit,
            )

    def message(self, room_id: str, message_id: str) -> Message:
        with self.repositories.read() as repository:
            repository.room(room_id)
            return repository.message(room_id, message_id)

    def queue(
        self,
        room_id: str,
        *,
        topic_id: str | None = None,
        member_id: str | None = None,
        before_seq: int | None = None,
        limit: int = 50,
    ) -> MessageQueuePage:
        with self.repositories.read() as repository:
            repository.room(room_id)
            return repository.queue(
                room_id,
                topic_id=topic_id,
                member_id=member_id,
                before_seq=before_seq,
                limit=limit,
            )

    def events(self, room_id: str, after_event_id: int, limit: int = 200) -> RoomEventPage:
        with self.repositories.read() as repository:
            return repository.events(room_id, after_event_id, limit)
