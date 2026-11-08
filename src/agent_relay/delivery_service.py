from __future__ import annotations

import json
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
        public_url: str,
    ) -> None:
        self.store = store
        self.driver = driver
        self.logger = logger
        self.concurrency = concurrency
        self.public_url = public_url.rstrip("/")
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
        envelope: dict[str, object] = {
            "roomId": work.room_id,
            "roomName": work.room.name,
            "messageId": work.message.id,
            "seq": work.message.seq,
            "senderId": work.message.sender_id,
            "senderName": work.message.sender_name,
            "senderKind": "member" if work.message.sender_id is not None else "user",
            "topicIds": work.message.topic_ids,
            "mentionedMemberIds": work.message.mentioned_member_ids,
            "targetMemberId": delivery.target_member_id,
            "replyToMessageId": work.message.reply_to_message_id,
            "content": work.message.content,
        }
        envelope["deliveryInstructions"] = (
            "这是发送者向当前目标会话投递的消息；targetMemberId 是接收者，不是发送者。"
            "senderKind=user 时消息来自聊天室用户，即使话题只有当前成员也应接收。"
            "下面的成员发布规则只适用于你决定另发一条聊天室消息，不影响接收本条消息。"
        )
        member_url = f"{self.public_url}/api/room/{work.room_id}/member/{delivery.target_member_id}"
        envelope["publish"] = {
            "method": "POST",
            "url": f"{member_url}/message",
            "lookupUrl": f"{member_url}/publication/{{publicationId}}",
            "headers": {"Content-Type": "application/json"},
            "instructions": (
                "如需在聊天室发言，用现有 HTTP 工具向 url 提交 JSON："
                "publicationId（为这次发布生成并保留唯一编号）、content、topicIds、"
                "mentionedMemberIds，以及可选 replyToMessageId。"
                "必须明确指定话题或 @ 成员；可从 context.catalogUrl 查询目标 ID。"
                "服务按 URL 中的聊天室和成员记录发送者，并排除自己。"
                "引用不会继承目标；引用当前消息需显式填本条 messageId。"
                "响应不确定时用原 publicationId 查询 lookupUrl，"
                "查无记录再用原编号和相同请求补交。"
                "只在决定发布时调用；普通过程输出和最终答复不会自动进入聊天室。"
            ),
        }
        envelope["context"] = {
            "catalogUrl": f"{member_url}/catalog",
            "queryUrl": f"{member_url}/context",
            "positionsUrl": f"{member_url}/position",
            "headers": {"Content-Type": "application/json"},
            "instructions": (
                "仅在需要背景时用现有 HTTP 工具查阅。"
                "GET catalogUrl 获取活动话题/成员 ID 及路径所指成员的订阅标记；"
                "向 queryUrl POST JSON（Content-Type: application/json）："
                "{messageId} 查单条，{topicId} 查订阅话题，"
                "或 {keyword, topicId?} 按正文区分大小写的字面子串搜索。"
                "列表可选 limit（默认50，最多200）、beforeSeq 或 afterSeq（二者互斥）；"
                "响应按 seq 正序，hasMore 时沿用筛选并使用 nextBeforeSeq/nextAfterSeq 翻页。"
                "只可查订阅话题，或逐条查该成员实际收到的消息；引用不扩大范围。"
                "响应仅含本次选取消息；queryId 记录服务提供事实，positions 是相关查阅位置。"
                "GET positionsUrl 只查看位置和位置后新增数；位置允许跳读与回查，"
                "不代表已读或任务完成，也不要求补读。"
            ),
        }
        text = "聊天室消息\n" + json.dumps(envelope, ensure_ascii=False)
        try:
            receipt = self.driver.enqueue(
                delivery.target_session_id, delivery.client_message_id, text
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
