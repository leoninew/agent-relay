from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as PersistenceSession
from support.databases import MemoryDatabases

from agent_relay.application.rooms.ports import RoomRepository
from agent_relay.domain.rooms.errors import RoomConflictError, RoomNotFoundError
from agent_relay.domain.rooms.members import observation_cutoff
from agent_relay.domain.rooms.models import Member, Room, Session, Topic
from agent_relay.domain.rooms.resources import fixed_user
from agent_relay.domain.rooms.rules import normalize_project_path, validate_member
from agent_relay.domain.rooms.state import RoomState
from agent_relay.infrastructure.persistence.database import Database
from agent_relay.infrastructure.persistence.models import (
    Base,
    ContextMessageRecord,
    ContextQueryRecord,
    DeliveryRecord,
    MemberRecord,
    MessageMentionRecord,
    MessageRecipientRecord,
    MessageRecord,
    MessageTopicRecord,
    RoomEventRecord,
    SessionRecord,
    TopicPositionRecord,
)
from agent_relay.infrastructure.persistence.repositories import SQLAlchemyRoomRepository
from agent_relay.infrastructure.persistence.resource_queries import ResourceQueries

pytestmark = pytest.mark.integration
OBSERVED_AT = datetime.fromisoformat("2026-11-11T12:00:00.123000+08:00")
TOPIC_IDS = ["topic-z", "topic-a", "topic-m", "topic-b"]


@pytest.fixture
def database(tmp_path: Path, databases: MemoryDatabases) -> Iterator[Database]:
    path = tmp_path / "resources.sqlite3"
    database = databases.create(path)
    try:
        yield database
    finally:
        database.close()


def _create_resources(
    repository: RoomRepository,
    room_id: str = "room",
    *,
    agent_count: int = 2,
) -> RoomState:
    repository.insert_room(
        Room(
            id=room_id,
            project_path=f"D:/{room_id}",
            name=room_id,
            description="Resources",
        ),
        user=fixed_user(),
    )
    state = repository.resources(room_id)
    original = deepcopy(state)
    state.topics = [
        Topic(id=topic_id, name=name, description=name, created_at=OBSERVED_AT)
        for topic_id, name in zip(TOPIC_IDS, ("产品", "架构", "开发", "测试"), strict=True)
    ]
    for index in range(agent_count):
        session_id = f"session-{index}"
        state.sessions.append(
            Session(
                id=session_id,
                name=f"Session {index}",
                provider="codex",
                project_path=f"D:/{room_id}",
                presence="available",
                observed_at=OBSERVED_AT,
            )
        )
        state.members.append(
            Member(
                id=f"agent-{index}",
                session_id=session_id,
                name=f"Alias {index}",
                initials="A",
                presence="available",
                activity="working",
                activity_source="codex",
                observed_at=OBSERVED_AT,
                topic_ids=TOPIC_IDS[:2],
            )
        )
    repository.save_resources(state, original)
    return state


def _seed(database: Database, room_id: str = "room") -> None:
    with database.write() as session:
        _create_resources(SQLAlchemyRoomRepository(session), room_id)


def _events(session: PersistenceSession, room_id: str = "room") -> list[tuple[str, str]]:
    return [
        (kind, entity_id)
        for kind, entity_id in session.execute(
            select(
                RoomEventRecord.kind,
                RoomEventRecord.entity_id,
            )
            .where(RoomEventRecord.room_id == room_id)
            .order_by(RoomEventRecord.event_id)
        )
    ]


