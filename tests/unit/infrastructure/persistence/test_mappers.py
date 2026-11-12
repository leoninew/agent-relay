from datetime import UTC, datetime

import pytest

from agent_relay.domain.rooms.models import Delivery
from agent_relay.infrastructure.persistence.mappers import delivery_from_model, delivery_to_model


@pytest.mark.parametrize("metadata", [None, {}, {"accepted": True, "details": {"attempt": 1}}])
def test_delivery_round_trip_stores_only_extra_receipt_metadata(
    metadata: dict[str, object] | None,
) -> None:
    receipt = (
        {"id": "queued-id", "clientUserMessageId": "client-id", **metadata}
        if metadata is not None
        else None
    )
    observed_at = datetime.now(UTC)
    delivery = Delivery(
        id="delivery-id",
        target_member_id="member-id",
        target_session_id="session-id",
        client_message_id="client-id",
        status="received" if receipt is not None else "unknown",
        updated_at=observed_at,
        queued_at=observed_at if receipt is not None else None,
        received_at=observed_at if receipt is not None else None,
        received_item_id="item-id" if receipt is not None else None,
        received_turn_id="turn-id" if receipt is not None else None,
        activation_attempted_at=observed_at if receipt is not None else None,
        note=None if receipt is not None else "observation note",
        error=None if receipt is not None else "observation error",
        queued_submission_id="queued-id" if receipt is not None else None,
        receipt=receipt,
    )
    model = delivery_to_model("room", "message", delivery)
    assert model.receipt_metadata == metadata
    assert delivery_from_model(model) == delivery
    assert delivery.receipt == receipt


@pytest.mark.parametrize("field", ["id", "clientUserMessageId"])
def test_delivery_rejects_receipt_identifiers_that_disagree_with_columns(field: str) -> None:
    receipt: dict[str, object] = {"id": "queued-id", "clientUserMessageId": "client-id"}
    receipt[field] = "another-id"
    delivery = Delivery(
        id="delivery-id",
        target_member_id="member-id",
        target_session_id="session-id",
        client_message_id="client-id",
        status="queued",
        updated_at=datetime.now(UTC),
        queued_submission_id="queued-id",
        receipt=receipt,
    )
    with pytest.raises(ValueError, match="identifiers"):
        delivery_to_model("room", "message", delivery)


@pytest.mark.parametrize("status", ["queued", "unknown", "received"])
def test_steered_delivery_keeps_distinct_submission_and_history_facts(status: str) -> None:
    at = datetime.now(UTC)
    delivery = Delivery.model_validate(
        {
            "id": "delivery",
            "target_member_id": "member",
            "target_session_id": "session",
            "client_message_id": "client",
            "status": status,
            "updated_at": at,
            "submission_method": "steer",
            "steered_turn_id": "accepted-turn" if status != "unknown" else None,
            "received_at": at if status == "received" else None,
            "received_item_id": "input-item" if status == "received" else None,
            "received_turn_id": "history-turn" if status == "received" else None,
        }
    )
    record = delivery_to_model("room", "message", delivery)
    assert record.queued_submission_id is None and record.receipt_metadata is None
    assert record.queued_at is None
    assert delivery_from_model(record) == delivery


@pytest.mark.parametrize(
    "conflict",
    [
        {"queued_submission_id": "queue-id"},
        {"receipt": {}},
        {"queued_at": datetime.now(UTC)},
        {"activation_attempted_at": datetime.now(UTC)},
        {"submission_method": "queue"},
        {"steered_turn_id": None},
    ],
)
def test_persistence_rejects_contradictory_facts_even_after_unvalidated_copy(
    conflict: dict[str, object],
) -> None:
    delivery = Delivery(
        id="delivery",
        target_member_id="member",
        target_session_id="session",
        client_message_id="client",
        status="queued",
        updated_at=datetime.now(UTC),
        submission_method="steer",
        steered_turn_id="turn",
    ).model_copy(update=conflict)
    with pytest.raises(ValueError):
        delivery_to_model("room", "message", delivery)


def test_uncertain_steer_can_be_confirmed_by_history_without_inventing_a_steer_receipt() -> None:
    at = datetime.now(UTC)
    uncertain = Delivery(
        id="delivery",
        target_member_id="member",
        target_session_id="session",
        client_message_id="client",
        status="unknown",
        updated_at=at,
        submission_method="steer",
    )
    received = uncertain.model_copy(
        update={
            "status": "received",
            "received_at": at,
            "received_item_id": "history-input",
            "received_turn_id": "history-turn",
        }
    )
    record = delivery_to_model("room", "message", received)
    assert delivery_from_model(record) == received
    assert record.steered_turn_id is None
    assert record.queued_submission_id is None and record.receipt_metadata is None
