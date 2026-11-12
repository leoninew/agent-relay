from datetime import UTC, datetime

import pytest

from agent_relay.domain.rooms.delivery import (
    INTERRUPTED_SUBMISSION,
    PROCESSING_FAILURE,
    REJECTED_SUBMISSION,
    UNCERTAIN_SUBMISSION,
    SubmissionFailure,
    queue_accepted,
    submission_failed,
)
from agent_relay.domain.rooms.models import Delivery


@pytest.fixture
def delivery() -> Delivery:
    return Delivery(
        id="delivery",
        target_member_id="target",
        target_session_id="session",
        client_message_id="client",
        status="submitting",
        updated_at=datetime.now(UTC),
    )


@pytest.mark.parametrize(
    "failure",
    [REJECTED_SUBMISSION, UNCERTAIN_SUBMISSION, PROCESSING_FAILURE, INTERRUPTED_SUBMISSION],
)
def test_submission_failure_preserves_identity_and_does_not_mutate_claim(
    delivery: Delivery,
    failure: SubmissionFailure,
) -> None:
    before = delivery.model_copy(deep=True)
    at = datetime.now(UTC)
    result = submission_failed(delivery, failure, at)
    assert delivery == before and result.id == delivery.id
    assert result.client_message_id == delivery.client_message_id
    assert result.status == failure.status and result.error == failure.error
    assert result.updated_at == at and result.queued_submission_id is None


def test_saved_queue_receipt_cannot_be_replaced_by_a_late_failure(delivery: Delivery) -> None:
    queued = queue_accepted(delivery, "submission", {"id": "receipt"}, datetime.now(UTC))
    with pytest.raises(ValueError):
        submission_failed(queued, PROCESSING_FAILURE, datetime.now(UTC))
    assert queued.status == "queued" and queued.receipt == {"id": "receipt"}
    assert delivery.status == "submitting" and delivery.receipt is None
