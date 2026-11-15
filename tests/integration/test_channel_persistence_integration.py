import asyncio
import subprocess
from collections.abc import Iterator
from io import BytesIO, StringIO
from pathlib import Path
from unittest.mock import Mock

import httpx2
import pytest
from alembic import command
from PIL import Image
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from agent_relay.application.channels.service import ChannelService
from agent_relay.application.dto.channels import CreateChannel, UpdateChannel
from agent_relay.application.dto.delivery import QueueHead
from agent_relay.application.dto.members import CreatedMember, CreateMember, SessionInfo
from agent_relay.application.dto.messages import CreateMessage
from agent_relay.application.dto.rooms import CreateRoom
from agent_relay.application.images.service import ImageService
from agent_relay.application.members.service import MemberService
from agent_relay.application.messages.service import MessageService
from agent_relay.application.rooms.service import RoomService
from agent_relay.bootstrap.http import build_app
from agent_relay.domain.rooms.errors import RoomConflictError, RoomInputError, RoomNotFoundError
from agent_relay.domain.rooms.models import DEFAULT_CHANNEL_ID, Room
from agent_relay.infrastructure.git.worktrees import GitWorktrees
from agent_relay.infrastructure.images.files import FileImageStore
from agent_relay.infrastructure.persistence import migration_sql
from agent_relay.infrastructure.persistence.channel_store import SQLAlchemyChannelStore
from agent_relay.infrastructure.persistence.database import Database
from agent_relay.infrastructure.persistence.delivery_store import SQLAlchemyDeliveryStore
from agent_relay.infrastructure.persistence.migrations import (
    MIGRATION_HEAD,
    _configuration,
    run_migrations,
)
from agent_relay.infrastructure.persistence.models import (
    ChannelRecord,
    DeliveryRecord,
    MemberRecord,
    MessageRecord,
    TopicRecord,
)
from agent_relay.infrastructure.persistence.room_store import SQLAlchemyRoomStore
from agent_relay.infrastructure.persistence.sqlite import create_sqlite_engine


@pytest.fixture
def database(tmp_path: Path) -> Iterator[Database]:
    path = tmp_path / "rooms.db"
    run_migrations(path)
    database = Database(path)
    yield database
    database.close()


def setup(database: Database, directory: Path) -> tuple[Room, SQLAlchemyRoomStore, ChannelService]:
    store = SQLAlchemyRoomStore(database, channel_id=DEFAULT_CHANNEL_ID)
    room = RoomService(store).create_room(CreateRoom(name="Room", project_path=str(directory)))
    channels = ChannelService(
        SQLAlchemyChannelStore(database), GitWorktrees(), directory / "managed"
    )
    return room, store, channels


def git(directory: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-C", str(directory), *arguments],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def join(
    store: SQLAlchemyRoomStore, room_id: str, directory: str, session_id: str, topic_id: str
) -> CreatedMember:
    driver = Mock()
    driver.inspect.return_value = SessionInfo(session_id, directory, "codex", "Thread", "idle")
    return MemberService(store, driver).add(
        room_id, CreateMember(name="Agent", session_id=session_id, topic_ids=[topic_id])
    )


def test_channel_update_preserves_workspace_and_rejects_conflicts(
    database: Database, tmp_path: Path
) -> None:
    room, store, channels = setup(database, tmp_path)
    channel = channels.create(room.id, CreateChannel(name="API"))
    updated = channels.update(room.id, channel.id, UpdateChannel(name="Backend", description="New"))
    assert updated.model_dump(exclude={"name", "description"}) == channel.model_dump(
        exclude={"name", "description"}
    )
    assert channels.channel(room.id, channel.id).description == "New"
    assert (
        store.for_channel(channel.id).queries.events(room.id, 0).events[-1].entity_id == channel.id
    )
    other = channels.create(room.id, CreateChannel(name="Other"))
    with pytest.raises(RoomConflictError, match="名称"):
        channels.update(room.id, other.id, UpdateChannel(name="Backend"))
    assert channels.channel(room.id, other.id).name == "Other"
    default = channels.channel(room.id, DEFAULT_CHANNEL_ID)
    channels.update(room.id, default.id, UpdateChannel(name=default.name, description="Default"))
    with pytest.raises(RoomConflictError, match="默认"):
        channels.update(room.id, default.id, UpdateChannel(name="Renamed"))
    channels.delete(room.id, channel.id)
    with pytest.raises(RoomConflictError):
        channels.update(room.id, channel.id, UpdateChannel(name="Deleted"))
    with pytest.raises(RoomNotFoundError):
        channels.update(room.id, "missing", UpdateChannel(name="Missing"))


