from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from agent_relay.domain.rooms.models import Delivery

ACTIVE_DELIVERY_STATUSES = ("pending", "submitting", "queued")
UNCONFIRMED_DELIVERY_STATUSES = ("queued", "unknown")

QUEUED_NOTE = "已入队，等待原会话消费；如已中断，请在原 Codex 会话继续"


@dataclass(frozen=True)
class SubmissionFailure:
    status: Literal["rejected", "unknown"]
    error: str


REJECTED_SUBMISSION = SubmissionFailure("rejected", "Codex 明确拒绝本次入队")
UNCERTAIN_SUBMISSION = SubmissionFailure("unknown", "无法确认入队结果；不会自动重发")
PROCESSING_FAILURE = SubmissionFailure(
    "unknown", "本次投递处理失败，无法确认入队结果；不会自动重发"
)
INTERRUPTED_SUBMISSION = SubmissionFailure("unknown", "提交中断，入队结果未知；不会自动重发")


def queue_accepted(
    delivery: Delivery, submission_id: str, receipt: dict[str, object], at: datetime
) -> Delivery:
    if delivery.status != "submitting":
        raise ValueError("Only a submitting delivery can receive a queue result")
    result = delivery.model_copy(deep=True)
    result.status = "queued"
    result.queued_at = at
    result.updated_at = at
    result.note = QUEUED_NOTE
    result.queued_submission_id = submission_id
    result.receipt = dict(receipt)
    return result


def submission_failed(delivery: Delivery, failure: SubmissionFailure, at: datetime) -> Delivery:
    if delivery.status != "submitting":
        raise ValueError("Only a submitting delivery can receive a queue result")
    result = delivery.model_copy(deep=True)
    result.status = failure.status
    result.error = failure.error
    result.updated_at = at
    return result