def test_resource_round_trip_preserves_fixed_user_order_and_detached_values(
    database: Database,
    databases: MemoryDatabases,
) -> None:
    _seed(database)
    reopened = databases.open(database.path)
    try:
        with reopened.read() as session:
            repository: RoomRepository = SQLAlchemyRoomRepository(session)
            state = repository.resources("room")
            assert [topic.id for topic in state.topics] == TOPIC_IDS
            assert [topic.name for topic in state.topics] == ["产品", "架构", "开发", "测试"]
            assert [item.id for item in state.sessions] == ["session-0", "session-1"]
            assert [member.id for member in state.members] == ["agent-0", "agent-1", "user"]
            user = state.members[-1]
            assert user.kind == "human" and user.name == "你" and user.session_id is None
            assert user.activity_source == "user" and user.deleted_at is None
            assert repository.publisher("room", None) == user
            assert repository.joined_members("room") == {
                "session-0": "agent-0",
                "session-1": "agent-1",
            }
            assert set(repository.bindings()) == {("room", "session-0"), ("room", "session-1")}
            assert state.sessions[0].observed_at is not None
            assert state.sessions[0].observed_at.isoformat() == OBSERVED_AT.isoformat()
            metadata = repository.metadata("room")
            assert metadata.summary.total_messages == 0
            assert len(metadata.positions) == 4
            assert metadata.event_id > 0
            state.members[0].topic_ids.clear()
            state.topics[0].name = "not saved"
        with reopened.read() as session:
            state = ResourceQueries(session).resources("room")
            assert state.topics[0].name == "产品"
            assert state.members[0].topic_ids == TOPIC_IDS[:2]
    finally:
        reopened.close()


def test_resource_changes_replace_subscriptions_and_append_only_changed_events(
    database: Database,
) -> None:
    _seed(database)
    with database.write() as session:
        repository = SQLAlchemyRoomRepository(session)
        state = repository.resources("room")
        original = deepcopy(state)
        before = len(_events(session))
        state.room.description = "Updated"
        state.topics[0].description = "Changed topic"
        state.sessions[0].name = "Renamed session"
        state.members[0].name = "Renamed alias"
        state.members[0].topic_ids = [TOPIC_IDS[1], TOPIC_IDS[3]]
        repository.save_resources(state, original)
        assert _events(session)[before:] == [
            ("room", "room"),
            ("topic", TOPIC_IDS[0]),
            ("session", "session-0"),
            ("member", "agent-0"),
        ]
        current = repository.resources("room")
        assert current.members[0].topic_ids == [TOPIC_IDS[1], TOPIC_IDS[3]]
        assert current.room.description == "Updated"
        after = len(_events(session))
        repository.save_resources(current, deepcopy(current))
        assert len(_events(session)) == after
    with database.read() as session:
        current = ResourceQueries(session).resources("room")
        assert current.members[0].name == "Renamed alias"
        assert current.members[0].topic_ids == [TOPIC_IDS[1], TOPIC_IDS[3]]
        assert current.sessions[0].name == "Renamed session"


def test_soft_deleted_resources_remain_historical_and_free_active_bindings(
    database: Database,
) -> None:
    _seed(database)
    with database.write() as session:
        repository = SQLAlchemyRoomRepository(session)
        state = repository.resources("room")
        original = deepcopy(state)
        removed = state.members[0]
        removed.deleted_at = OBSERVED_AT
        removed.topic_ids = []
        state.topics[0].deleted_at = OBSERVED_AT
        state.members[1].topic_ids = [TOPIC_IDS[1]]
        state.members.append(
            Member(
                id="replacement",
                session_id="session-0",
                name=removed.name,
                initials="A",
                presence="available",
                activity="replacement",
                topic_ids=[TOPIC_IDS[1]],
            )
        )
        repository.save_resources(state, original)
        assert repository.joined_members("room")["session-0"] == "replacement"
        with pytest.raises(RoomNotFoundError):
            repository.publisher("room", removed.id)
        assert repository.queries.member_for_session("room", "session-0").id == "replacement"
        current = repository.resources("room")
        assert current.topics[0].deleted_at == OBSERVED_AT
        assert current.members[0].deleted_at == OBSERVED_AT
        assert all(item.topic_id != TOPIC_IDS[0] for item in repository.metadata("room").positions)
        unchanged = deepcopy(current)
        current.sessions = []
        repository.save_resources(current, unchanged)
        assert len(repository.resources("room").sessions) == 2


