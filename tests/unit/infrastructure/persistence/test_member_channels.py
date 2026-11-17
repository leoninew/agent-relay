from pathlib import Path
from unittest.mock import Mock

import pytest

from conflua.application.dto.members import CreateMember, SessionInfo
from conflua.application.members.service import MemberService
from conflua.application.members.sessions import SessionDriver
from conflua.domain.rooms.errors import RoomConflictError, RoomNotFoundError
from conflua.infrastructure.persistence.database import Database
from conflua.infrastructure.persistence.migrations import MIGRATION_HEAD
from conflua.infrastructure.persistence.models import Base, ChannelRecord, RoomRecord, TopicRecord
from conflua.infrastructure.persistence.repositories.channels import SQLAlchemyChannelRepository
from conflua.infrastructure.persistence.room_store import SQLAlchemyRoomStore
from conflua.infrastructure.persistence.sqlite import create_sqlite_engine


def test_session_memberships_are_independent_per_channel(tmp_path: Path) -> None:
    path = tmp_path / "conflua.db"
    engine = create_sqlite_engine(path)
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"
        )
        connection.exec_driver_sql("INSERT INTO alembic_version VALUES (?)", (MIGRATION_HEAD,))
    database = Database(path, engine=engine)
    project = tmp_path.as_posix()
    other_project = (tmp_path / "other").as_posix()
    (tmp_path / "other").mkdir()
    try:
        with database.write() as session:
            session.add(RoomRecord(id="room", name="Room", project_path=project, description=""))
            session.flush()
            for channel_id, working_path in (
                ("channel-default", project),
                ("second", project),
                ("different", other_project),
            ):
                session.add(
                    ChannelRecord(
                        room_id="room",
                        id=channel_id,
                        name=channel_id,
                        description="",
                        worktree_path=working_path if channel_id == "different" else None,
                        is_default=channel_id == "channel-default",
                        workspace_kind="worktree" if channel_id == "different" else "existing",
                    )
                )
            session.flush()
            for channel_id in ("channel-default", "second"):
                session.add(
                    TopicRecord(
                        room_id="room",
                        channel_id=channel_id,
                        id="topic",
                        name=channel_id,
                        description="",
                    )
                )
        info = SessionInfo("session", "codex", "Session", "idle")
        driver = Mock(spec=SessionDriver)
        driver.list_sessions.return_value = [info]
        driver.inspect.return_value = info
        first_store = SQLAlchemyRoomStore(database, channel_id="channel-default")
        second_store = first_store.for_channel("second")
        with database.write() as session:
            room = session.get(RoomRecord, "room")
            assert room is not None
            room.project_path = (tmp_path / "updated").as_posix()
        with database.read() as session:
            channels = SQLAlchemyChannelRepository(session, "channel-default").channels("room")
            paths = {channel.id: channel.working_path for channel in channels}
            assert paths == {
                "channel-default": (tmp_path / "updated").as_posix(),
                "second": (tmp_path / "updated").as_posix(),
                "different": other_project,
            }
            for channel_id in ("channel-default", "second"):
                record = session.get(ChannelRecord, ("room", channel_id))
                assert record is not None and record.worktree_path is None
        with second_store.read() as rooms:
            assert rooms.working_path("room") == paths["second"]
        first = MemberService(first_store, driver)
        second = MemberService(second_store, driver)
        first_member = first.add(
            "room", CreateMember(name="First", session_id="session", topic_ids=["topic"])
        )

        assert first.candidates("room")[0].member_id == first_member.id
        assert second.candidates("room")[0].member_id is None
        with pytest.raises(RoomNotFoundError) as missing:
            second_store.queries.member_for_session("room", "session")
        assert missing.value.code == "session_not_joined"

        second_member = second.add(
            "room", CreateMember(name="Second", session_id="session", topic_ids=["topic"])
        )
        assert first_member.id != second_member.id
        assert first_store.queries.member_for_session("room", "session").id == first_member.id
        second_binding = second_store.queries.member_for_session("room", "session")
        assert second_binding.id == second_member.id and second_binding.topic_ids == ["topic"]
        assert second.candidates("room")[0].member_id == second_member.id
        with pytest.raises(RoomConflictError) as duplicate:
            second.add("room", CreateMember(name="Duplicate", session_id="session", topic_ids=[]))
        assert duplicate.value.code == "session_already_joined"

        different = MemberService(first_store.for_channel("different"), driver)
        assert different.candidates("room")[0].member_id is None
        other_member = different.add(
            "room", CreateMember(name="Other", session_id="session", topic_ids=[])
        )
        assert other_member.session_id == "session"
        assert different.candidates("room")[0].member_id == other_member.id

        first.delete_member("room", first_member.id)
        assert first.candidates("room")[0].member_id is None
        assert second_store.queries.member_for_session("room", "session").id == second_member.id
        assert different.candidates("room")[0].member_id == other_member.id
        with pytest.raises(RoomNotFoundError):
            first_store.queries.member_for_session("room", "session")
        replacement = first.add(
            "room", CreateMember(name="Replacement", session_id="session", topic_ids=[])
        )
        assert replacement.id != first_member.id
    finally:
        database.close()
