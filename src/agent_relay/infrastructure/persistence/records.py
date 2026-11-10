import json
import sqlite3
from collections.abc import Mapping
from typing import Any

from agent_relay.domain.rooms.models import Delivery, Member, Message


def member_from_record(row: Mapping[str, Any], topic_ids: list[str]) -> Member:
    return Member.model_validate({**row, "topic_ids": topic_ids})


def delivery_record(delivery: Delivery) -> dict[str, str | None]:
    record = {
        "id": delivery.id,
        "target_member_id": delivery.target_member_id,
        "target_session_id": delivery.target_session_id,
        "client_message_id": delivery.client_message_id,
        "status": delivery.status,
        "updated_at": delivery.updated_at.isoformat(),
        "queued_at": delivery.queued_at.isoformat() if delivery.queued_at else None,
        "received_at": delivery.received_at.isoformat() if delivery.received_at else None,
        "received_item_id": delivery.received_item_id,
        "received_turn_id": delivery.received_turn_id,
        "activation_attempted_at": (
            delivery.activation_attempted_at.isoformat()
            if delivery.activation_attempted_at
            else None
        ),
        "note": delivery.note,
        "queued_submission_id": delivery.queued_submission_id,
        "error": delivery.error,
    }
    receipt = delivery.receipt
    if receipt is not None and (
        receipt.get("id") != delivery.queued_submission_id
        or receipt.get("clientUserMessageId") != delivery.client_message_id
    ):
        raise ValueError("Queue receipt does not match the delivery identifiers")
    record["receipt_metadata"] = (
        json.dumps(
            {
                key: value
                for key, value in receipt.items()
                if key not in {"id", "clientUserMessageId"}
            },
            ensure_ascii=False,
        )
        if receipt is not None
        else None
    )
    return record


def delivery_from_record(row: Mapping[str, Any]) -> Delivery:
    record = dict(row)
    metadata = record.pop("receipt_metadata")
    record["receipt"] = (
        {
            **json.loads(metadata),
            "id": record["queued_submission_id"],
            "clientUserMessageId": record["client_message_id"],
        }
        if metadata is not None
        else None
    )
    return Delivery.model_validate(record)


def messages_from_rows(
    connection: sqlite3.Connection, room_id: str, rows: list[sqlite3.Row]
) -> list[Message]:
    if not rows:
        return []
    topics: dict[str, list[str]] = {}
    mentions: dict[str, list[str]] = {}
    recipients: dict[str, list[str]] = {}
    slots = ",".join("?" for _ in rows)
    message_ids = [row["id"] for row in rows]
    for table, column, targets in (
        ("message_topics", "topic_id", topics),
        ("message_mentions", "member_id", mentions),
        ("message_recipients", "member_id", recipients),
    ):
        for relation in connection.execute(
            f"SELECT message_id, {column} FROM {table} WHERE room_id = ? "
            f"AND message_id IN ({slots}) ORDER BY position",
            (room_id, *message_ids),
        ):
            targets.setdefault(relation["message_id"], []).append(relation[column])
    return [
        Message.model_validate(
            {
                **dict(row),
                "sender_id": row["publisher_id"],
                "topic_ids": topics.get(row["id"], []),
                "mentioned_member_ids": mentions.get(row["id"], []),
                "recipient_ids": recipients.get(row["id"], []),
                "deliveries": [],
            }
        )
        for row in rows
    ]
