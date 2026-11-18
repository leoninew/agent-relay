from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from conflua.application.dto.members import SessionChannel
from conflua.application.dto.messages import MessageUpdatesQuery
from conflua.domain.rooms.errors import RoomConflictError, RoomNotFoundError
from conflua.domain.rooms.models import Member
from conflua.infrastructure.persistence.models import (
    Base,
    ChannelRecord,
    MemberRecord,
    MessageRecipientRecord,
    MessageRecord,
    MessageTopicRecord,
    RoomEventRecord,
    RoomRecord,
    SessionRecord,
    TopicRecord,
)
from conflua.infrastructure.persistence.repositories.channels import SQLAlchemyChannelRepository
from conflua.infrastructure.persistence.repositories.messages import SQLAlchemyMessageRepository
from conflua.infrastructure.persistence.repositories.rooms import SQLAlchemyRoomRepository


@pytest.fixture
def scoped_session() -> Iterator[Session]:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            RoomRecord(
                id="room",
                workspace_path="/project",
                raw_workspace_path="/project",
                name="Room",
                description="",
            )
        )
        for channel_id in ("channel-default", "other"):
            session.add(
                ChannelRecord(
                    room_id="room",
                    id=channel_id,
                    name=channel_id,
                    description="",
                    is_default=channel_id == "channel-default",
                    workspace_kind="existing",
                )
            )
        for session_id, channel_id, deleted in (
            ("current", "channel-default", False),
            ("historical", "channel-default", True),
            ("elsewhere", "other", False),
        ):
            session.add(
                SessionRecord(
                    room_id="room",
                    id=session_id,
                    name=session_id,
                    provider="codex",
                    presence="available",
                )
            )
            member = Member(
                id=session_id,
                session_id=session_id,
                name=session_id,
                initials="M",
                presence="available",
                activity="",
                topic_ids=[],
                deleted_at=datetime.now(UTC) if deleted else None,
            )
            session.add(
                MemberRecord(
                    room_id="room",
                    channel_id=channel_id,
                    **member.model_dump(exclude={"topic_ids"}),
                )
            )
        session.flush()
        yield session
    engine.dispose()


def test_channel_sessions_include_history_but_exclude_other_channel(
    scoped_session: Session,
) -> None:
    repository = SQLAlchemyRoomRepository(scoped_session, "channel-default")
    assert {info.id for info in repository.resources("room").sessions} == {"current", "historical"}
    assert repository.active_bindings("room") == {"current": "current"}
    assert repository.member("room", "current").session_id == "current"
    for member_id in ("historical", "elsewhere", "missing"):
        with pytest.raises(RoomNotFoundError):
            repository.member("room", member_id)


@pytest.mark.parametrize("name", [None, "other", "Finished API"])
def test_archive_persists_name_and_status_without_removing_channel_history(
    scoped_session: Session, name: str | None
) -> None:
    repository = SQLAlchemyChannelRepository(scoped_session, "other")
    archived = repository.archive("room", "other", name=name)
    assert archived.name == (name or "other")
    assert archived.status == "archived"
    assert archived.archived_at is not None

    scoped_session.expire_all()
    assert [channel.id for channel in repository.channels("room")] == ["channel-default"]
    assert repository.channel("room", "other") == archived
    assert repository.archive("room", "other", name=name) == archived
    assert scoped_session.get(MemberRecord, ("room", "elsewhere", "other")) is not None
    assert [event.entity_id for event in scoped_session.scalars(select(RoomEventRecord))] == [
        "other"
    ]


def test_archive_does_not_mutate_a_channel_when_its_name_conflicts(scoped_session: Session) -> None:
    repository = SQLAlchemyChannelRepository(scoped_session, "other")
    active = repository.channel("room", "other")

    with pytest.raises(RoomConflictError) as error:
        repository.archive("room", "other", name="channel-default")

    assert error.value.code == "channel_name_conflict"
    assert repository.channel("room", "other") == active
    assert scoped_session.scalar(select(RoomEventRecord)) is None


