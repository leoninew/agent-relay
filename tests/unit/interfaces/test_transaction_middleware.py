import asyncio
from dataclasses import dataclass, field

import pytest
from starlette.types import Message, Receive, Scope, Send

from agent_relay.interfaces.http.middleware import RequestTransactionMiddleware


@dataclass
class RecordingTransaction:
    commits: list[bool] = field(default_factory=list)
    finished: bool = False

    def finish(self, *, commit: bool) -> None:
        if not self.finished:
            self.commits.append(commit)
            self.finished = True


@pytest.mark.parametrize("status", [201, 409])
def test_transaction_finishes_before_the_response_is_sent(status: int) -> None:
    transaction = RecordingTransaction()

    async def application(scope: Scope, receive: Receive, send: Send) -> None:
        assert scope["state"]["database_transaction"] is transaction
        await send({"type": "http.response.start", "status": status, "headers": []})

    async def receive() -> Message:
        return {"type": "http.request"}

    async def send(message: Message) -> None:
        assert transaction.commits == [status < 400]

    middleware = RequestTransactionMiddleware(application, transaction_factory=lambda: transaction)
    asyncio.run(middleware({"type": "http"}, receive, send))
    assert transaction.commits == [status < 400]


def test_application_exception_rolls_back_before_propagating() -> None:
    transaction = RecordingTransaction()

    async def application(scope: Scope, receive: Receive, send: Send) -> None:
        raise RuntimeError("failed")

    async def receive() -> Message:
        return {"type": "http.request"}

    async def send(message: Message) -> None:
        pytest.fail("A failed application must not send a response")

    middleware = RequestTransactionMiddleware(application, transaction_factory=lambda: transaction)
    with pytest.raises(RuntimeError, match="failed"):
        asyncio.run(middleware({"type": "http"}, receive, send))
    assert transaction.commits == [False]
