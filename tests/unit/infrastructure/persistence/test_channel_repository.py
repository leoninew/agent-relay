from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from conflua.domain.rooms.errors import RoomConflictError
from conflua.domain.rooms.models import DEFAULT_CHANNEL_ID
from conflua.infrastructure.persistence.models import Base, ChannelRecord, RoomRecord
from conflua.infrastructure.persistence.repositories.channels import SQLAlchemyChannelRepository
from conflua.infrastructure.persistence.sqlite import create_sqlite_engine


@pytest.fixture
def repository(tmp_path: Path) -> Iterator[SQLAlchemyChannelRepository]:
    engine = create_sqlite_engine(tmp_path / "channels.db")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            session.add(
                RoomRecord(id="room", name="Room", project_path=tmp_path.as_posix(), description="")
            )
            session.flush()
            for channel_id in (DEFAULT_CHANNEL_ID, "channel-api"):
                session.add(
                    ChannelRecord(
                        room_id="room",
                        id=channel_id,
                        name=channel_id,
                        description="Original description",
                        is_default=channel_id == DEFAULT_CHANNEL_ID,
                        workspace_kind="existing",
                    )
                )
            session.commit()
            yield SQLAlchemyChannelRepository(session, DEFAULT_CHANNEL_ID)
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    ("name", "description"),
    [
        ("Renamed", "Original description"),
        (DEFAULT_CHANNEL_ID, "Changed description"),
        (DEFAULT_CHANNEL_ID, "Original description"),
    ],
)
def test_default_channel_rejects_all_edits(
    repository: SQLAlchemyChannelRepository, name: str, description: str
) -> None:
    original = repository.channel("room", DEFAULT_CHANNEL_ID)

    with pytest.raises(RoomConflictError) as caught:
        repository.update("room", DEFAULT_CHANNEL_ID, name, description)

    assert caught.value.code == "default_channel_read_only"
    assert repository.channel("room", DEFAULT_CHANNEL_ID) == original


def test_default_channel_cannot_be_deleted(repository: SQLAlchemyChannelRepository) -> None:
    with pytest.raises(RoomConflictError) as caught:
        repository.delete("room", DEFAULT_CHANNEL_ID)

    assert caught.value.code == "default_channel_required"
    assert repository.channel("room", DEFAULT_CHANNEL_ID).archived_at is None


def test_other_channels_can_still_be_edited_and_deleted(
    repository: SQLAlchemyChannelRepository,
) -> None:
    updated = repository.update("room", "channel-api", "API", "Changed description")
    assert updated.name == "API"
    assert updated.description == "Changed description"

    repository.delete("room", "channel-api")
    assert repository.channel("room", "channel-api").archived_at is not None
    assert [channel.id for channel in repository.channels("room")] == [DEFAULT_CHANNEL_ID]
