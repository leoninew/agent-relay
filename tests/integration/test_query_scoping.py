from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from conflua.application.dto.delivery import ReceivedInput
from conflua.application.dto.desktop import ShutdownNotificationTarget
from conflua.application.dto.members import SessionChannel
from conflua.application.dto.messages import MessageUpdatesQuery
from conflua.domain.rooms.models import Member
from conflua.infrastructure.persistence.models import (
    Base,
    ChannelRecord,
    DeliveryRecord,
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
from conflua.infrastructure.persistence.repositories.deliveries import SQLAlchemyDeliveryRepository
from conflua.infrastructure.persistence.repositories.messages import SQLAlchemyMessageRepository
from conflua.infrastructure.persistence.repositories.rooms import SQLAlchemyRoomRepository

pytestmark = pytest.mark.integration

ROOM_ID = "0000000000200"
SECOND_ROOM_ID = "0000000000201"
ANOTHER_ROOM_ID = "0000000000202"
DEFAULT_CHANNEL = "0000000000203"
OTHER_CHANNEL = "0000000000204"
CURRENT = "0000000000205"
HISTORICAL = "0000000000206"
ELSEWHERE = "0000000000207"
FRONTEND = "0000000000208"
BACKEND = "0000000000209"
MATCHING = "0000000000210"
RECIPIENT = "0000000000211"
WRONG_TOPIC = "0000000000212"
WRONG_MEMBER = "0000000000213"
WRONG_KEYWORD = "0000000000214"
OTHER_CHANNEL_MESSAGE = "0000000000215"
UNREQUESTED = "0000000000216"
DELETED_MESSAGE = "0000000000217"
HUMAN = "0000000000218"


@pytest.fixture
def scoped_session() -> Iterator[Session]:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            RoomRecord(
                id=ROOM_ID,
                workspace_path="/project",
                raw_workspace_path="/project",
                name="Room",
                description="",
            )
        )
        for channel_id in (DEFAULT_CHANNEL, OTHER_CHANNEL):
            session.add(
                ChannelRecord(
                    room_id=ROOM_ID,
                    id=channel_id,
                    name=channel_id,
                    description="",
                    is_default=channel_id == DEFAULT_CHANNEL,
                    workspace_kind="existing",
                )
            )
        for session_id, channel_id, deleted in (
            (CURRENT, DEFAULT_CHANNEL, False),
            (HISTORICAL, DEFAULT_CHANNEL, True),
            (ELSEWHERE, OTHER_CHANNEL, False),
        ):
            session.add(
                SessionRecord(
                    room_id=ROOM_ID,
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
                    room_id=ROOM_ID,
                    channel_id=channel_id,
                    **member.model_dump(exclude={"topic_ids"}),
                    is_deleted=deleted,
                )
            )
        session.flush()
        yield session
    engine.dispose()


def test_channel_sessions_include_history_but_exclude_other_channel(
    scoped_session: Session,
) -> None:
    repository = SQLAlchemyRoomRepository(scoped_session, DEFAULT_CHANNEL)
    assert {info.id for info in repository.resources(ROOM_ID).sessions} == {CURRENT, HISTORICAL}
    assert repository.active_bindings(ROOM_ID) == {CURRENT: CURRENT}
    assert repository.member(ROOM_ID, CURRENT).session_id == CURRENT


def test_navigation_heads_only_include_live_incoming_messages_in_active_channels(
    scoped_session: Session,
) -> None:
    now = datetime.now(UTC)
    scoped_session.add(
        RoomRecord(
            id=SECOND_ROOM_ID,
            workspace_path="/second",
            raw_workspace_path="/second",
            name="Second",
            description="",
        )
    )
    scoped_session.add(
        ChannelRecord(
            room_id=SECOND_ROOM_ID,
            id=DEFAULT_CHANNEL,
            name="Default",
            description="",
            is_default=True,
            workspace_kind="existing",
        )
    )
    scoped_session.add(
        MemberRecord(
            room_id=ROOM_ID,
            channel_id=OTHER_CHANNEL,
            id=HUMAN,
            kind="human",
            name="你",
            initials="你",
            presence="available",
            activity="",
            activity_source="user",
        )
    )
    for room, channel, seq, sender, deleted in (
        (ROOM_ID, OTHER_CHANNEL, 1, ELSEWHERE, False),
        (ROOM_ID, OTHER_CHANNEL, 2, HUMAN, False),
        (ROOM_ID, OTHER_CHANNEL, 3, ELSEWHERE, True),
        (SECOND_ROOM_ID, DEFAULT_CHANNEL, 8, "another", False),
    ):
        scoped_session.add(
            MessageRecord(
                room_id=room,
                channel_id=channel,
                id=f"{seq + 100:013d}",
                seq=seq,
                publisher_id=sender,
                content="text",
                created_at=now,
                is_deleted=deleted,
                deleted_at=now if deleted else None,
            )
        )
    repo = SQLAlchemyRoomRepository(scoped_session, DEFAULT_CHANNEL)

    def heads() -> dict[tuple[str, str], int]:
        return {
            (row.room_id, row.channel_id): row.latest_seq for row in repo.channel_message_heads()
        }

    assert heads() == {
        (ROOM_ID, OTHER_CHANNEL): 1,
        (ROOM_ID, DEFAULT_CHANNEL): 0,
        (SECOND_ROOM_ID, DEFAULT_CHANNEL): 8,
    }
    assert repo.notification_targets(now) == [
        ShutdownNotificationTarget(ROOM_ID, (ELSEWHERE,), OTHER_CHANNEL)
    ]
    channel_record = scoped_session.get(ChannelRecord, (ROOM_ID, OTHER_CHANNEL))
    room_record = scoped_session.get(RoomRecord, SECOND_ROOM_ID)
    assert channel_record and room_record
    channel_record.is_deleted = room_record.is_deleted = True
    channel_record.deleted_at = room_record.deleted_at = now
    assert heads() == {(ROOM_ID, DEFAULT_CHANNEL): 0}