def test_channel_edit_http_contract_and_conflict_rollback(
    database: Database, tmp_path: Path
) -> None:
    room, _, channels = setup(database, tmp_path)
    channel = channels.create(room.id, CreateChannel(name="API"))
    channels.create(room.id, CreateChannel(name="Taken"))
    app = build_app(
        database=database, session_driver=Mock(), queue_driver=Mock(), capability_driver=Mock()
    )

    async def exercise() -> None:
        async with httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app), base_url="http://test"
        ) as client:
            path = f"/api/room/{room.id}/channel/{channel.id}"
            response = await client.patch(path, json={"name": " Backend ", "description": "New"})
            assert response.status_code == 200, response.text
            assert response.json()["name"] == "Backend"
            assert response.json()["workingPath"] == channel.working_path
            response = await client.patch(path, json={"name": "Taken", "description": "Wrong"})
            assert response.status_code == 409, response.text
            assert response.json()["code"] == "channel_name_conflict"
            response = await client.patch(path, json={"name": " ", "useWorktree": True})
            assert response.status_code == 422, response.text
            response = await client.get(path)
            assert response.json()["name"] == "Backend"
            assert response.json()["description"] == "New"

    asyncio.run(exercise())


def test_existing_directory_channels_are_isolated_and_replay_is_idempotent(
    database: Database, tmp_path: Path
) -> None:
    room, store, channels = setup(database, tmp_path)
    channels.git = Mock(side_effect=AssertionError("Git must not run"))
    request = CreateChannel(name="API", description="Backend work", channel_id="channel-api")
    channel = channels.create(room.id, request)
    assert channel.description == "Backend work"
    assert channels.create(room.id, request) == channel
    scoped = store.for_channel(channel.id)
    default = store.queries.metadata(room.id)
    metadata = scoped.queries.metadata(room.id)
    assert metadata.members[0].id == "user"
    assert len(metadata.topics) == 4
    assert {topic.id for topic in metadata.topics}.isdisjoint(topic.id for topic in default.topics)
    join(scoped, room.id, room.project_path, "api-thread", metadata.topics[0].id)
    join(store, room.id, room.project_path, "default-thread", default.topics[0].id)
    first = MessageService(scoped).post_message(
        room.id,
        CreateMessage(publication_id="same", content="API", topic_ids=[metadata.topics[0].id]),
    )
    second = MessageService(store).post_message(
        room.id,
        CreateMessage(publication_id="same", content="Default", topic_ids=[default.topics[0].id]),
    )
    assert first.seq == 1 and second.seq == 2
    assert [message.content for message in scoped.queries.page(room.id).messages] == ["API"]
    assert [message.content for message in store.queries.page(room.id).messages] == ["Default"]
    with pytest.raises(RoomInputError):
        MessageService(scoped).post_message(
            room.id,
            CreateMessage(
                publication_id="reply",
                content="Wrong",
                topic_ids=[metadata.topics[0].id],
                reply_to_message_id=second.id,
            ),
        )
    with pytest.raises(RoomNotFoundError):
        scoped.queries.message(room.id, second.id)
    events = scoped.queries.events(room.id, 0)
    assert not any(event.message_id == second.id for event in events.events)
    with pytest.raises(RoomConflictError):
        channels.create(room.id, request.model_copy(update={"name": "Other"}))
    driver = Mock()
    driver.list_sessions.return_value = [
        SessionInfo("api-thread", room.project_path, "codex", "Thread", "idle")
    ]
    RoomService(scoped).clear_room(room.id, driver)
    assert scoped.queries.page(room.id).messages == []
    assert [message.content for message in store.queries.page(room.id).messages] == ["Default"]


