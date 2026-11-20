from io import BytesIO
from pathlib import Path
from unittest.mock import Mock

import pytest
from PIL import Image
from sqlalchemy import select

from conflua.application.channels.ports import WorktreeDriver
from conflua.application.channels.service import ChannelService
from conflua.application.dto.channels import CreateChannel
from conflua.application.dto.rooms import CreateRoom
from conflua.application.images.service import ImageService
from conflua.application.rooms.ports import RoomQueries
from conflua.application.rooms.service import RoomService
from conflua.domain.identifiers import is_tsid
from conflua.domain.rooms.inline_images import inline_images
from conflua.domain.rooms.resources import DEFAULT_TOPIC_NAMES
from conflua.infrastructure.images.files import FileImageStore
from conflua.infrastructure.persistence.channel_store import SQLAlchemyChannelStore
from conflua.infrastructure.persistence.database import Database
from conflua.infrastructure.persistence.models import ChannelRecord, MemberRecord, RoomRecord
from conflua.infrastructure.persistence.room_store import SQLAlchemyRoomStore

pytestmark = pytest.mark.integration


def test_room_and_independent_channel_have_distinct_scoped_humans(
    file_database: Database, tmp_path: Path
) -> None:
    database = file_database
    room_input = CreateRoom(name="Room", workspace_path=tmp_path.as_posix())
    git = Mock(spec=WorktreeDriver)
    channels = ChannelService(SQLAlchemyChannelStore(database), git, tmp_path / "worktrees")
    room_transaction = database.request_transaction()
    try:
        room = RoomService(SQLAlchemyRoomStore(database, room_transaction)).create_room(room_input)
        with database.read() as session:
            assert session.get(RoomRecord, room.id) is None
        room_transaction.finish(commit=True)
    finally:
        room_transaction.finish(commit=False)

    (default,) = channels.channels(room.id)
    assert default.is_default and default.room_id == room.id
    issued = channels.issue_id(room.id)
    with database.read() as session:
        assert session.get(ChannelRecord, (room.id, issued.channel_id)) is None
    assert channels.channels(room.id) == [default] and git.mock_calls == []

    channel_transaction = database.request_transaction()
    try:
        service = ChannelService(
            SQLAlchemyChannelStore(database, channel_transaction), git, tmp_path / "worktrees"
        )
        created = service.create(
            room.id, CreateChannel(name="Another", channel_id=issued.channel_id)
        )
        assert channels.channels(room.id) == [default]
        channel_transaction.finish(commit=True)
    finally:
        channel_transaction.finish(commit=False)

    assert created.id == issued.channel_id and not created.is_default
    assert channels.channel(room.id, issued.channel_id) == created
    assert channels.channels(room.id) == [default, created] and git.mock_calls == []
    rooms = SQLAlchemyRoomStore(database)
    other_room = RoomService(rooms).create_room(
        CreateRoom(name="Other room", workspace_path=(tmp_path / "other").as_posix())
    )
    (other_default,) = channels.channels(other_room.id)
    with rooms.read() as repository:
        assert repository.resources(room.id).channel_id == default.id
        assert repository.resources(other_room.id).channel_id == other_default.id
        assert default.id != other_default.id
    ids = [room.id, default.id, created.id]
    for channel, store in ((default, rooms), (created, rooms.for_channel(created.id))):
        with store.read() as repository:
            state = repository.resources(room.id)
            human = repository.publisher(room.id, None)
            assert human.kind == "human" and human.name == "你" and human.session_id is None
            assert state.channel_id == channel.id and state.members == [human]
            assert [topic.name for topic in state.topics] == list(DEFAULT_TOPIC_NAMES)
            events = repository.events(room.id, 0).events
            event_entities = {event.entity_id for event in events}
            assert {topic.id for topic in state.topics} <= event_entities
            assert (room.id if channel.is_default else channel.id) in event_entities
        ids.extend([human.id, *(topic.id for topic in state.topics)])
        with database.read() as session:
            assert (
                session.scalars(
                    select(MemberRecord.id).where(
                        MemberRecord.room_id == room.id,
                        MemberRecord.channel_id == channel.id,
                        MemberRecord.kind == "human",
                    )
                ).one()
                == human.id
            )
    assert len(set(ids)) == len(ids) and all(is_tsid(value) for value in ids)


def test_image_round_trip_uses_the_explicit_tsid_scope(tmp_path: Path) -> None:
    room_id = "0000000000123"
    channel_id = "0000000000124"
    image_bytes = BytesIO()
    Image.new("RGB", (2, 2)).save(image_bytes, format="PNG")
    queries = Mock(spec=RoomQueries)
    images = FileImageStore(tmp_path / "rooms").for_channel(channel_id)
    service = ImageService(queries, images, channel_id)

    uploaded = service.upload(room_id, image_bytes.getvalue())
    result = service.read(room_id, uploaded.id)
    (reference,) = inline_images(uploaded.markdown, room_id, channel_id)

    assert uploaded.url == f"/api/room/{room_id}/channel/{channel_id}/image/{uploaded.id}"
    assert (
        result.path
        == tmp_path / "rooms" / room_id / "channels" / channel_id / "images" / f"{uploaded.id}.png"
    )
    assert result.path.read_bytes() == image_bytes.getvalue()
    assert reference.id == uploaded.id
    assert uploaded.markdown[reference.start : reference.end] == uploaded.url