@pytest.mark.parametrize("constraint", ["topic_name", "session_binding"])
def test_constraint_failures_roll_back_earlier_resource_changes_and_events(
    database: Database,
    constraint: str,
) -> None:
    _seed(database)
    with database.read() as session:
        original = ResourceQueries(session).resources("room")
        before_events = _events(session)
    with pytest.raises(IntegrityError), database.write() as session:
        repository = SQLAlchemyRoomRepository(session)
        state = repository.resources("room")
        before = deepcopy(state)
        state.room.description = "must roll back"
        if constraint == "topic_name":
            state.topics[1].name = state.topics[0].name
        else:
            state.members[1].session_id = state.members[0].session_id
        repository.save_resources(state, before)
    with database.read() as session:
        assert ResourceQueries(session).resources("room") == original
        assert _events(session) == before_events


@pytest.mark.parametrize("relation", ["subscription", "session"])
def test_cross_room_resource_references_are_rejected(database: Database, relation: str) -> None:
    _seed(database)
    with database.write() as session:
        repository = SQLAlchemyRoomRepository(session)
        repository.insert_room(
            Room(id="other", project_path="D:/other", name="Other", description=""),
            user=fixed_user(),
        )
        state = repository.resources("other")
        original = deepcopy(state)
        state.topics.append(Topic(id="foreign-topic", name="Foreign", description=""))
        state.sessions.append(
            Session(
                id="foreign-session",
                name="Foreign",
                provider="codex",
                project_path="D:/other",
                presence="available",
            )
        )
        repository.save_resources(state, original)
    with pytest.raises(IntegrityError), database.write() as session:
        repository = SQLAlchemyRoomRepository(session)
        state = repository.resources("room")
        original = deepcopy(state)
        if relation == "subscription":
            state.members[0].topic_ids = ["foreign-topic"]
        else:
            state.members[0].session_id = "foreign-session"
        repository.save_resources(state, original)
    with database.read() as session:
        state = ResourceQueries(session).resources("room")
        assert state.members[0].session_id == "session-0"
        assert state.members[0].topic_ids == TOPIC_IDS[:2]


def test_missing_resources_raise_domain_errors(database: Database) -> None:
    with database.read() as session:
        queries = ResourceQueries(session)
        for read in (queries.room, queries.resources, queries.metadata):
            with pytest.raises(RoomNotFoundError, match="聊天室不存在"):
                read("missing")
        with pytest.raises(RoomNotFoundError, match="聊天室成员不存在"):
            queries.publisher("missing", None)
    _seed(database)
    with database.read() as session, pytest.raises(RoomNotFoundError, match="尚未加入"):
        ResourceQueries(session).member_for_session("room", "missing")


@pytest.mark.parametrize(("seconds", "updated"), [(29, False), (30, True)])
def test_unchanged_observations_checkpoint_inclusively_across_timezones(
    database: Database,
    seconds: int,
    updated: bool,
) -> None:
    _seed(database)
    observed_at = OBSERVED_AT.astimezone(UTC) + timedelta(seconds=seconds)
    with database.write() as session:
        repository = SQLAlchemyRoomRepository(session)
        member = session.get(MemberRecord, ("room", "agent-0"))
        saved_session = session.get(SessionRecord, ("room", "session-0"))
        assert member is not None and saved_session is not None
        before = len(_events(session))
        repository.save_observation(
            "room",
            "agent-0",
            "session-0",
            "available",
            "working",
            observed_at,
            None,
            refresh_cutoff=observation_cutoff(observed_at),
        )
        assert _events(session)[before:] == (
            [("member", "agent-0"), ("session", "session-0")] if updated else []
        )
        expected_time = observed_at if updated else OBSERVED_AT
        assert member.observed_at is not None and saved_session.observed_at is not None
        assert member.observed_at.isoformat() == expected_time.isoformat()
        assert saved_session.observed_at.isoformat() == expected_time.isoformat()
        assert saved_session.name == "Session 0"
        assert repository.resources("room").members[0].name == "Alias 0"
    with database.read() as session:
        state = ResourceQueries(session).resources("room")
        assert state.members[0].observed_at == expected_time
        assert state.sessions[0].observed_at == expected_time


