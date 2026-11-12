from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from agent_relay.domain.rooms.models import CapabilityReference
from agent_relay.infrastructure.persistence.types import (
    CapabilityReferences,
    ISODateTime,
    ReceiptMetadata,
)


class Base(DeclarativeBase):
    pass


class RoomRecord(Base):
    __tablename__ = "rooms"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_path: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)


class TopicRecord(Base):
    __tablename__ = "topics"

    room_id: Mapped[str] = mapped_column(Text, ForeignKey("rooms.id"), primary_key=True)
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(ISODateTime)
    deleted_at: Mapped[datetime | None] = mapped_column(ISODateTime)

    __table_args__ = (
        Index(
            "topics_active_name", "room_id", "name", unique=True, sqlite_where=deleted_at.is_(None)
        ),
    )


class SessionRecord(Base):
    __tablename__ = "sessions"

    room_id: Mapped[str] = mapped_column(Text, ForeignKey("rooms.id"), primary_key=True)
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(Text)
    project_path: Mapped[str] = mapped_column(Text)
    presence: Mapped[str] = mapped_column(Text)
    observed_at: Mapped[datetime | None] = mapped_column(ISODateTime)

    __table_args__ = (CheckConstraint("presence IN ('available', 'busy', 'offline', 'unknown')"),)


class MemberRecord(Base):
    __tablename__ = "members"

    room_id: Mapped[str] = mapped_column(Text, ForeignKey("rooms.id"), primary_key=True)
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    session_id: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    initials: Mapped[str] = mapped_column(Text)
    presence: Mapped[str] = mapped_column(Text)
    activity: Mapped[str] = mapped_column(Text)
    activity_source: Mapped[str] = mapped_column(Text)
    observed_at: Mapped[datetime | None] = mapped_column(ISODateTime)
    deleted_at: Mapped[datetime | None] = mapped_column(ISODateTime)

    __table_args__ = (
        ForeignKeyConstraint(["room_id", "session_id"], ["sessions.room_id", "sessions.id"]),
        CheckConstraint("kind IN ('human', 'agent')"),
        CheckConstraint("presence IN ('available', 'busy', 'offline', 'unknown')"),
        CheckConstraint(
            "(kind = 'human' AND session_id IS NULL AND id = 'user' "
            "AND name = '你' AND deleted_at IS NULL) "
            "OR (kind = 'agent' AND session_id IS NOT NULL AND id <> 'user')"
        ),
        Index(
            "members_active_name", "room_id", "name", unique=True, sqlite_where=deleted_at.is_(None)
        ),
        Index(
            "members_active_session",
            "room_id",
            "session_id",
            unique=True,
            sqlite_where=deleted_at.is_(None),
        ),
    )


class MemberTopicRecord(Base):
    __tablename__ = "member_topics"

    room_id: Mapped[str] = mapped_column(Text, primary_key=True)
    member_id: Mapped[str] = mapped_column(Text, primary_key=True)
    topic_id: Mapped[str] = mapped_column(Text, primary_key=True)
    position: Mapped[int]

    __table_args__ = (
        ForeignKeyConstraint(["room_id", "member_id"], ["members.room_id", "members.id"]),
        ForeignKeyConstraint(["room_id", "topic_id"], ["topics.room_id", "topics.id"]),
    )


class MessageRecord(Base):
    __tablename__ = "messages"

    room_id: Mapped[str] = mapped_column(Text, ForeignKey("rooms.id"), primary_key=True)
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    seq: Mapped[int]
    publisher_id: Mapped[str] = mapped_column(Text)
    publication_id: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    capabilities: Mapped[tuple[CapabilityReference, ...]] = mapped_column(
        CapabilityReferences, nullable=False, default=tuple, server_default=text("'[]'")
    )
    reply_to_message_id: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(ISODateTime)
    deleted_at: Mapped[datetime | None] = mapped_column(ISODateTime)

    __table_args__ = (
        CheckConstraint("seq > 0"),
        UniqueConstraint("room_id", "seq"),
        ForeignKeyConstraint(["room_id", "publisher_id"], ["members.room_id", "members.id"]),
        ForeignKeyConstraint(
            ["room_id", "reply_to_message_id"], ["messages.room_id", "messages.id"]
        ),
        CheckConstraint("json_valid(capabilities) AND json_type(capabilities) = 'array'"),
        Index("messages_publication", "room_id", "publisher_id", "publication_id", unique=True),
        Index("messages_sender_page", "room_id", "publisher_id", "seq"),
    )


