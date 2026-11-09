from agent_relay.application.delivery.ports import ClaimedDelivery, QueueHead, ReceivedInput
from agent_relay.domain.rooms.models import Delivery


class MemoryDeliveryStore:
    def __init__(self, work: ClaimedDelivery) -> None:
        self.work = work
        self.saved = work.delivery.model_copy(deep=True)
        self.activated = False

    def interrupt_submissions(self) -> None:
        if self.saved.status == "submitting":
            self.saved.status = "unknown"

    def claim_delivery(self) -> ClaimedDelivery | None:
        return None

    def finish_delivery(self, room_id: str, delivery: Delivery) -> None:
        if self.saved.status == "submitting":
            self.saved = delivery.model_copy(deep=True)

    def claim_activation(self, session_id: str, head: QueueHead) -> bool:
        if self.activated or head.client_message_id != self.saved.client_message_id:
            return False
        self.activated = True
        return True

    def delivery_note(self, session_id: str, client_message_id: str, note: str) -> None:
        self.saved.note = note

    def unconfirmed_inputs(self) -> dict[str, set[str]]:
        return {self.saved.target_session_id: {self.saved.client_message_id}}

    def confirm_input(self, session_id: str, received: ReceivedInput) -> None:
        self.saved.status = "received"
        self.saved.received_item_id = received.item_id
        self.saved.received_turn_id = received.turn_id
