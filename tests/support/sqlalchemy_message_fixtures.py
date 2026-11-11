from copy import deepcopy
from datetime import datetime

from agent_relay.domain.rooms.models import Member, Room, Session, Topic
from agent_relay.domain.rooms.resources import fixed_user
from agent_relay.infrastructure.persistence.database import Database
from agent_relay.infrastructure.persistence.room_store import SQLAlchemyRoomStore
from agent_relay.infrastructure.persistence.transaction import SQLAlchemyTransaction

ROOM_ID = "messages"
FIRST_TOPIC = "topic-z"
SECOND_TOPIC = "topic-a"
OBSERVED_AT = datetime.fromisoformat("2026-11-11T12:34:56.123456+08:00")


class MessageTestStore(SQLAlchemyRoomStore):
    def for_request(self, transaction: SQLAlchemyTransaction) -> "MessageTestStore":
        return MessageTestStore(self.database, transaction)


def seed_message_store(database: Database) -> MessageTestStore:
    store = MessageTestStore(database)
    with store.write() as repository:
        repository.insert_room(
            Room(id=ROOM_ID, project_path="D:/messages", name="Messages", description="Queries"),
            user=fixed_user(),
        )
        state = repository.resources(ROOM_ID)
        original = deepcopy(state)
        state.topics = [
            Topic(id=FIRST_TOPIC, name="First", description="", created_at=OBSERVED_AT),
            Topic(id=SECOND_TOPIC, name="Second", description="", created_at=OBSERVED_AT),
            Topic(id="empty-topic", name="Empty", description=""),
        ]
        for member_id, name, topics in (
            ("alpha", "Alpha", [FIRST_TOPIC, SECOND_TOPIC]),
            ("beta", "Beta", [FIRST_TOPIC]),
            ("gamma", "Gamma", [SECOND_TOPIC]),
        ):
            session_id = f"session-{member_id}"
            state.sessions.append(
                Session(
                    id=session_id,
                    name=name,
                    provider="codex",
                    project_path="D:/messages",
                    presence="available",
                    observed_at=OBSERVED_AT,
                )
            )
            state.members.append(
                Member(
                    id=member_id,
                    session_id=session_id,
                    name=name,
                    initials=name[:2],
                    presence="available",
                    activity="",
                    topic_ids=topics,
                    observed_at=OBSERVED_AT,
                )
            )
        repository.save_resources(state, original)
        repository.insert_room(
            Room(id="other", project_path="D:/other", name="Other", description="Empty"),
            user=fixed_user(),
        )
    return store