def test_real_worktree_uses_current_commit_and_preserves_dirty_source(
    database: Database, tmp_path: Path
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    git(source, "init")
    git(source, "config", "user.name", "Relay Test")
    git(source, "config", "user.email", "relay@example.invalid")
    (source / "file.txt").write_text("committed", encoding="utf-8")
    git(source, "add", "file.txt")
    git(source, "commit", "-m", "Initial")
    commit = git(source, "rev-parse", "HEAD")
    (source / "file.txt").write_text("dirty", encoding="utf-8")
    room, store, channels = setup(database, source)
    channels.root = tmp_path / "managed"
    (source / "later.txt").write_text("later", encoding="utf-8")
    git(source, "add", "later.txt")
    git(source, "commit", "-m", "Later")
    channel = channels.create(room.id, CreateChannel(name="Git", use_worktree=True))
    assert channel.base_commit == git(source, "rev-parse", "HEAD")
    assert channel.base_commit != commit
    assert (Path(channel.working_path) / "file.txt").read_text(encoding="utf-8") == "committed"
    assert (source / "file.txt").read_text(encoding="utf-8") == "dirty"
    scoped = store.for_channel(channel.id)
    member = join(
        scoped,
        room.id,
        channel.working_path,
        "worktree-thread",
        scoped.queries.metadata(room.id).topics[0].id,
    )
    join(
        store,
        room.id,
        room.project_path,
        "source-thread",
        store.queries.metadata(room.id).topics[0].id,
    )
    driver = Mock()
    driver.list_sessions.return_value = [
        SessionInfo("worktree-thread", channel.working_path, "codex", "Worktree", "idle"),
        SessionInfo("source-thread", room.project_path, "codex", "Source", "idle"),
    ]
    candidates = MemberService(scoped, driver).candidates(room.id)
    assert [candidate.id for candidate in candidates] == ["worktree-thread"]
    assert (
        next(
            session
            for session in store.queries.metadata(room.id).sessions
            if session.id == "source-thread"
        ).presence
        == "available"
    )
    MessageService(scoped).post_message(
        room.id,
        CreateMessage(publication_id="worktree", content="Work", mentioned_member_ids=[member.id]),
    )
    work = SQLAlchemyDeliveryStore(database).claim_delivery()
    assert work is not None and work.working_path == channel.working_path
    with pytest.raises(RoomConflictError):
        channels.delete(room.id, channel.id)
    with database.write() as session:
        session.connection().exec_driver_sql(
            "UPDATE deliveries SET status='unknown' WHERE room_id=? AND channel_id=?",
            (room.id, channel.id),
        )
    channels.delete(room.id, channel.id)
    assert Path(channel.working_path).is_dir()
    assert channel.id not in {item.id for item in channels.channels(room.id)}
    with pytest.raises(RoomConflictError):
        store.for_channel(channel.id).queries.metadata(room.id)


def test_session_cannot_join_two_channels_and_delivery_uses_channel_directory(
    database: Database, tmp_path: Path
) -> None:
    room, store, channels = setup(database, tmp_path)
    channel = channels.create(room.id, CreateChannel(name="API"))
    scoped = store.for_channel(channel.id)
    driver = Mock()
    driver.inspect.return_value = SessionInfo(
        "thread", room.project_path, "codex", "Thread", "idle"
    )
    member = MemberService(scoped, driver).add(
        room.id, CreateMember(name="Agent", session_id="thread", topic_ids=[])
    )
    with pytest.raises(RoomConflictError) as conflict:
        MemberService(store, driver).add(
            room.id, CreateMember(name="Agent", session_id="thread", topic_ids=[])
        )
    assert conflict.value.code == "session_already_joined"
    with pytest.raises(RoomConflictError, match="频道"):
        store.queries.member_for_session(room.id, "thread")
    MessageService(scoped).post_message(
        room.id,
        CreateMessage(publication_id="message", content="Work", mentioned_member_ids=[member.id]),
    )
    work = SQLAlchemyDeliveryStore(database).claim_delivery()
    assert (
        work is not None
        and work.channel_id == channel.id
        and work.working_path == channel.working_path
    )
    with database.write() as session:
        session.connection().exec_driver_sql(
            "UPDATE deliveries SET status='queued',submission_method='queue',"
            "queued_submission_id='receipt' WHERE room_id=? AND channel_id=?",
            (room.id, channel.id),
        )
    MemberService(scoped, driver).delete_member(room.id, member.id)
    assert not SQLAlchemyDeliveryStore(database).claim_activation(
        "thread", QueueHead("receipt", work.delivery.client_message_id)
    )


def test_http_creates_channel_and_reads_and_writes_its_resources(
    database: Database, tmp_path: Path
) -> None:
    app = build_app(
        database=database, session_driver=Mock(), queue_driver=Mock(), capability_driver=Mock()
    )
    app.state.http_dependencies.session_driver.inspect.return_value = SessionInfo(
        "http-thread", str(tmp_path), "codex", "Thread", "idle"
    )
    app.state.http_dependencies.session_driver.list_sessions.return_value = [
        app.state.http_dependencies.session_driver.inspect.return_value
    ]

    async def exercise() -> None:
        async with httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/room", json={"name": "Room", "projectPath": str(tmp_path)}
            )
            assert response.status_code == 201, response.text
            room_id = response.json()["id"]
            response = await client.post(
                f"/api/room/{room_id}/channel",
                json={"name": "API", "description": "Backend work"},
            )
            assert response.status_code == 201, response.text
            channel_id = response.json()["id"]
            assert response.json()["description"] == "Backend work"
            assert "status" not in response.json() and "error" not in response.json()
            prefix = f"/api/room/{room_id}/channel/{channel_id}"
            snapshot = await client.get(prefix + "/snapshot")
            assert snapshot.status_code == 200, snapshot.text
            topic_id = snapshot.json()["topics"][0]["id"]
            member = await client.post(
                prefix + "/member",
                json={"name": "Agent", "sessionId": "http-thread", "topicIds": [topic_id]},
            )
            assert member.status_code == 201, member.text
            message = await client.post(
                prefix + "/message",
                json={"publicationId": "http", "content": "API", "topicIds": [topic_id]},
            )
            assert message.status_code == 201, message.text
            assert len((await client.get(prefix + "/message")).json()["messages"]) == 1
            default_prefix = f"/api/room/{room_id}/channel/{DEFAULT_CHANNEL_ID}"
            assert (await client.get(default_prefix + "/message")).json()["messages"] == []
            for suffix in ("/message", "/metadata", "/topic", "/member", "/image/old", "/skills"):
                assert (await client.get(f"/api/room/{room_id}{suffix}")).status_code == 404
            caller = {"X-Agent-Relay-Session-Id": "http-thread"}
            wrong = await client.get(default_prefix + "/message", headers=caller)
            assert wrong.status_code == 409
            assert wrong.json()["code"] == "channel_required"
            correct = await client.get(prefix + "/message", headers=caller)
            assert correct.status_code == 200
            context = await client.post(
                prefix + f"/member/{member.json()['id']}/context", headers=caller, json={}
            )
            assert context.status_code == 200, context.text
            assert [item["content"] for item in context.json()["messages"]] == ["API"]
            message_id = message.json()["id"]
            removed_queue = await client.delete(prefix + f"/queue/{message_id}")
            assert removed_queue.status_code == 200, removed_queue.text
            assert len((await client.get(prefix + "/message")).json()["messages"]) == 1
            removed_topic = await client.delete(prefix + f"/topic/{topic_id}")
            assert removed_topic.status_code == 200, removed_topic.text
            assert removed_topic.json()["deletedAt"] is not None
            member_id = member.json()["id"]
            removed_member = await client.delete(prefix + f"/member/{member_id}")
            assert removed_member.status_code == 200, removed_member.text
            assert removed_member.json()["deletedAt"] is not None
            clear = await client.post(prefix + "/clear")
            assert clear.status_code in {200, 204}, clear.text
            assert (await client.get(prefix + "/message")).json()["messages"] == []
            with database.read() as session:
                key = {"room_id": room_id, "channel_id": channel_id}
                saved_topic = session.get(TopicRecord, {**key, "id": topic_id})
                saved_member = session.get(MemberRecord, {**key, "id": member_id})
                saved_message = session.get(MessageRecord, {**key, "id": message_id})
                saved_delivery = session.scalar(
                    select(DeliveryRecord).where(
                        DeliveryRecord.room_id == room_id,
                        DeliveryRecord.channel_id == channel_id,
                        DeliveryRecord.message_id == message_id,
                    )
                )
                assert saved_topic is not None and saved_topic.deleted_at is not None
                assert saved_member is not None and saved_member.deleted_at is not None
                assert saved_message is not None and saved_message.deleted_at is not None
                assert saved_delivery is not None and saved_delivery.deleted_at is not None
                assert saved_message.content == "API"
            for suffix, code, status in (
                (DEFAULT_CHANNEL_ID, "default_channel_required", 409),
                ("missing", "channel_not_found", 404),
            ):
                rejected = await client.delete(
                    f"/api/room/{room_id}/channel/{suffix}", headers={"X-Request-Id": "delete-test"}
                )
                assert rejected.status_code == status, rejected.text
                assert rejected.json()["code"] == code
                assert (
                    rejected.json()["requestId"]
                    == rejected.headers["X-Request-Id"]
                    == "delete-test"
                )
            deleted = await client.delete(prefix)
            assert deleted.status_code == 204 and deleted.content == b""
            listed = await client.get(f"/api/room/{room_id}/channel")
            assert [item["id"] for item in listed.json()] == [DEFAULT_CHANNEL_ID]
            unavailable = await client.get(prefix + "/snapshot")
            assert unavailable.status_code == 409
            assert unavailable.json()["code"] == "channel_unavailable"
            with database.read() as session:
                saved_channel = session.get(ChannelRecord, (room_id, channel_id))
                assert saved_channel is not None and saved_channel.archived_at is not None
                deleted_at = saved_channel.archived_at
                assert session.get(MessageRecord, {**key, "id": message_id}) is not None
            assert (await client.delete(prefix)).status_code == 204
            with database.read() as session:
                saved_channel = session.get(ChannelRecord, (room_id, channel_id))
                assert saved_channel is not None and saved_channel.archived_at == deleted_at
            assert (await client.get(default_prefix + "/snapshot")).status_code == 200

    asyncio.run(exercise())