@pytest.mark.parametrize(
    ("channel_id", "other_state"),
    [
        ("channel-default", "active"),
        ("other", "active"),
        ("channel-default", "archived"),
        ("other", "archived"),
        ("channel-default", "deleted"),
    ],
)
def test_joined_channels_are_room_scoped_and_exclude_inactive_memberships(
    scoped_session: Session,
    channel_id: str,
    other_state: str,
) -> None:
    other = scoped_session.get(ChannelRecord, ("room", "other"))
    assert other is not None
    if other_state != "active":
        other.archived_at = datetime.now(UTC)
        other.status = "archived" if other_state == "archived" else "active"
    shared = scoped_session.get(MemberRecord, ("room", "current", "channel-default"))
    assert shared is not None
    scoped_session.add(
        MemberRecord(
            room_id="room",
            channel_id="other",
            **{
                field: getattr(shared, field)
                for field in Member.model_fields
                if field != "topic_ids"
            },
        )
    )
    scoped_session.add(
        RoomRecord(
            id="another-room",
            workspace_path="/another-project",
            raw_workspace_path="/another-project",
            name="Another room",
            description="",
        )
    )
    scoped_session.add(
        ChannelRecord(
            room_id="another-room",
            id="channel-default",
            name="Another room channel",
            description="",
            is_default=True,
            workspace_kind="existing",
        )
    )
    scoped_session.add(
        SessionRecord(
            room_id="another-room",
            id="current",
            name="Current",
            provider="codex",
            presence="available",
        )
    )
    scoped_session.add(
        MemberRecord(
            room_id="another-room",
            channel_id="channel-default",
            **{
                field: getattr(shared, field)
                for field in Member.model_fields
                if field != "topic_ids"
            },
        )
    )
    scoped_session.flush()

    result = SQLAlchemyRoomRepository(scoped_session, channel_id).joined_channels("room")

    expected = {"current": [SessionChannel(id="channel-default", name="channel-default")]}
    if other_state == "active":
        expected["current"].append(SessionChannel(id="other", name="other"))
        expected["elsewhere"] = [SessionChannel(id="other", name="other")]
    assert result == expected


@pytest.mark.parametrize("retain", [False, True])
def test_event_message_query_applies_all_filters_and_bounds_retained_ids(
    scoped_session: Session,
    retain: bool,
) -> None:
    for known_topic_id in ("frontend", "backend"):
        scoped_session.add(
            TopicRecord(
                room_id="room",
                channel_id="channel-default",
                id=known_topic_id,
                name=known_topic_id,
                description="",
            )
        )
    now = datetime.now(UTC)
    fixtures = [
        ("matching", "channel-default", "current", "frontend", "needle%", False),
        ("recipient", "channel-default", "historical", "frontend", "needle%", False),
        ("wrong-topic", "channel-default", "current", "backend", "needle%", False),
        ("wrong-member", "channel-default", "historical", "frontend", "needle%", False),
        ("wrong-keyword", "channel-default", "current", "frontend", "needleX", False),
        ("other-channel", "other", "elsewhere", None, "needle%", False),
        ("unrequested", "channel-default", "current", "frontend", "needle%", False),
        ("deleted", "channel-default", "current", "frontend", "needle%", True),
    ]
    for sequence, (message_id, channel_id, publisher, topic_id, content, deleted) in enumerate(
        fixtures, 1
    ):
        scoped_session.add(
            MessageRecord(
                room_id="room",
                channel_id=channel_id,
                id=message_id,
                seq=sequence,
                publisher_id=publisher,
                content=content,
                created_at=now,
                deleted_at=now if deleted else None,
            )
        )
        if topic_id:
            scoped_session.add(
                MessageTopicRecord(
                    room_id="room",
                    channel_id=channel_id,
                    message_id=message_id,
                    topic_id=topic_id,
                    position=0,
                )
            )
    scoped_session.add(
        MessageRecipientRecord(
            room_id="room",
            channel_id="channel-default",
            message_id="recipient",
            member_id="current",
            position=0,
        )
    )
    scoped_session.flush()
    result = SQLAlchemyMessageRepository(scoped_session, "channel-default").message_updates(
        "room",
        MessageUpdatesQuery(
            message_ids=[row[0] for row in fixtures if row[0] != "unrequested"],
            retained_ids=["wrong-keyword", "other-channel", "unrequested", "deleted"]
            if retain
            else [],
            topic_id="frontend",
            member_id="current",
            keyword="needle%",
        ),
    )
    assert [message.id for message in result] == (
        ["matching", "recipient", "wrong-keyword"] if retain else ["matching", "recipient"]
    )


def test_activity_reads_no_complete_resources(
    scoped_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = SQLAlchemyRoomRepository(scoped_session, "channel-default")

    def unexpected_resources(room_id: str) -> None:
        pytest.fail("Activity must not load full resources")

    monkeypatch.setattr(repository, "resources", unexpected_resources)
    activity = repository.activity("room")
    assert activity.summary.total_messages == 0
    assert "members" not in activity.model_dump()
