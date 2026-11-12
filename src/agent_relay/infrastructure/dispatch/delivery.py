import logging
from concurrent.futures import Future, ThreadPoolExecutor
from threading import Event, Thread
from time import monotonic

from agent_relay.application.delivery.ports import DeliveryRepository
from agent_relay.application.delivery.service import DeliveryService
from agent_relay.infrastructure.dispatch.lock import SubmitterLock


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
        self.thread = Thread(target=self._run, name="relay-dispatch", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def close(self) -> None:
        self.stop.set()
        self.thread.join()

    def collect(self, future: Future[None]) -> None:
        try:
            future.result()
        except Exception:
            self.logger.exception("Unable to finish a delivery task")

    def _run(self) -> None:
        try:
            while not self.stop.is_set() and not self.lock.acquire():
                self.stop.wait(0.5)
            if self.stop.is_set():
                return
            self.service.recover()
            with ThreadPoolExecutor(max_workers=self.concurrency) as pool:
                active: set[Future[None]] = set()
                observations: dict[Future[None], str] = {}
                due_observations: dict[str, set[str]] = {}
                next_observation = monotonic()
                prefer_observation = True
                while not self.stop.is_set():
                    done = {future for future in active if future.done()}
                    for future in done:
                        self.collect(future)
                        observations.pop(future, None)
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
                        work = None
                        if not due_observations or not prefer_observation:
                            try:
                                work = self.store.claim_delivery()
                            except Exception:
                                self.logger.exception("Unable to claim a delivery")
                        if work is not None:
                            active.add(pool.submit(self.service.submit, work))
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