def test_migration_preserves_old_records_and_event_high_water(tmp_path: Path) -> None:
    path = tmp_path / "legacy.db"
    command.upgrade(_configuration(path), "message_deleted_20261112")
    engine = create_sqlite_engine(path)
    with engine.begin() as connection:
        connection.exec_driver_sql("INSERT INTO rooms VALUES ('room-old', 'd:/old', 'Old', '')")
        connection.exec_driver_sql(
            "INSERT INTO members(room_id,id,name,kind,initials,presence,activity,activity_source) "
            "VALUES ('room-old','user','你','human','你','available','','user')"
        )
        connection.exec_driver_sql(
            "INSERT INTO messages(room_id,id,seq,publisher_id,publication_id,content,capabilities,"
            "created_at,deleted_at) VALUES ('room-old','old-message',3,'user','old-pub','Old','[]',"
            "'2026-01-01T00:00:00Z','2026-01-02T00:00:00Z')"
        )
        connection.exec_driver_sql(
            "INSERT INTO room_events(event_id,room_id,kind,entity_id) "
            "VALUES (500,'room-old','message','old-message')"
        )
        connection.exec_driver_sql("DELETE FROM room_events")
    engine.dispose()
    run_migrations(path)
    database = Database(path)
    try:
        with database.read() as session:
            record = session.scalar(select(MessageRecord))
            assert (
                record is not None
                and record.channel_id == DEFAULT_CHANNEL_ID
                and record.seq == 3
                and record.deleted_at is not None
            )
            assert session.connection().exec_driver_sql("PRAGMA foreign_key_check").fetchall() == []
            assert (
                session.connection()
                .exec_driver_sql("SELECT seq FROM sqlite_sequence WHERE name = 'room_events'")
                .scalar()
                == 500
            )
    finally:
        database.close()