class MessageTopicRecord(Base):
    __tablename__ = "message_topics"

    room_id: Mapped[str] = mapped_column(Text, primary_key=True)
    message_id: Mapped[str] = mapped_column(Text, primary_key=True)
    topic_id: Mapped[str] = mapped_column(Text, primary_key=True)
    position: Mapped[int]

    __table_args__ = (
        CheckConstraint("position >= 0"),
        ForeignKeyConstraint(["room_id", "message_id"], ["messages.room_id", "messages.id"]),
        ForeignKeyConstraint(["room_id", "topic_id"], ["topics.room_id", "topics.id"]),
        Index("message_topics_topic", "room_id", "topic_id", "message_id"),
    )


class MessageMentionRecord(Base):
    __tablename__ = "message_mentions"

    room_id: Mapped[str] = mapped_column(Text, primary_key=True)
    message_id: Mapped[str] = mapped_column(Text, primary_key=True)
    member_id: Mapped[str] = mapped_column(Text, primary_key=True)
    position: Mapped[int]

    __table_args__ = (
        CheckConstraint("position >= 0"),
        ForeignKeyConstraint(["room_id", "message_id"], ["messages.room_id", "messages.id"]),
        ForeignKeyConstraint(["room_id", "member_id"], ["members.room_id", "members.id"]),
        Index("message_mentions_member", "room_id", "member_id", "message_id"),
    )


class MessageRecipientRecord(Base):
    __tablename__ = "message_recipients"

    room_id: Mapped[str] = mapped_column(Text, primary_key=True)
    message_id: Mapped[str] = mapped_column(Text, primary_key=True)
    member_id: Mapped[str] = mapped_column(Text, primary_key=True)
    position: Mapped[int]

    __table_args__ = (
        CheckConstraint("position >= 0"),
        ForeignKeyConstraint(["room_id", "message_id"], ["messages.room_id", "messages.id"]),
        ForeignKeyConstraint(["room_id", "member_id"], ["members.room_id", "members.id"]),
        Index("message_recipients_member", "room_id", "member_id", "message_id"),
    )


class DeliveryRecord(Base):
    __tablename__ = "deliveries"

    room_id: Mapped[str] = mapped_column(Text, primary_key=True)
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    message_id: Mapped[str] = mapped_column(Text)
    target_member_id: Mapped[str] = mapped_column(Text)
    target_session_id: Mapped[str] = mapped_column(Text)
    client_message_id: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(ISODateTime)
    queued_at: Mapped[datetime | None] = mapped_column(ISODateTime)
    received_at: Mapped[datetime | None] = mapped_column(ISODateTime)
    received_item_id: Mapped[str | None] = mapped_column(Text)
    received_turn_id: Mapped[str | None] = mapped_column(Text)
    activation_attempted_at: Mapped[datetime | None] = mapped_column(ISODateTime)
    note: Mapped[str | None] = mapped_column(Text)
    queued_submission_id: Mapped[str | None] = mapped_column(Text)
    receipt_metadata: Mapped[dict[str, object] | None] = mapped_column(ReceiptMetadata)
    submission_method: Mapped[str | None] = mapped_column(Text)
    steered_turn_id: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(ISODateTime)

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'submitting', 'queued', 'received', 'rejected', 'unknown')"
        ),
        CheckConstraint(
            "receipt_metadata IS NULL OR (queued_submission_id IS NOT NULL "
            "AND json_valid(receipt_metadata) AND json_type(receipt_metadata) = 'object' "
            "AND json_type(receipt_metadata, '$.id') IS NULL "
            "AND json_type(receipt_metadata, '$.clientUserMessageId') IS NULL)"
        ),
        CheckConstraint("submission_method IS NULL OR submission_method IN ('queue', 'steer')"),
        CheckConstraint(
            "submission_method IS NOT 'steer' OR (queued_submission_id IS NULL "
            "AND receipt_metadata IS NULL AND queued_at IS NULL "
            "AND activation_attempted_at IS NULL)"
        ),
        CheckConstraint(
            "steered_turn_id IS NULL OR (submission_method IS 'steer' "
            "AND length(trim(steered_turn_id)) > 0)"
        ),
        CheckConstraint(
            "submission_method IS NOT 'steer' OR status <> 'queued' OR steered_turn_id IS NOT NULL"
        ),
        CheckConstraint(
            "submission_method IS NOT 'steer' OR status <> 'received' OR "
            "(received_at IS NOT NULL AND received_item_id IS NOT NULL "
            "AND received_turn_id IS NOT NULL)"
        ),
        UniqueConstraint("room_id", "message_id", "target_member_id"),
        ForeignKeyConstraint(["room_id", "message_id"], ["messages.room_id", "messages.id"]),
        ForeignKeyConstraint(["room_id", "target_member_id"], ["members.room_id", "members.id"]),
        ForeignKeyConstraint(["room_id", "target_session_id"], ["sessions.room_id", "sessions.id"]),
        Index("deliveries_dispatch", "status", "target_session_id"),
        Index("deliveries_client", "target_session_id", "client_message_id", unique=True),
    )


