from copy import deepcopy

from agent_relay.domain.rooms.models import (
    Delivery,
    Member,
    Message,
    Room,
    Session,
    Topic,
)
from agent_relay.infrastructure.persistence.models import (
    DeliveryRecord,
    MemberRecord,
    MessageRecord,
    RoomRecord,
    SessionRecord,
    TopicRecord,
)


def room_from_model(record: RoomRecord) -> Room:
    return Room(
        id=record.id,
        name=record.name,
        project_path=record.project_path,
        description=record.description,
    )


def topic_from_model(record: TopicRecord) -> Topic:
    return Topic(
        id=record.id,
        name=record.name,
        description=record.description,
        created_at=record.created_at,
        deleted_at=record.deleted_at,
    )


def session_from_model(record: SessionRecord) -> Session:
    return Session.model_validate(
        {
            "id": record.id,
            "name": record.name,
            "provider": record.provider,
            "project_path": record.project_path,
            "presence": record.presence,
            "observed_at": record.observed_at,
        }
    )


def member_from_model(record: MemberRecord, topic_ids: list[str]) -> Member:
    return Member.model_validate(
        {
            "id": record.id,
            "name": record.name,
            "session_id": record.session_id,
            "kind": record.kind,
            "initials": record.initials,
            "presence": record.presence,
            "activity": record.activity,
            "activity_source": record.activity_source,
            "observed_at": record.observed_at,
            "deleted_at": record.deleted_at,
            "topic_ids": list(topic_ids),
        }
    )


def delivery_values(delivery: Delivery) -> dict[str, object]:
    delivery = Delivery.model_validate(delivery.model_dump())
    values = delivery.model_dump(exclude={"receipt"})
    receipt = delivery.receipt
    if receipt is not None and (
        delivery.queued_submission_id is None
        or receipt.get("id") != delivery.queued_submission_id
        or receipt.get("clientUserMessageId") != delivery.client_message_id
    ):
        raise ValueError("Queue receipt does not match the delivery identifiers")
    values["receipt_metadata"] = (
        {key: value for key, value in receipt.items() if key not in {"id", "clientUserMessageId"}}
        if receipt is not None
        else None
    )
    return values


def delivery_to_model(room_id: str, message_id: str, delivery: Delivery) -> DeliveryRecord:
    return DeliveryRecord(room_id=room_id, message_id=message_id, **delivery_values(delivery))


def delivery_from_model(record: DeliveryRecord) -> Delivery:
    receipt = (
        {
            **deepcopy(record.receipt_metadata),
            "id": record.queued_submission_id,
            "clientUserMessageId": record.client_message_id,
        }
        if record.receipt_metadata is not None
        else None
    )
    return Delivery.model_validate(
        {
            "id": record.id,
            "target_member_id": record.target_member_id,
            "target_session_id": record.target_session_id,
            "client_message_id": record.client_message_id,
            "status": record.status,
            "updated_at": record.updated_at,
            "deleted_at": record.deleted_at,
            "queued_at": record.queued_at,
            "received_at": record.received_at,
            "received_item_id": record.received_item_id,
            "received_turn_id": record.received_turn_id,
            "activation_attempted_at": record.activation_attempted_at,
            "note": record.note,
            "queued_submission_id": record.queued_submission_id,
            "receipt": receipt,
            "error": record.error,
            "submission_method": record.submission_method,
            "steered_turn_id": record.steered_turn_id,
        }
    )


def message_from_model(
    record: MessageRecord,
    *,
    sender_name: str,
    topic_ids: list[str],
    mentioned_member_ids: list[str],
    recipient_ids: list[str],
    deliveries: list[Delivery],
) -> Message:
    return Message(
        id=record.id,
        publication_id=record.publication_id,
        seq=record.seq,
        sender_id=record.publisher_id,
        sender_name=sender_name,
        content=record.content,
        capabilities=record.capabilities,
        topic_ids=list(topic_ids),
        mentioned_member_ids=list(mentioned_member_ids),
        recipient_ids=list(recipient_ids),
        reply_to_message_id=record.reply_to_message_id,
        created_at=record.created_at,
        deliveries=list(deliveries),
    )