def legacy_graph(path: Path) -> dict[str, tuple[list[str], list[tuple[object, ...]]]]:
    command.upgrade(_configuration(path), "message_deleted_20261112")
    engine = create_sqlite_engine(path)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("INSERT INTO rooms VALUES ('room','d:/old','Old','Room')")
            connection.exec_driver_sql(
                "INSERT INTO topics VALUES "
                "('room','topic','Topic','Description','created','deleted')"
            )
            for index, status in enumerate(
                ("pending", "submitting", "queued", "received", "rejected", "unknown")
            ):
                session_id, member_id, message_id = (
                    f"session-{index}",
                    f"member-{index}",
                    f"message-{index}",
                )
                connection.exec_driver_sql(
                    "INSERT INTO sessions VALUES ('room',?,?,'codex','d:/old','busy','observed')",
                    (session_id, session_id),
                )
                connection.exec_driver_sql(
                    "INSERT INTO members VALUES ('room',?,?,?,'agent','A','busy','activity',"
                    "'codex','observed',?)",
                    (member_id, member_id, session_id, "deleted" if index == 5 else None),
                )
                connection.exec_driver_sql(
                    "INSERT INTO member_topics VALUES ('room',?,'topic',?)", (member_id, index)
                )
                connection.exec_driver_sql(
                    "INSERT INTO messages(room_id,id,seq,publisher_id,publication_id,content,"
                    "reply_to_message_id,created_at,capabilities,deleted_at) "
                    "VALUES ('room',?,?,?,?,'Content',?,'created','[{\"type\":\"skill\"}]',?)",
                    (
                        message_id,
                        index + 1,
                        member_id,
                        f"publication-{index}",
                        f"message-{index - 1}" if index else None,
                        "deleted" if index == 5 else None,
                    ),
                )
                connection.exec_driver_sql(
                    "INSERT INTO message_topics VALUES ('room',?,'topic',0)", (message_id,)
                )
                for table in ("message_mentions", "message_recipients"):
                    connection.exec_driver_sql(
                        f"INSERT INTO {table} VALUES ('room',?,?,0)", (message_id, member_id)
                    )
                connection.exec_driver_sql(
                    "INSERT INTO deliveries(room_id,id,message_id,target_member_id,"
                    "target_session_id,client_message_id,status,updated_at,queued_at,received_at,"
                    "received_item_id,received_turn_id,activation_attempted_at,note,"
                    "queued_submission_id,receipt_metadata,error,deleted_at,submission_method) "
                    "VALUES ('room',?,?,?,?,?,?,'updated','queued','received','item','turn',"
                    "'activation','note','receipt','{\"position\":2}','error',?,'queue')",
                    (
                        f"delivery-{index}",
                        message_id,
                        member_id,
                        session_id,
                        f"client-{index}",
                        status,
                        "deleted" if index == 5 else None,
                    ),
                )
            connection.exec_driver_sql(
                "INSERT INTO room_events VALUES (7,'room','message','message-0','message-0')"
            )
            connection.exec_driver_sql(
                "INSERT INTO room_events VALUES (500,'room','message','message-0','message-0')"
            )
            connection.exec_driver_sql("DELETE FROM room_events WHERE event_id = 500")
            connection.exec_driver_sql(
                "INSERT INTO member_context_queries VALUES "
                "('query','room','member-0','message-0','topic','Content',10,0,20,'provided')"
            )
            connection.exec_driver_sql(
                "INSERT INTO member_context_messages VALUES ('room','query','message-0',0)"
            )
            connection.exec_driver_sql(
                "INSERT INTO member_topic_positions VALUES ('room','member-0','topic',6,'updated')"
            )
            tables = (
                connection.exec_driver_sql(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name NOT IN ('alembic_version','sqlite_sequence') ORDER BY name"
                )
                .scalars()
                .all()
            )
            snapshot = {}
            for table in tables:
                columns = [
                    row[1] for row in connection.exec_driver_sql(f"PRAGMA table_info({table})")
                ]
                rows = [
                    tuple(row)
                    for row in connection.exec_driver_sql(
                        f"SELECT {','.join(columns)} FROM {table} ORDER BY rowid"
                    )
                ]
                snapshot[table] = (columns, rows)
            return snapshot
    finally:
        engine.dispose()


