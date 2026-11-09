import logging
from concurrent.futures import Future, ThreadPoolExecutor
from threading import Event, Thread
from time import monotonic

from agent_relay.application.delivery.ports import DeliveryStore
from agent_relay.application.delivery.service import DeliveryService
from agent_relay.infrastructure.dispatch.lock import SubmitterLock


class DeliveryRunner:
    def __init__(
        self,
        store: DeliveryStore,
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
            self.store.interrupt_submissions()
            with ThreadPoolExecutor(max_workers=self.concurrency) as pool:
                active: set[Future[None]] = set()
                observations: dict[Future[None], str] = {}
                next_observation = monotonic()
                observation_offset = 0
                while not self.stop.is_set():
                    done = {future for future in active if future.done()}
                    for future in done:
                        self.collect(future)
                        observations.pop(future, None)
                    active -= done
                    while len(active) < self.concurrency and not self.stop.is_set():
                        try:
                            work = self.store.claim_delivery()
                        except Exception:
                            self.logger.exception("Unable to claim a delivery")
                            break
                        if work is None:
                            break
                        active.add(pool.submit(self.service.submit, work))
                    if len(active) < self.concurrency and monotonic() >= next_observation:
                        try:
                            pending = self.store.unconfirmed_inputs()
                        except Exception:
                            self.logger.exception("Unable to read unconfirmed inputs")
                            pending = {}
                        sessions = list(pending)
                        if sessions:
                            index = observation_offset % len(sessions)
                            sessions = sessions[index:] + sessions[:index]
                        for session_id in sessions:
                            if len(active) >= self.concurrency:
                                break
                            if session_id in observations.values():
                                continue
                            future = pool.submit(
                                self.service.observe, session_id, pending[session_id]
                            )
                            active.add(future)
                            observations[future] = session_id
                            observation_offset += 1
                        next_observation = monotonic() + 2
                    self.stop.wait(0.2)
                for future in active:
                    self.collect(future)
        except Exception:
            self.logger.exception("Queue dispatcher stopped")
        finally:
            self.lock.release()
