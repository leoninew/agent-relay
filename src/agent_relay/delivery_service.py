from __future__ import annotations

import logging
import sys
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Event, Thread
from time import monotonic
from typing import BinaryIO, Protocol

from agent_relay.drivers.codex import InputPage, QueueHead, QueueRejected, RpcRejected
from agent_relay.room_store import ClaimedDelivery, SQLiteRoomStore


class QueueDriver(Protocol):
    def enqueue(self, thread_id: str, client_message_id: str, text: str) -> dict[str, object]: ...
    def activation_candidate(self, thread_id: str) -> QueueHead | None: ...
    def activate(self, thread_id: str, queued_submission_id: str) -> str: ...
    def read_input_page(self, thread_id: str, cursor: str | None = None) -> InputPage: ...


class SubmitterLock:
    """One dispatcher per database, including during interrupted-call recovery."""

    def __init__(self, path: Path) -> None:
        self.path = path.with_suffix(path.suffix + ".dispatch.lock")
        self.file: BinaryIO | None = None

    def acquire(self) -> bool:
        stream = self.path.open("a+b")
        try:
            if sys.platform == "win32":
                import msvcrt

                if self.path.stat().st_size == 0:
                    stream.write(b"\0")
                    stream.flush()
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            stream.close()
            return False
        self.file = stream
        return True

    def release(self) -> None:
        if self.file is not None:
            self.file.close()
            self.file = None


class DeliveryService:
    def __init__(
        self,
        store: SQLiteRoomStore,
        driver: QueueDriver,
        logger: logging.Logger,
        concurrency: int,
    ) -> None:
        self.store = store
        self.driver = driver
        self.logger = logger
        self.concurrency = concurrency
        self.stop = Event()
        self.thread = Thread(target=self._run, name="relay-dispatch", daemon=True)
        self.history_cursors: dict[str, str | None] = {}

    def start(self) -> None:
        self.thread.start()

    def close(self) -> None:
        self.stop.set()
        self.thread.join()

    def _run(self) -> None:
        lock = SubmitterLock(self.store.path)
        try:
            while not self.stop.is_set() and not lock.acquire():
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
                        active.add(pool.submit(self.submit, work))
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
                            future = pool.submit(self.observe, session_id, pending[session_id])
                            active.add(future)
                            observations[future] = session_id
                            observation_offset += 1
                        next_observation = monotonic() + 2
                    self.stop.wait(0.2)
                for future in active:
                    self.collect(future)
        except Exception:
            # No RPC is repeated after a local persistence/scheduler failure.
            self.logger.exception("Queue dispatcher stopped")
        finally:
            lock.release()

    def submit(self, work: ClaimedDelivery) -> None:
        try:
            self._submit(work)
        except Exception:
            self.logger.exception("Delivery processing failed delivery=%s", work.delivery.id)
            delivery = work.delivery.model_copy(deep=True)
            delivery.status = "unknown"
            delivery.error = "本次投递处理失败，无法确认入队结果；不会自动重发"
            delivery.updated_at = datetime.now(UTC)
            # Only an unfinished submission can change. A saved queue receipt or
            # received input must survive an error in the later activation step.
            self.store.finish_delivery(work.room_id, delivery)

    def collect(self, future: Future[None]) -> None:
        try:
            future.result()
        except Exception:
            # A local result-write failure belongs to this work item. Never
            # repeat its RPC or stop processing unrelated deliveries.
            self.logger.exception("Unable to finish a delivery task")

    def _submit(self, work: ClaimedDelivery) -> None:
        delivery = work.delivery.model_copy(deep=True)
        sender = f"{work.message.sender_name}（{work.message.sender_id}）"
        text = f"roomId: {work.room_id}\n发送者: {sender}\n\n{work.message.content}"
        try:
            receipt = self.driver.enqueue(
                delivery.target_session_id,
                delivery.client_message_id,
                text,
            )
            delivery.status = "queued"
            delivery.queued_at = datetime.now(UTC)
            delivery.note = "已入队，等待原会话消费；如已中断，请在原 Codex 会话继续"
            delivery.queued_submission_id = str(receipt["id"])
            # queue/add echoes the entire prompt; the delivery receipt stores only metadata.
            delivery.receipt = {key: value for key, value in receipt.items() if key != "input"}
        except QueueRejected:
            delivery.status = "rejected"
            delivery.error = "Codex 明确拒绝本次入队"
            self.logger.exception("Queue rejected delivery=%s", delivery.id)
        except Exception:
            delivery.status = "unknown"
            delivery.error = "无法确认入队结果；不会自动重发"
            self.logger.exception("Queue result unknown delivery=%s", delivery.id)
        delivery.updated_at = datetime.now(UTC)
        self.store.finish_delivery(work.room_id, delivery)
        if delivery.status == "queued":
            self.activate_after_submission(delivery.target_session_id, delivery.client_message_id)

    def activate_after_submission(self, session_id: str, client_message_id: str) -> None:
        """Only a new submission can trigger one guarded start of an existing FIFO head."""
        try:
            head = self.driver.activation_candidate(session_id)
            if head is None or not self.store.claim_activation(session_id, head):
                self.store.delivery_note(
                    session_id,
                    client_message_id,
                    "已入队，等待原会话消费；如已中断，请在原 Codex 会话继续",
                )
                return
            self.driver.activate(session_id, head.id)
            self.store.delivery_note(
                session_id,
                head.client_message_id or client_message_id,
                "已请求启动原队列首项，等待接收确认",
            )
        except RpcRejected:
            # A competing consumer may already have taken this exact item. Never
            # start another item or repeat add in response to the rejection.
            self.store.delivery_note(
                session_id,
                client_message_id,
                "已入队；启动请求未被接受，继续核验原会话输入",
            )
            self.logger.info("Queue activation rejected session=%s", session_id)
        except Exception:
            self.store.delivery_note(
                session_id,
                client_message_id,
                "已入队；无法确认队列启动结果，不重复启动或提交",
            )
            self.logger.exception("Queue activation outcome unknown session=%s", session_id)

    def observe(self, session_id: str, client_message_ids: set[str]) -> None:
        try:
            latest = self.driver.read_input_page(session_id)
            inputs = list(latest.inputs)
            cursor = self.history_cursors.get(session_id)
            if cursor is not None:
                older = self.driver.read_input_page(session_id, cursor)
                inputs.extend(older.inputs)
                self.history_cursors[session_id] = older.next_cursor
            else:
                self.history_cursors[session_id] = latest.next_cursor
            for received in inputs:
                if received.client_message_id in client_message_ids:
                    self.store.confirm_input(session_id, received)
        except Exception:
            # A missing or unreadable history page never proves rejection or
            # receipt and never causes a new queue/add or queue/start.
            self.logger.exception("Input receipt observation unavailable session=%s", session_id)