@pytest.mark.parametrize("fail", [False, True])
def test_migration_full_graph_and_transaction_rollback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fail: bool
) -> None:
    path = tmp_path / "graph.db"
    snapshot = legacy_graph(path)
    original = migration_sql.execute_sql_file

    def execute(file: Path) -> None:
        original(file)
        if file.name == "02_data.up.sql":
            raise RuntimeError("Injected failure")

    if fail:
        monkeypatch.setattr(migration_sql, "execute_sql_file", execute)
        with pytest.raises(RuntimeError, match="Injected failure"):
            run_migrations(path)
    else:
        run_migrations(path)
    engine = create_sqlite_engine(path)
    try:
        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall() == []
            assert connection.exec_driver_sql(
                "SELECT version_num FROM alembic_version"
            ).scalar() == ("message_deleted_20261112" if fail else MIGRATION_HEAD)
            for table, (columns, rows) in snapshot.items():
                actual = [
                    tuple(row)
                    for row in connection.exec_driver_sql(
                        f"SELECT {','.join(columns)} FROM {table} ORDER BY rowid"
                    )
                ]
                assert actual == rows, table
                if not fail and table not in {"rooms", "sessions"}:
                    assert set(
                        connection.exec_driver_sql(f"SELECT channel_id FROM {table}").scalars()
                    ) == {DEFAULT_CHANNEL_ID}
            assert (
                connection.exec_driver_sql(
                    "SELECT seq FROM sqlite_sequence WHERE name='room_events'"
                ).scalar()
                == 500
            )
            assert (
                connection.exec_driver_sql(
                    "SELECT name FROM sqlite_master WHERE name LIKE 'legacy_%'"
                ).fetchall()
                == []
            )
    finally:
        engine.dispose()