@pytest.mark.parametrize(
    ("change", "changed_kinds"),
    [
        ("presence", ["member", "session"]),
        ("rename", ["session"]),
    ],
)
def test_presence_and_session_rename_update_only_the_matching_resources(
    database: Database,
    change: str,
    changed_kinds: list[str],
) -> None:
    _seed(database)
    observed_at = OBSERVED_AT + timedelta(seconds=1)
    with database.write() as session:
        repository = SQLAlchemyRoomRepository(session)
        member = session.get(MemberRecord, ("room", "agent-0"))
        saved_session = session.get(SessionRecord, ("room", "session-0"))
        assert member is not None and saved_session is not None
        before = len(_events(session))
        repository.save_observation(
            "room",
            "agent-0",
            "session-0",
            "busy" if change == "presence" else "available",
            "working",
            observed_at,
            "Renamed upstream" if change == "rename" else None,
            refresh_cutoff=observation_cutoff(observed_at),
        )
        assert [kind for kind, entity_id in _events(session)[before:]] == changed_kinds
        assert member.name == "Alias 0"
        assert member.activity_source == "codex"
        assert member.presence == ("busy" if change == "presence" else "available")
        assert member.activity == "working"
        assert member.observed_at == (observed_at if "member" in changed_kinds else OBSERVED_AT)
        assert saved_session.observed_at == (
            observed_at if "session" in changed_kinds else OBSERVED_AT
        )
        assert saved_session.name == ("Renamed upstream" if change == "rename" else "Session 0")
        assert repository.resources("room").members[0].topic_ids == TOPIC_IDS[:2]
    with database.read() as session:
        assert ResourceQueries(session).publisher("room", "agent-0").name == "Alias 0"


def test_observation_does_not_resurrect_a_removed_member(database: Database) -> None:
    _seed(database)
    with database.write() as session:
        repository = SQLAlchemyRoomRepository(session)
        state = repository.resources("room")
        original = deepcopy(state)
        state.members[0].deleted_at = OBSERVED_AT
        state.members[0].topic_ids = []
        repository.save_resources(state, original)
        before = len(_events(session))
        repository.save_observation(
            "room",
            "agent-0",
            "session-0",
            "busy",
            "changed",
            OBSERVED_AT + timedelta(seconds=1),
            None,
            refresh_cutoff=observation_cutoff(OBSERVED_AT + timedelta(seconds=1)),
        )
        assert _events(session)[before:] == [("session", "session-0")]
        removed = repository.resources("room").members[0]
        assert removed.deleted_at == OBSERVED_AT
        assert removed.presence == "available" and removed.topic_ids == []
        assert "session-0" not in repository.joined_members("room")


def test_concurrent_normalized_project_creation_has_one_winner(database: Database) -> None:
    paths = ["D:/Concurrent", "d:/concurrent", "D:\\Concurrent\\.", "d:/concurrent/"] * 2

    def create(index: int) -> str:
        project_path = normalize_project_path(paths[index])
        try:
            with database.write() as session:
                repository = SQLAlchemyRoomRepository(session)
                if repository.project_exists(project_path):
                    raise RoomConflictError("该项目已有聊天室")
                repository.insert_room(
                    Room(
                        id=f"room-{index}",
                        name="Concurrent",
                        project_path=project_path,
                        description="",
                    ),
                    user=fixed_user(),
                )
            return "created"
        except RoomConflictError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=4) as workers:
        outcomes = list(workers.map(create, range(len(paths))))
    assert outcomes.count("created") == 1 and outcomes.count("conflict") == 7
    with database.read() as session:
        queries = ResourceQueries(session)
        [room] = queries.rooms()
        assert room.project_path == "d:/concurrent"
        assert [member.id for member in queries.resources(room.id).members] == ["user"]
        assert _events(session, room.id) == [("room", room.id), ("member", "user")]


