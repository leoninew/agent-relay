from datetime import datetime

from agent_relay.domain.rooms.models import Delivery, SubmissionFailure, SubmissionMethod

ACTIVE_DELIVERY_STATUSES = ("pending", "submitting", "queued")
UNCONFIRMED_DELIVERY_STATUSES = ("queued", "unknown")

QUEUED_NOTE = "已入队，等待原会话消费；如已中断，请在原 Codex 会话继续"


REJECTED_SUBMISSION = SubmissionFailure("rejected", "Codex 未接受本次发送")
UNCERTAIN_SUBMISSION = SubmissionFailure("unknown", "无法确认发送结果；不会自动重发")
PROCESSING_FAILURE = SubmissionFailure(
    "unknown", "本次投递处理失败，无法确认发送结果；不会自动重发"
)
INTERRUPTED_SUBMISSION = SubmissionFailure("unknown", "提交中断，发送结果未知；不会自动重发")


def queue_accepted(
    delivery: Delivery, submission_id: str, receipt: dict[str, object], at: datetime
) -> Delivery:
    if delivery.status != "submitting":
        raise ValueError("Only a submitting delivery can receive a queue result")
    result = delivery.model_copy(deep=True)
    result.status = "queued"
    result.submission_method = "queue"
    result.queued_at = at
    result.updated_at = at
    result.note = QUEUED_NOTE
    result.queued_submission_id = submission_id
    result.receipt = dict(receipt)
    return result


def steer_accepted(delivery: Delivery, turn_id: str, at: datetime) -> Delivery:
    if delivery.status != "submitting" or not turn_id.strip():
        raise ValueError("Only a submitting delivery can receive a valid steer result")
    result = delivery.model_copy(deep=True)
    result.status = "queued"
    result.submission_method = "steer"
    result.steered_turn_id = turn_id
    result.updated_at = at
    result.note = "已送入当前轮次，等待输入接收确认"
    return result


def submission_failed(
    delivery: Delivery,
    failure: SubmissionFailure,
    at: datetime,
    method: SubmissionMethod | None = None,
) -> Delivery:
    if delivery.status != "submitting":
        raise ValueError("Only a submitting delivery can receive a queue result")
    result = delivery.model_copy(deep=True)
    result.status = failure.status
    result.error = failure.error
    if method is not None:
        result.submission_method = method
    result.updated_at = at
    return result
