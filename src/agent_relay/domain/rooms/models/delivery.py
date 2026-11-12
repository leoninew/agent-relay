from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Self

from pydantic import model_validator

from agent_relay.domain.rooms.models.base import RoomModel

type SubmissionMethod = Literal["queue", "steer"]


class Delivery(RoomModel):
    id: str
    target_member_id: str
    target_session_id: str
    client_message_id: str
    status: Literal["pending", "submitting", "queued", "received", "rejected", "unknown"]
    updated_at: datetime
    deleted_at: datetime | None = None
    queued_at: datetime | None = None
    received_at: datetime | None = None
    received_item_id: str | None = None
    received_turn_id: str | None = None
    activation_attempted_at: datetime | None = None
    note: str | None = None
    queued_submission_id: str | None = None
    receipt: dict[str, object] | None = None
    error: str | None = None
    submission_method: SubmissionMethod | None = None
    steered_turn_id: str | None = None

    @model_validator(mode="after")
    def validate_submission(self) -> Self:
        if self.submission_method == "steer":
            if any(
                value is not None
                for value in (
                    self.queued_at,
                    self.queued_submission_id,
                    self.receipt,
                    self.activation_attempted_at,
                )
            ):
                raise ValueError("Steered input cannot have queue receipt or activation facts")
            if self.status == "queued" and not self.steered_turn_id:
                raise ValueError("Accepted steered input requires a turn identity")
            if self.status == "received" and (
                self.received_at is None or not self.received_item_id or not self.received_turn_id
            ):
                raise ValueError("Received steered input requires history evidence")
        if self.steered_turn_id is not None and (
            self.submission_method != "steer" or not self.steered_turn_id.strip()
        ):
            raise ValueError("Steer turn identity requires a steered submission")
        return self


@dataclass(frozen=True)
class SubmissionFailure:
    status: Literal["rejected", "unknown"]
    error: str
