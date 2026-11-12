import logging
from collections.abc import Callable
from concurrent.futures import Future
from unittest.mock import MagicMock, Mock

import pytest

from agent_relay.application.delivery.ports import DeliveryRepository
from agent_relay.application.delivery.service import DeliveryService
from agent_relay.application.dto.delivery import ClaimedDelivery
from agent_relay.infrastructure.dispatch.delivery import DeliveryRunner
from agent_relay.infrastructure.dispatch.lock import SubmitterLock


@pytest.mark.parametrize("concurrency", [1, 4])
@pytest.mark.parametrize("mode", ["both", "only-observe", "only-submit", "failure"])
def test_dispatch_fairness_remains_bounded_without_real_waits(
    monkeypatch: pytest.MonkeyPatch, concurrency: int, mode: str
) -> None:
    store = Mock(spec=DeliveryRepository)
    service = Mock(spec=DeliveryService)
    lock = Mock(spec=SubmitterLock)
    lock.acquire.return_value = True
    store.claim_delivery.return_value = (
        None if mode == "only-observe" else Mock(spec=ClaimedDelivery)
    )
    store.unconfirmed_inputs.return_value = (
        {} if mode == "only-submit" else {"first": {"one"}, "second": {"two"}, "third": {"three"}}
    )
    pool = MagicMock()
    pool.__enter__.return_value = pool
    runner = DeliveryRunner(store, service, lock, logging.getLogger("tests.runner"), concurrency)
    stop = Mock()
    runner.stop = stop
    ticks = 0
    tasks: list[tuple[str, str | None, Future[None]]] = []

    def submit(operation: Callable[..., None], *args: object) -> Future[None]:
        in_flight = [task for task in tasks if not task[2].done()]
        assert len(in_flight) < concurrency
        session_id = None
        kind = "submit"
        if operation is service.observe:
            kind = "observe"
            assert isinstance(args[0], str)
            session_id = args[0]
            assert not any(task[1] == session_id for task in in_flight)
        future: Future[None] = Future()
        tasks.append((kind, session_id, future))
        return future

    def advance(timeout: float) -> None:
        nonlocal ticks
        ticks += 1
        for kind, _, future in tasks:
            if not future.done():
                if mode == "failure" and kind == "observe":
                    future.set_exception(RuntimeError("Observation failed"))
                else:
                    future.set_result(None)

    stop.is_set.side_effect = lambda: ticks >= 12
    stop.wait.side_effect = advance
    pool.submit.side_effect = submit
    monkeypatch.setattr(
        "agent_relay.infrastructure.dispatch.delivery.ThreadPoolExecutor", lambda **_: pool
    )
    monkeypatch.setattr(
        "agent_relay.infrastructure.dispatch.delivery.monotonic", lambda: ticks * 3.0
    )

    runner._run()

    kinds = [kind for kind, _, _ in tasks]
    if mode in {"both", "failure"}:
        assert "observe" in kinds and "submit" in kinds
        assert all(
            previous != following for previous, following in zip(kinds, kinds[1:], strict=False)
        )
        assert [session_id for kind, session_id, _ in tasks if kind == "observe"][:3] == [
            "first",
            "second",
            "third",
        ]
    elif mode == "only-observe":
        assert set(kinds) == {"observe"}
    else:
        assert set(kinds) == {"submit"}
    service.recover.assert_called_once_with()
    lock.release.assert_called_once_with()
    assert all(future.done() for _, _, future in tasks)


def test_due_observations_survive_full_capacity_until_a_slot_is_released(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = Mock(spec=DeliveryRepository)
    store.claim_delivery.return_value = Mock(spec=ClaimedDelivery)
    store.unconfirmed_inputs.side_effect = [{}, {"session": {"client"}}, {"session": {"client"}}]
    service = Mock(spec=DeliveryService)
    lock = Mock(spec=SubmitterLock)
    lock.acquire.return_value = True
    pool = MagicMock()
    pool.__enter__.return_value = pool
    runner = DeliveryRunner(store, service, lock, logging.getLogger("tests.runner"), 1)
    stop = Mock()
    runner.stop = stop
    ticks = 0
    operations: list[Callable[..., None]] = []
    futures: list[Future[None]] = []

    def submit(operation: Callable[..., None], *args: object) -> Future[None]:
        operations.append(operation)
        future: Future[None] = Future()
        futures.append(future)
        return future

    def advance(timeout: float) -> None:
        nonlocal ticks
        ticks += 1
        if ticks >= 2:
            for future in futures:
                if not future.done():
                    future.set_result(None)

    stop.is_set.side_effect = lambda: ticks >= 3
    stop.wait.side_effect = advance
    pool.submit.side_effect = submit
    monkeypatch.setattr(
        "agent_relay.infrastructure.dispatch.delivery.ThreadPoolExecutor", lambda **_: pool
    )
    monkeypatch.setattr(
        "agent_relay.infrastructure.dispatch.delivery.monotonic", lambda: ticks * 3.0
    )

    runner._run()

    assert operations == [service.submit, service.observe]
    lock.release.assert_called_once_with()