def test_receipt_updates_unconfirmed_delivery_and_records_event(scoped_session: Session) -> None:
    delivery = DeliveryRecord(
        room_id=ROOM_ID,
        channel_id=OTHER_CHANNEL,
        id="0000000000501",
        message_id=MATCHING,
        target_member_id=ELSEWHERE,
        target_session_id=ELSEWHERE,
        client_message_id="client-message",
        status="unknown",
        updated_at=datetime.now(UTC),
    )
    scoped_session.add(delivery)
    scoped_session.flush()
    repository = SQLAlchemyDeliveryRepository(scoped_session)
    receipt = ReceivedInput("client-message", "item", "turn")
    assert repository.confirm_input(ELSEWHERE, receipt)
    scoped_session.refresh(delivery)
    assert (delivery.status, delivery.received_item_id, delivery.received_turn_id) == (
        "received",
        "item",
        "turn",
    )
    assert list(scoped_session.scalars(select(RoomEventRecord.message_id))) == [MATCHING]


def test_targeted_observation_updates_current_bindings(scoped_session: Session) -> None:
    shared = scoped_session.get(MemberRecord, (ROOM_ID, ELSEWHERE, OTHER_CHANNEL))
    assert shared is not None
    shared.session_id = CURRENT
    scoped_session.flush()
    repository = SQLAlchemyRoomRepository(scoped_session, DEFAULT_CHANNEL)
    now = datetime.now(UTC)
    repository.save_bound_session_observation(CURRENT, "busy", "active", now, "Worker")
    assert repository.member(ROOM_ID, CURRENT).presence == "busy"
    session_record = scoped_session.get(SessionRecord, (ROOM_ID, CURRENT))
    assert session_record is not None
    assert (session_record.presence, session_record.name) == ("busy", "Worker")
    assert {event.channel_id for event in scoped_session.scalars(select(RoomEventRecord))} == {
        DEFAULT_CHANNEL,
        OTHER_CHANNEL,
    }
    assert shared.presence == "busy"


@pytest.mark.parametrize("name", [None, OTHER_CHANNEL, "Finished API"])
def test_archive_persists_name_and_status_without_removing_channel_history(
    scoped_session: Session, name: str | None
) -> None:
    repository = SQLAlchemyChannelRepository(scoped_session, OTHER_CHANNEL)
    archived = repository.archive(ROOM_ID, OTHER_CHANNEL, name=name)
    assert archived.name == (name or OTHER_CHANNEL)
    assert archived.status == "archived"
    assert archived.archived_at is not None

    scoped_session.expire_all()
    assert [channel.id for channel in repository.channels(ROOM_ID)] == [DEFAULT_CHANNEL]
    assert repository.channel(ROOM_ID, OTHER_CHANNEL) == archived
    assert repository.archive(ROOM_ID, OTHER_CHANNEL, name=name) == archived
    assert scoped_session.get(MemberRecord, (ROOM_ID, ELSEWHERE, OTHER_CHANNEL)) is not None
    assert [event.entity_id for event in scoped_session.scalars(select(RoomEventRecord))] == [
        OTHER_CHANNEL
    ]