def test_offline_migration_can_be_reviewed_without_database(tmp_path: Path) -> None:
    path = tmp_path / "offline.db"
    config = _configuration(path)
    config.output_buffer = output = StringIO()
    command.upgrade(config, "message_deleted_20261112:head", sql=True)
    assert "CREATE TABLE channels" in output.getvalue()
    assert "INSERT INTO messages" in output.getvalue()
    assert not path.exists()


def test_database_rejects_cross_channel_relationships(database: Database, tmp_path: Path) -> None:
    room, store, channels = setup(database, tmp_path)
    channel = channels.create(room.id, CreateChannel(name="API"))
    foreign_topic = store.for_channel(channel.id).queries.metadata(room.id).topics[0]
    with pytest.raises(IntegrityError), database.write() as session:
        session.connection().exec_driver_sql(
            "INSERT INTO member_topics(room_id,member_id,topic_id,position,channel_id) "
            "VALUES (?,'user',?,0,?)",
            (room.id, foreign_topic.id, DEFAULT_CHANNEL_ID),
        )


def test_images_are_only_readable_in_their_channel(database: Database, tmp_path: Path) -> None:
    room, store, channels = setup(database, tmp_path)
    channel = channels.create(room.id, CreateChannel(name="Images"))
    files = FileImageStore(tmp_path / "images", DEFAULT_CHANNEL_ID)
    default = ImageService(store.queries, files, DEFAULT_CHANNEL_ID)
    scoped = ImageService(
        store.for_channel(channel.id).queries, files.for_channel(channel.id), channel.id
    )
    image = BytesIO()
    Image.new("RGB", (2, 2)).save(image, format="PNG")
    uploaded = scoped.upload(room.id, image.getvalue())
    assert f"/channel/{channel.id}/image/" in uploaded.url
    assert scoped.read(room.id, uploaded.id).path.read_bytes() == image.getvalue()
    with pytest.raises(RoomNotFoundError):
        default.read(room.id, uploaded.id)
    default_image = default.upload(room.id, image.getvalue())
    assert f"/channel/{DEFAULT_CHANNEL_ID}/image/" in default_image.url
    assert default.read(room.id, default_image.id).path.parent == (
        files.root / room.id / "channels" / DEFAULT_CHANNEL_ID / "images"
    )
    with pytest.raises(RoomNotFoundError):
        scoped.read(room.id, default_image.id)