def test_concurrent_member_binding_has_one_winner(database: Database) -> None:
    with database.write() as session:
        _create_resources(SQLAlchemyRoomRepository(session), agent_count=0)

    def join(index: int) -> str:
        try:
            with database.write() as session:
                repository = SQLAlchemyRoomRepository(session)
                state = repository.resources("room")
                validate_member(state, "Alias", [TOPIC_IDS[0]])
                if "original-session" in repository.joined_members("room"):
                    raise RoomConflictError("该会话已加入聊天室")
                original = deepcopy(state)
                state.sessions.append(
                    Session(
                        id="original-session",
                        name="Original",
                        provider="codex",
                        project_path="D:/room",
                        presence="available",
                    )
                )
                state.members.append(
                    Member(
                        id=f"member-{index}",
                        session_id="original-session",
                        name="Alias",
                        initials="A",
                        presence="available",
                        activity="",
                        topic_ids=[TOPIC_IDS[0]],
                    )
                )
                repository.save_resources(state, original)
            return "joined"
        except RoomConflictError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=4) as workers:
        outcomes = list(workers.map(join, range(8)))
    assert outcomes.count("joined") == 1 and outcomes.count("conflict") == 7
    with database.read() as session:
        state = ResourceQueries(session).resources("room")
        assert len(state.sessions) == 1 and len(state.members) == 2
        assert len([event for event in _events(session) if event[0] == "session"]) == 1


def _insert_history(session: PersistenceSession, room_id: str = "room") -> None:
    session.add(
        MessageRecord(
            room_id=room_id,
            id="message-1",
            seq=1,
            publisher_id="user",
            content="First",
            created_at=OBSERVED_AT,
        )
    )
    session.flush()
    session.add(
        MessageRecord(
            room_id=room_id,
            id="message-2",
            seq=2,
            publisher_id="agent-0",
            content="Reply",
            reply_to_message_id="message-1",
            created_at=OBSERVED_AT + timedelta(seconds=1),
        )
    )
    session.flush()
    session.add_all(
        [
            MessageTopicRecord(
                room_id=room_id, message_id="message-1", topic_id=TOPIC_IDS[0], position=0
            ),
            MessageTopicRecord(
                room_id=room_id, message_id="message-1", topic_id=TOPIC_IDS[1], position=1
            ),
            MessageTopicRecord(
                room_id=room_id, message_id="message-2", topic_id=TOPIC_IDS[0], position=0
            ),
            MessageMentionRecord(
                room_id=room_id, message_id="message-1", member_id="agent-0", position=0
            ),
            MessageRecipientRecord(
                room_id=room_id, message_id="message-1", member_id="agent-0", position=0
            ),
            DeliveryRecord(
                room_id=room_id,
                id="delivery-1",
                message_id="message-1",
                target_member_id="agent-0",
                target_session_id="session-0",
                client_message_id=f"{room_id}-client-1",
                status="queued",
                updated_at=OBSERVED_AT,
                queued_at=OBSERVED_AT,
                queued_submission_id="queued-1",
                receipt_metadata={"accepted": True},
            ),
            DeliveryRecord(
                room_id=room_id,
                id="delivery-2",
                message_id="message-2",
                target_member_id="agent-0",
                target_session_id="session-0",
                client_message_id=f"{room_id}-client-2",
                status="unknown",
                updated_at=OBSERVED_AT,
                deleted_at=OBSERVED_AT,
            ),
            ContextQueryRecord(
                room_id=room_id,
                id=f"{room_id}-query",
                member_id="agent-0",
                message_id="message-1",
                topic_id=TOPIC_IDS[0],
                page_limit=50,
                provided_at=OBSERVED_AT,
            ),
            TopicPositionRecord(
                room_id=room_id,
                member_id="agent-0",
                topic_id=TOPIC_IDS[0],
                seq=1,
                updated_at=OBSERVED_AT,
            ),
            RoomEventRecord(
                room_id=room_id, kind="message", entity_id="message-1", message_id="message-1"
            ),
        ]
    )
    session.flush()
    session.add(
        ContextMessageRecord(
            room_id=room_id,
            query_id=f"{room_id}-query",
            message_id="message-1",
            position=0,
        )
    )
    session.flush()


