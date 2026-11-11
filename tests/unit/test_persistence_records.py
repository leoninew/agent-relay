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