def test_request_transaction_rolls_back_channel_and_initial_resources(
    database: Database, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    room, _, _ = setup(database, tmp_path)
    monkeypatch.setattr(GitWorktrees, "inspect", Mock(return_value="commit"))
    monkeypatch.setattr(GitWorktrees, "available", Mock())
    monkeypatch.setattr(
        GitWorktrees,
        "create",
        Mock(side_effect=RoomInputError("Git failed", code="worktree_git_failed")),
    )
    app = build_app(
        database=database, session_driver=Mock(), queue_driver=Mock(), capability_driver=Mock()
    )

    async def exercise() -> None:
        async with httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                f"/api/room/{room.id}/channel",
                json={"name": "API", "channelId": "channel-failed", "useWorktree": True},
            )
            assert response.status_code == 422, response.text
            assert response.json()["code"] == "worktree_git_failed"

    asyncio.run(exercise())
    with database.read() as session:
        for table, column in (
            ("channels", "id"),
            ("members", "channel_id"),
            ("topics", "channel_id"),
            ("room_events", "channel_id"),
        ):
            assert (
                session.connection()
                .exec_driver_sql(
                    f"SELECT COUNT(*) FROM {table} WHERE room_id=? AND {column}=?",
                    (room.id, "channel-failed"),
                )
                .scalar()
                == 0
            )


def test_description_migration_preserves_channels_without_status(tmp_path: Path) -> None:
    path = tmp_path / "channel-description.db"
    command.upgrade(_configuration(path), "channels_20261113")
    engine = create_sqlite_engine(path)
    with engine.begin() as connection:
        connection.exec_driver_sql("INSERT INTO rooms VALUES ('room', 'd:/old', 'Old', '', NULL)")
        connection.exec_driver_sql(
            "INSERT INTO channels(room_id,id,name,working_path,is_default,workspace_kind,status) "
            "VALUES ('room','channel-default','默认','d:/old',1,'existing','ready')"
        )
        connection.exec_driver_sql(
            "INSERT INTO room_events(room_id,channel_id,kind,entity_id) "
            "VALUES ('room','channel-default','room','room')"
        )
    engine.dispose()
    run_migrations(path)
    database = Database(path)
    try:
        with database.read() as session:
            columns = {
                row[1]
                for row in session.connection().exec_driver_sql("PRAGMA table_info(channels)")
            }
            assert "description" in columns and not {"status", "error", "repository_path"} & columns
            assert session.connection().exec_driver_sql(
                "SELECT name, description FROM channels"
            ).one() == ("默认", "")
            assert session.connection().exec_driver_sql("PRAGMA foreign_key_check").fetchall() == []
    finally:
        database.close()


@pytest.mark.parametrize("initialize", [False, True])
def test_worktree_requires_repository_with_a_commit(
    database: Database, tmp_path: Path, initialize: bool
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    if initialize:
        git(source, "init")
    room, _, channels = setup(database, source)
    with pytest.raises(RoomInputError):
        channels.create(room.id, CreateChannel(name="Git", use_worktree=True))
    assert len(channels.channels(room.id)) == 1
