from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from conflua.application.dto.messages import MessageUpdatesQuery
from conflua.domain.rooms.errors import RoomNotFoundError
from conflua.domain.rooms.models import Member
from conflua.infrastructure.persistence.models import (
    Base,
    ChannelRecord,
    MemberRecord,
    MessageRecipientRecord,
    MessageRecord,
    MessageTopicRecord,
    RoomRecord,
    SessionRecord,
    TopicRecord,
)
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
                project_path="/project",
                raw_project_path="/project",
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
