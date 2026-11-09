from agent_relay.application.delivery.ports import InputPage, QueueHead, QueueReceipt, ReceivedInput
from agent_relay.application.members.sessions import SessionInfo


class FakeSessionDriver:
    """Metadata only: no method can create, resume or mutate a Codex thread."""

    def __init__(self, sessions: list[SessionInfo] | None = None) -> None:
        self.sessions = {info.id: info for info in sessions or []}
        self.inspected: list[str] = []
        self.listed = 0
        self.error: Exception | None = None

    def list_sessions(self) -> list[SessionInfo]:
        self.listed += 1
        if self.error:
            raise self.error
        return list(self.sessions.values())

    def inspect(self, thread_id: str) -> SessionInfo:
        self.inspected.append(thread_id)
        if self.error:
            raise self.error
        return self.sessions[thread_id]


class FakeQueueDriver:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []
        self.heads: dict[str, QueueHead] = {}
        self.activations: list[tuple[str, str]] = []
        self.inputs: dict[str, list[ReceivedInput]] = {}

    def enqueue(self, thread_id: str, client_message_id: str, text: str) -> QueueReceipt:
        self.calls.append((thread_id, client_message_id, text))
        return QueueReceipt(
            "queue-" + client_message_id,
            {"id": "queue-" + client_message_id, "clientUserMessageId": client_message_id},
        )

    def activation_candidate(self, thread_id: str) -> QueueHead | None:
        return self.heads.get(thread_id)

    def activate(self, thread_id: str, queued_submission_id: str) -> str:
        self.activations.append((thread_id, queued_submission_id))
        head = self.heads.pop(thread_id)
        assert head.client_message_id is not None
        turn_id = "turn-" + head.client_message_id
        self.inputs.setdefault(thread_id, []).append(
            ReceivedInput(head.client_message_id, "item-" + head.client_message_id, turn_id)
        )
        return turn_id

    def read_input_page(self, thread_id: str, cursor: str | None = None) -> InputPage:
        return InputPage(tuple(self.inputs.get(thread_id, [])), None)
