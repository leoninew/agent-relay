from agent_relay.application.delivery.ports import ClaimedDelivery, QueueHead, ReceivedInput
from agent_relay.domain.rooms.models import Delivery
from agent_relay.infrastructure.persistence.database import Database
from agent_relay.infrastructure.persistence.repositories.deliveries import (
    SQLAlchemyDeliveryRepository,
)


class SQLAlchemyDeliveryStore:
    def __init__(self, database: Database) -> None:
        self.database = database

    def interrupt_submissions(self) -> None:
        with self.database.write() as session:
            SQLAlchemyDeliveryRepository(session).interrupt_submissions()

    def claim_delivery(self) -> ClaimedDelivery | None:
        with self.database.write() as session:
            return SQLAlchemyDeliveryRepository(session).claim_delivery()

    def finish_delivery(self, room_id: str, delivery: Delivery) -> bool:
        with self.database.write() as session:
            return SQLAlchemyDeliveryRepository(session).finish_delivery(room_id, delivery)

    def claim_activation(self, session_id: str, head: QueueHead) -> bool:
        if head.client_message_id is None:
            return False
        with self.database.write() as session:
            return SQLAlchemyDeliveryRepository(session).claim_activation(session_id, head)

    def delivery_note(self, session_id: str, client_message_id: str, note: str) -> None:
        with self.database.write() as session:
            SQLAlchemyDeliveryRepository(session).delivery_note(session_id, client_message_id, note)

    def unconfirmed_inputs(self) -> dict[str, set[str]]:
        with self.database.read() as session:
            return SQLAlchemyDeliveryRepository(session).unconfirmed_inputs()

    def confirm_input(self, session_id: str, received: ReceivedInput) -> None:
        with self.database.write() as session:
            SQLAlchemyDeliveryRepository(session).confirm_input(session_id, received)