@pytest.mark.parametrize(
    ("channel_id", "other_state"),
    [
        (DEFAULT_CHANNEL, "active"),
        (OTHER_CHANNEL, "active"),
        (DEFAULT_CHANNEL, "archived"),
        (OTHER_CHANNEL, "archived"),
        (DEFAULT_CHANNEL, "deleted"),
    ],
)
def test_joined_channels_are_room_scoped_and_exclude_inactive_memberships(
    scoped_session: Session,
    channel_id: str,
    other_state: str,
) -> None:
    other = scoped_session.get(ChannelRecord, (ROOM_ID, OTHER_CHANNEL))
    assert other is not None
    if other_state == "archived":
        other.archived_at = datetime.now(UTC)
        other.status = "archived"
    elif other_state == "deleted":
        other.is_deleted = True
        other.deleted_at = datetime.now(UTC)
    shared = scoped_session.get(MemberRecord, (ROOM_ID, CURRENT, DEFAULT_CHANNEL))
    assert shared is not None
    scoped_session.add(
        MemberRecord(
            room_id=ROOM_ID,
            channel_id=OTHER_CHANNEL,
            **{
                field: getattr(shared, field)
                for field in Member.model_fields
                if field != "topic_ids"
            },
        )
    )
    scoped_session.add(
        RoomRecord(
            id=ANOTHER_ROOM_ID,
            workspace_path="/another-project",
            raw_workspace_path="/another-project",
            name="Another room",
            description="",
        )
    )
    scoped_session.add(
        ChannelRecord(
            room_id=ANOTHER_ROOM_ID,
            id=DEFAULT_CHANNEL,
            name="Another room channel",
            description="",
            is_default=True,
            workspace_kind="existing",
        )
    )
    scoped_session.add(
        SessionRecord(
            room_id=ANOTHER_ROOM_ID,
            id=CURRENT,
            name="Current",
            provider="codex",
            presence="available",
        )
    )
    scoped_session.add(
        MemberRecord(
            room_id=ANOTHER_ROOM_ID,
            channel_id=DEFAULT_CHANNEL,
            **{
                field: getattr(shared, field)
                for field in Member.model_fields
                if field != "topic_ids"
            },
        )
    )
    scoped_session.flush()

    result = SQLAlchemyRoomRepository(scoped_session, channel_id).joined_channels(ROOM_ID)

    expected = {CURRENT: [SessionChannel(id=DEFAULT_CHANNEL, name=DEFAULT_CHANNEL)]}
    if other_state == "active":
        expected[CURRENT].append(SessionChannel(id=OTHER_CHANNEL, name=OTHER_CHANNEL))
        expected[ELSEWHERE] = [SessionChannel(id=OTHER_CHANNEL, name=OTHER_CHANNEL)]
    assert result == expected


@pytest.mark.parametrize("retain", [False, True])
def test_event_message_query_applies_all_filters_and_bounds_retained_ids(
    scoped_session: Session,
    retain: bool,
) -> None:
    for known_topic_id in (FRONTEND, BACKEND):
        scoped_session.add(
            TopicRecord(
                room_id=ROOM_ID,
                channel_id=DEFAULT_CHANNEL,
                id=known_topic_id,
                name=known_topic_id,
                description="",
            )
        )
    now = datetime.now(UTC)
    fixtures = [
        (MATCHING, DEFAULT_CHANNEL, CURRENT, FRONTEND, "needle%", False),
        (RECIPIENT, DEFAULT_CHANNEL, HISTORICAL, FRONTEND, "needle%", False),
        (WRONG_TOPIC, DEFAULT_CHANNEL, CURRENT, BACKEND, "needle%", False),
        (WRONG_MEMBER, DEFAULT_CHANNEL, HISTORICAL, FRONTEND, "needle%", False),
        (WRONG_KEYWORD, DEFAULT_CHANNEL, CURRENT, FRONTEND, "needleX", False),
        (OTHER_CHANNEL_MESSAGE, OTHER_CHANNEL, ELSEWHERE, None, "needle%", False),
        (UNREQUESTED, DEFAULT_CHANNEL, CURRENT, FRONTEND, "needle%", False),
        (DELETED_MESSAGE, DEFAULT_CHANNEL, CURRENT, FRONTEND, "needle%", True),
    ]
    for sequence, (message_id, channel_id, publisher, topic_id, content, deleted) in enumerate(
        fixtures, 1
    ):
        scoped_session.add(
            MessageRecord(
                room_id=ROOM_ID,
                channel_id=channel_id,
                id=message_id,
                seq=sequence,
                publisher_id=publisher,
                content=content,
                created_at=now,
                is_deleted=deleted,
                deleted_at=now if deleted else None,
            )
        )
        if topic_id:
            scoped_session.add(
                MessageTopicRecord(
                    room_id=ROOM_ID,
                    channel_id=channel_id,
                    message_id=message_id,
                    topic_id=topic_id,
                    position=0,
                )
            )
    scoped_session.add(
        MessageRecipientRecord(
            room_id=ROOM_ID,
            channel_id=DEFAULT_CHANNEL,
            message_id=RECIPIENT,
            member_id=CURRENT,
            position=0,
        )
    )
    scoped_session.flush()
    result = SQLAlchemyMessageRepository(scoped_session, DEFAULT_CHANNEL).message_updates(
        ROOM_ID,
        MessageUpdatesQuery(
            message_ids=[row[0] for row in fixtures if row[0] != UNREQUESTED],
            retained_ids=[WRONG_KEYWORD, OTHER_CHANNEL_MESSAGE, UNREQUESTED, DELETED_MESSAGE]
            if retain
            else [],
            topic_id=FRONTEND,
            member_id=CURRENT,
            keyword="needle%",
        ),
    )
    assert [message.id for message in result] == (
        [MATCHING, RECIPIENT, WRONG_KEYWORD] if retain else [MATCHING, RECIPIENT]
    )


def test_activity_summarizes_new_channel(scoped_session: Session) -> None:
    repository = SQLAlchemyRoomRepository(scoped_session, DEFAULT_CHANNEL)
    activity = repository.activity(ROOM_ID)
    assert activity.summary.total_messages == 0
    assert activity.positions == []
