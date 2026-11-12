from datetime import UTC, datetime
from unittest.mock import Mock

from sqlalchemy import Update
from sqlalchemy.dialects import sqlite
from sqlalchemy.orm import Session

from agent_relay.infrastructure.persistence.models import RoomEventRecord, RoomRecord
from agent_relay.infrastructure.persistence.repositories.rooms import SQLAlchemyRoomRepository


def test_clear_marks_messages_and_deliveries_in_one_room_without_deleting_history() -> None:
    session = Mock(spec=Session)
    session.scalars.return_value = ["first", "second"]
    now = datetime.now(UTC)

    removed = SQLAlchemyRoomRepository(session).clear_messages("target-room", now)

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
    session.get.return_value = RoomRecord(
        id="room", name="Room", project_path="d:/project", description=""
    )
    session.scalar.side_effect = [400, 401]

    result = SQLAlchemyRoomRepository(session).events("room", after_event_id=10, limit=1)

    assert result.resync_required and result.events == [] and result.next_event_id == 401
    session.scalars.assert_not_called()
    statement = session.scalar.call_args_list[0].args[0].compile(dialect=sqlite.dialect())
    assert "clear" in statement.params.values()
    assert 10 in statement.params.values()