def test_metadata_aggregates_historical_routes_and_only_active_delivery_counts(
    database: Database,
) -> None:
    _seed(database)
    _seed(database, "other")
    with database.write() as session:
        _insert_history(session)
        _insert_history(session, "other")
    with database.read() as session:
        queries = ResourceQueries(session)
        assert [room.id for room in queries.rooms()] == ["room", "other"]
        metadata = queries.metadata("room")
        assert [topic.id for topic in metadata.topics] == TOPIC_IDS
        assert metadata.summary.total_messages == 2
        assert metadata.summary.queued_count == 1
        assert metadata.summary.unknown_count == 0
        assert [
            (position.member_id, position.topic_id, position.seq, position.later_count)
            for position in metadata.positions
        ] == [
            ("agent-0", TOPIC_IDS[0], 1, 1),
            ("agent-0", TOPIC_IDS[1], 0, 1),
            ("agent-1", TOPIC_IDS[0], 0, 2),
            ("agent-1", TOPIC_IDS[1], 0, 1),
        ]
        assert metadata.positions[0].updated_at == OBSERVED_AT
        assert [position.member_id for position in queries.positions("room", "agent-1")] == [
            "agent-1",
            "agent-1",
        ]
    with database.write() as session:
        repository = SQLAlchemyRoomRepository(session)
        state = repository.resources("room")
        original = deepcopy(state)
        state.topics[0].deleted_at = OBSERVED_AT
        state.members[1].deleted_at = OBSERVED_AT
        state.members[1].topic_ids = []
        repository.save_resources(state, original)
    with database.read() as session:
        metadata = ResourceQueries(session).metadata("room")
        assert [topic.id for topic in metadata.topics] == TOPIC_IDS
        assert [(position.member_id, position.topic_id) for position in metadata.positions] == [
            ("agent-0", TOPIC_IDS[1]),
        ]
        assert len(ResourceQueries(session).metadata("other").positions) == 4


def test_room_deletion_respects_foreign_keys_and_preserves_other_rooms(database: Database) -> None:
    _seed(database)
    _seed(database, "other")
    with database.write() as session:
        _insert_history(session)
        _insert_history(session, "other")
    with database.write() as session:
        repository = SQLAlchemyRoomRepository(session)
        loaded_member = session.get(MemberRecord, ("room", "agent-0"))
        assert loaded_member is not None
        assert repository.metadata("room").summary.total_messages == 2
        repository.delete_room("room")
        assert session.get(MemberRecord, ("room", "agent-0")) is None
        with pytest.raises(RoomNotFoundError):
            repository.room("room")
    with database.read() as session:
        for name, table in Base.metadata.tables.items():
            criterion = table.c.id == "room" if name == "rooms" else table.c.room_id == "room"
            assert session.scalar(select(func.count()).select_from(table).where(criterion)) == 0
        queries = ResourceQueries(session)
        assert [room.id for room in queries.rooms()] == ["other"]
        assert queries.metadata("other").summary.total_messages == 2


def test_project_uniqueness_rolls_back_without_an_orphan_fixed_user(database: Database) -> None:
    _seed(database)
    with pytest.raises(IntegrityError), database.write() as session:
        SQLAlchemyRoomRepository(session).insert_room(
            Room(
                id="duplicate",
                project_path="D:/room",
                name="Duplicate",
                description="",
            ),
            user=fixed_user(),
        )
    with database.read() as session:
        queries = ResourceQueries(session)
        assert [room.id for room in queries.rooms()] == ["room"]
        assert session.get(MemberRecord, ("duplicate", "user")) is None
        assert _events(session, "duplicate") == []
