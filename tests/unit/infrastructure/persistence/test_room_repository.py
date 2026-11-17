from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock

import pytest
from sqlalchemy import Update
from sqlalchemy.dialects import sqlite
from sqlalchemy.orm import Session

from conflua.application.dto.rooms import CreateRoom
from conflua.application.rooms.service import RoomService
from conflua.domain.rooms.errors import RoomConflictError
from conflua.infrastructure.persistence.database import Database
from conflua.infrastructure.persistence.migrations import MIGRATION_HEAD
from conflua.infrastructure.persistence.models import (
    Base,
    ChannelRecord,
    RoomEventRecord,
    RoomRecord,
)
from conflua.infrastructure.persistence.repositories.rooms import SQLAlchemyRoomRepository
from conflua.infrastructure.persistence.room_store import SQLAlchemyRoomStore
from conflua.infrastructure.persistence.sqlite import create_sqlite_engine


def test_clear_marks_messages_and_deliveries_in_one_room_without_deleting_history() -> None:
    session = Mock(spec=Session)
    session.scalars.return_value = ["first", "second"]
    now = datetime.now(UTC)

    removed = SQLAlchemyRoomRepository(session, "channel-default").clear_messages(
        "target-room", now
    )

    assert removed == 2
    for statement in [session.scalars.call_args.args[0], session.execute.call_args.args[0]]:
        assert isinstance(statement, Update)
        compiled = statement.compile(dialect=sqlite.dialect())
        sql = str(compiled)
        assert "deleted_at IS NULL" in sql and "room_id = ?" in sql
        assert compiled.params["deleted_at"] == now
        assert "target-room" in compiled.params.values()
    event = session.add.call_args.args[0]
    assert isinstance(event, RoomEventRecord) and event.kind == "clear"
    assert event.room_id == event.entity_id == "target-room" and event.message_id is None
    session.delete.assert_not_called()
    session.commit.assert_not_called()
    session.flush.assert_called_once()


def test_clear_event_forces_resync_before_replaying_any_old_message_events() -> None:
    session = Mock(spec=Session)
    session.get.side_effect = [
        RoomRecord(id="room", name="Room", project_path="d:/project", description=""),
        ChannelRecord(id="channel-default", room_id="room", workspace_kind="existing"),
        ChannelRecord(id="channel-default", room_id="room", workspace_kind="existing"),
    ]
    session.scalar.side_effect = [400, 401]

    result = SQLAlchemyRoomRepository(session, "channel-default").events(
        "room", after_event_id=10, limit=1
    )

    assert result.resync_required and result.events == [] and result.next_event_id == 401
    session.scalars.assert_not_called()
    statement = session.scalar.call_args_list[0].args[0].compile(dialect=sqlite.dialect())
    assert "clear" in statement.params.values()
    assert 10 in statement.params.values()


def test_project_path_uniqueness_compares_existing_room_and_worktree_paths(tmp_path: Path) -> None:
    path = tmp_path / "conflua.db"
    engine = create_sqlite_engine(path)
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"
        )
        connection.exec_driver_sql("INSERT INTO alembic_version VALUES (?)", (MIGRATION_HEAD,))
    database = Database(path, engine=engine)
    try:
        store = SQLAlchemyRoomStore(database, channel_id="channel-default")
        service = RoomService(store)
        room = service.create_room(CreateRoom(name="Room", project_path="D:\\Project\\"))
        assert room.project_path == "D:/Project"
        with database.write() as session:
            record = session.get(RoomRecord, room.id)
            assert record is not None
            record.project_path = "D:\\Project\\"
        with pytest.raises(RoomConflictError) as duplicate:
            service.create_room(CreateRoom(name="Duplicate", project_path="d:/PROJECT/"))
        assert duplicate.value.code == "project_room_exists"
        with database.write() as session:
            session.add(
                ChannelRecord(
                    room_id=room.id,
                    id="worktree",
                    name="Worktree",
                    description="",
                    worktree_path="D:\\Other\\",
                    is_default=False,
                    workspace_kind="worktree",
                )
            )
        with pytest.raises(RoomConflictError) as occupied:
            service.create_room(CreateRoom(name="Occupied", project_path="d:/OTHER"))
        assert occupied.value.code == "project_room_exists"
    finally:
        database.close()
