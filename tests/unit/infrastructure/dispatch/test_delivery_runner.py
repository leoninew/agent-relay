import logging
from collections.abc import Callable
from concurrent.futures import Future
from unittest.mock import MagicMock, Mock

import pytest

from conflua.application.delivery.ports import DeliveryRepository
from conflua.application.delivery.service import DeliveryService
from conflua.application.dto.delivery import ActivationWork, ClaimedDelivery, DeliveryOutcome
from conflua.infrastructure.dispatch.delivery import DeliveryRunner
from conflua.infrastructure.dispatch.lock import SubmitterLock


@pytest.mark.parametrize("concurrency", [1, 4])
@pytest.mark.parametrize("mode", ["both", "only-observe", "only-submit", "failure"])
def test_dispatch_fairness_remains_bounded_without_real_waits(
    monkeypatch: pytest.MonkeyPatch, concurrency: int, mode: str
) -> None:
    store = Mock(spec=DeliveryRepository)
    store.claim_activation_work.return_value = None
    service = Mock(spec=DeliveryService)
    lock = Mock(spec=SubmitterLock)
    lock.acquire.return_value = True
    store.claim_delivery.return_value = (
        None if mode == "only-observe" else Mock(spec=ClaimedDelivery)
    )
    if mode != "only-observe":
        store.claim_delivery.return_value.delivery = Mock(target_session_id="target")
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
        "conflua.infrastructure.dispatch.delivery.ThreadPoolExecutor", lambda **_: pool
    )
    monkeypatch.setattr("conflua.infrastructure.dispatch.delivery.monotonic", lambda: ticks * 3.0)

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


@pytest.mark.parametrize("concurrency", [1, 4])
@pytest.mark.parametrize("include_save", [False, True])
def test_due_first_activation_checks_cannot_starve_submissions_or_observations(
    monkeypatch: pytest.MonkeyPatch, concurrency: int, include_save: bool
) -> None:
    store = Mock(spec=DeliveryRepository)
    service = Mock(spec=DeliveryService)
    lock = Mock(spec=SubmitterLock)
    lock.acquire.return_value = True
    work = Mock(spec=ClaimedDelivery)
    work.delivery = Mock(target_session_id="pending")
    unsaved = Mock(spec=ClaimedDelivery)
    unsaved.delivery = Mock(target_session_id="unsaved")
    pending_result = DeliveryOutcome(unsaved)
    unsaved_claimed = False
    activation = ActivationWork("activation", "client", "queued")

    def claim(excluded: frozenset[str]) -> ClaimedDelivery | None:
        nonlocal unsaved_claimed
        if include_save and not unsaved_claimed:
            unsaved_claimed = True
            return unsaved
        return None if "pending" in excluded else work

    store.claim_delivery.side_effect = claim
    store.claim_activation_work.side_effect = lambda excluded: (
        None if "activation" in excluded else activation
    )
    store.unconfirmed_inputs.return_value = {"observer": {"client"}}
    pool = MagicMock()
    pool.__enter__.return_value = pool
    runner = DeliveryRunner(store, service, lock, logging.getLogger("tests.runner"), concurrency)
    stop = Mock()
    runner.stop = stop
    ticks = 0
    tasks: list[tuple[str, Future[DeliveryOutcome | None], DeliveryOutcome | None]] = []
    scheduled_at: list[tuple[int, str]] = []

    def submit(operation: object, *args: object) -> Future[DeliveryOutcome | None]:
        kind = (
            "activation"
            if operation is service.check_activation
            else "submit"
            if operation is service.submit
            else "save"
            if operation is service.complete
            else "observe"
        )
        future: Future[DeliveryOutcome | None] = Future()
        result = pending_result if operation is service.complete or args[0] is unsaved else None
        tasks.append((kind, future, result))
        scheduled_at.append((ticks, "initial-save" if args[0] is unsaved else kind))
        return future

    def advance(timeout: float) -> None:
        nonlocal ticks
        ticks += 1
        for _, future, result in tasks:
            if not future.done():
                future.set_result(result)

    stop.is_set.side_effect = lambda: ticks >= 24
    stop.wait.side_effect = advance
    pool.submit.side_effect = submit
    monkeypatch.setattr(
        "conflua.infrastructure.dispatch.delivery.ThreadPoolExecutor", lambda **_: pool
    )
    monkeypatch.setattr("conflua.infrastructure.dispatch.delivery.monotonic", lambda: ticks * 3.0)

    runner._run()

    kinds = [kind for kind, _, _ in tasks]
    assert set(kinds) == (
        {"activation", "submit", "observe", "save"}
        if include_save
        else {"activation", "submit", "observe"}
    )
    writes = [kind for kind in kinds if kind in {"activation", "submit"}]
    assert kinds.count("observe") >= 3 and writes.count("submit") >= 3
    required = {"activation", "submit", "observe"} | ({"save"} if include_save else set())
    for start in range(13):
        assert required <= {kind for tick, kind in scheduled_at if start <= tick < start + 12}
    assert all(future.done() for _, future, _ in tasks)