class RoomEventRecord(Base):
    __tablename__ = "room_events"

    event_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    room_id: Mapped[str] = mapped_column(Text, ForeignKey("rooms.id"))
    kind: Mapped[str] = mapped_column(Text)
    entity_id: Mapped[str] = mapped_column(Text)
    message_id: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("room_events_cursor", "room_id", "event_id"),
        {"sqlite_autoincrement": True},
    )


class ContextQueryRecord(Base):
    __tablename__ = "member_context_queries"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    room_id: Mapped[str] = mapped_column(Text)
    member_id: Mapped[str] = mapped_column(Text)
    message_id: Mapped[str | None] = mapped_column(Text)
    topic_id: Mapped[str | None] = mapped_column(Text)
    keyword: Mapped[str | None] = mapped_column(Text)
    before_seq: Mapped[int | None]
    after_seq: Mapped[int | None]
    page_limit: Mapped[int]
    provided_at: Mapped[datetime] = mapped_column(ISODateTime)

    __table_args__ = (
        UniqueConstraint("room_id", "id"),
        CheckConstraint("before_seq >= 1"),
        CheckConstraint("after_seq >= 0"),
        CheckConstraint("page_limit BETWEEN 1 AND 200"),
        ForeignKeyConstraint(["room_id", "member_id"], ["members.room_id", "members.id"]),
        ForeignKeyConstraint(["room_id", "message_id"], ["messages.room_id", "messages.id"]),
        ForeignKeyConstraint(["room_id", "topic_id"], ["topics.room_id", "topics.id"]),
        Index("member_context_queries_member", "room_id", "member_id"),
    )


class ContextMessageRecord(Base):
    __tablename__ = "member_context_messages"

    room_id: Mapped[str] = mapped_column(Text, primary_key=True)
    query_id: Mapped[str] = mapped_column(Text, primary_key=True)
    message_id: Mapped[str] = mapped_column(Text, primary_key=True)
    position: Mapped[int]

    __table_args__ = (
        CheckConstraint("position >= 0"),
        ForeignKeyConstraint(
            ["room_id", "query_id"], ["member_context_queries.room_id", "member_context_queries.id"]
        ),
        ForeignKeyConstraint(["room_id", "message_id"], ["messages.room_id", "messages.id"]),
    )


class TopicPositionRecord(Base):
    __tablename__ = "member_topic_positions"

    room_id: Mapped[str] = mapped_column(Text, primary_key=True)
    member_id: Mapped[str] = mapped_column(Text, primary_key=True)
    topic_id: Mapped[str] = mapped_column(Text, primary_key=True)
    seq: Mapped[int]
    updated_at: Mapped[datetime] = mapped_column(ISODateTime)

    __table_args__ = (
        CheckConstraint("seq >= 0"),
        ForeignKeyConstraint(["room_id", "member_id"], ["members.room_id", "members.id"]),
        ForeignKeyConstraint(["room_id", "topic_id"], ["topics.room_id", "topics.id"]),
    )
