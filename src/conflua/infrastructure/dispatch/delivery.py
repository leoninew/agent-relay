import logging
from concurrent.futures import Future, ThreadPoolExecutor
from threading import Event, Thread
from time import monotonic

from conflua.application.delivery.ports import DeliveryRepository
from conflua.application.delivery.service import DeliveryService
from conflua.application.dto.delivery import DeliveryOutcome
from conflua.infrastructure.dispatch.lock import SubmitterLock


class DeliveryRunner:
    def __init__(
        self,
        store: DeliveryRepository,
        service: DeliveryService,
        lock: SubmitterLock,
        logger: logging.Logger,
        concurrency: int,
    ) -> None:
        self.store = store
        self.service = service
        self.lock = lock
        self.logger = logger
        self.concurrency = concurrency
        self.stop = Event()
        self.thread = Thread(target=self._run, name="conflua-dispatch", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def close(self) -> None:
        self.stop.set()
        self.thread.join()

    def collect(self, future: Future[DeliveryOutcome | None]) -> DeliveryOutcome | None:
        try:
            return future.result()
        except Exception:
            self.logger.exception("Unable to finish a delivery task")
            return None

    def _run(self) -> None:
        try:
            while not self.stop.is_set() and not self.lock.acquire():
                self.stop.wait(0.5)
            if self.stop.is_set():
                return
            self.service.recover()
            with ThreadPoolExecutor(max_workers=self.concurrency) as pool:
                active: set[Future[DeliveryOutcome | None]] = set()
                observations: dict[Future[DeliveryOutcome | None], str] = {}
                submissions: dict[Future[DeliveryOutcome | None], str] = {}
                pending_results: dict[str, tuple[DeliveryOutcome, float]] = {}
                due_observations: dict[str, set[str]] = {}
                next_observation = monotonic()
                prefer_observation = True
                prefer_activation = True
                prefer_result = True
                while not self.stop.is_set():
                    done = {future for future in active if future.done()}
                    for future in done:
                        outcome = self.collect(future)
                        observations.pop(future, None)
                        submissions.pop(future, None)
                        if outcome is not None:
                            pending_results[outcome.work.delivery.target_session_id] = (
                                outcome,
                                monotonic() + 1,
                            )
                    active -= done
                    if monotonic() >= next_observation:
                        try:
                            pending = self.store.unconfirmed_inputs()
                        except Exception:
                            self.logger.exception("Unable to read unconfirmed inputs")
                        else:
                            due_observations = {
                                session_id: pending[session_id]
                                for session_id in due_observations
                                if session_id in pending
                            }
                            for session_id, client_ids in pending.items():
                                if session_id not in observations.values():
                                    due_observations[session_id] = client_ids
                        next_observation = monotonic() + 2
                    while len(active) < self.concurrency and not self.stop.is_set():
                        ready_result = next(
                            (
                                session_id
                                for session_id, (_, due) in pending_results.items()
                                if due <= monotonic()
                            ),
                            None,
                        )
                        if (
                            ready_result is not None
                            and prefer_result
                            and (not due_observations or not prefer_observation)
                        ):
                            outcome, _ = pending_results.pop(ready_result)
                            future = pool.submit(self.service.complete, outcome)
                            active.add(future)
                            submissions[future] = ready_result
                            prefer_result = False
                            prefer_observation = True
                            continue
                        work = None
                        if not due_observations or not prefer_observation:
                            try:
                                excluded = frozenset(submissions.values()) | frozenset(
                                    pending_results
                                )
                                activation = None
                                if prefer_activation:
                                    activation = self.store.claim_activation_work(excluded)
                                    if activation is None:
                                        work = self.store.claim_delivery(excluded)
                                else:
                                    work = self.store.claim_delivery(excluded)
                                    if work is None:
                                        activation = self.store.claim_activation_work(excluded)
                                if activation is not None:
                                    future = pool.submit(self.service.check_activation, activation)
                                    active.add(future)
                                    submissions[future] = activation.session_id
                                    prefer_observation = True
                                    prefer_activation = False
                                    prefer_result = True
                                    continue
                            except Exception:
                                self.logger.exception("Unable to claim a delivery")
                        if work is not None:
                            future = pool.submit(self.service.submit, work)
                            active.add(future)
                            submissions[future] = work.delivery.target_session_id
                            prefer_observation = True
                            prefer_activation = True
                            prefer_result = True
                        elif ready_result is not None and (
                            not due_observations or not prefer_observation
                        ):
                            outcome, _ = pending_results.pop(ready_result)
                            future = pool.submit(self.service.complete, outcome)
                            active.add(future)
                            submissions[future] = ready_result
                            prefer_result = False
                            prefer_observation = True
                        elif due_observations:
                            session_id = next(iter(due_observations))
                            future = pool.submit(
                                self.service.observe, session_id, due_observations.pop(session_id)
                            )
                            active.add(future)
                            observations[future] = session_id
                            prefer_observation = False
                        else:
                            break
                    self.stop.wait(0.2)
                for future in active:
                    self.collect(future)
        except Exception:
            self.logger.exception("Queue dispatcher stopped")
        finally:
            self.lock.release()