def test_due_observations_survive_full_capacity_until_a_slot_is_released(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = Mock(spec=DeliveryRepository)
    store.claim_activation_work.return_value = None
    store.claim_delivery.return_value = Mock(spec=ClaimedDelivery)
    store.claim_delivery.return_value.delivery = Mock(target_session_id="target")
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
        "conflua.infrastructure.dispatch.delivery.ThreadPoolExecutor", lambda **_: pool
    )
    monkeypatch.setattr("conflua.infrastructure.dispatch.delivery.monotonic", lambda: ticks * 3.0)

    runner._run()

    assert operations == [service.submit, service.observe]
    lock.release.assert_called_once_with()


@pytest.mark.parametrize("stage", ["activation", "save-retry"])
def test_session_stays_owned_until_activation_or_original_result_save_finishes(
    monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    store = Mock(spec=DeliveryRepository)
    store.claim_activation_work.return_value = None
    service = Mock(spec=DeliveryService)
    lock = Mock(spec=SubmitterLock)
    lock.acquire.return_value = True
    store.unconfirmed_inputs.return_value = {}
    first = Mock(spec=ClaimedDelivery)
    first.delivery = Mock(target_session_id="target")
    following = Mock(spec=ClaimedDelivery)
    following.delivery = Mock(target_session_id="target")
    other = Mock(spec=ClaimedDelivery)
    other.delivery = Mock(target_session_id="other")
    outcome = DeliveryOutcome(first)
    pool = MagicMock()
    pool.__enter__.return_value = pool
    runner = DeliveryRunner(store, service, lock, logging.getLogger("tests.runner"), 2)
    stop = Mock()
    runner.stop = stop
    ticks = 0
    claimed: list[object] = []
    tasks: list[tuple[object, object, Future[DeliveryOutcome | None]]] = []
    exclusions: list[tuple[int, frozenset[str]]] = []

    def claim(excluded: frozenset[str]) -> ClaimedDelivery | None:
        exclusions.append((ticks, excluded))
        if first not in claimed:
            claimed.append(first)
            return first
        if other not in claimed:
            claimed.append(other)
            return other
        if ticks < 4:
            assert "target" in excluded
        elif following not in claimed and "target" not in excluded:
            claimed.append(following)
            return following
        return None

    def submit(operation: object, argument: object) -> Future[DeliveryOutcome | None]:
        future: Future[DeliveryOutcome | None] = Future()
        tasks.append((operation, argument, future))
        return future

    def advance(timeout: float) -> None:
        nonlocal ticks
        ticks += 1
        for operation, argument, future in tasks:
            if future.done():
                continue
            if argument is first:
                if stage == "save-retry":
                    future.set_result(outcome)
                elif ticks >= 4:
                    future.set_result(None)
            elif operation is service.complete:
                if ticks >= 4:
                    future.set_result(None)
            else:
                future.set_result(None)

    store.claim_delivery.side_effect = claim
    stop.is_set.side_effect = lambda: ticks >= 6
    stop.wait.side_effect = advance
    pool.submit.side_effect = submit
    monkeypatch.setattr(
        "conflua.infrastructure.dispatch.delivery.ThreadPoolExecutor", lambda **_: pool
    )
    monkeypatch.setattr("conflua.infrastructure.dispatch.delivery.monotonic", lambda: float(ticks))

    runner._run()

    assert claimed == [first, other, following]
    assert any(0 < tick < 4 and "target" in excluded for tick, excluded in exclusions)
    assert (
        sum(operation is service.submit and argument is first for operation, argument, _ in tasks)
        == 1
    )
    assert sum(operation is service.complete for operation, _, _ in tasks) == (
        stage == "save-retry"
    )
    assert all(future.done() for _, _, future in tasks)
