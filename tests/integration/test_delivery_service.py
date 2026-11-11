import logging
from pathlib import Path
from time import monotonic, sleep
from uuid import uuid4

from fastapi.testclient import TestClient
from room_fixtures import DemoRoomService, create_room_store, open_room_store
from session_fixtures import FakeQueueDriver, FakeSessionDriver

from agent_relay.application.delivery.ports import InputPage, QueueHead, QueueReceipt, ReceivedInput
from agent_relay.application.delivery.service import DeliveryService
from agent_relay.application.members.service import MemberSessions
from agent_relay.application.members.sessions import SessionInfo
from agent_relay.application.rooms.contracts import (
    CreateMember,
    CreateMessage,
    CreateRoom,
    CreateTopic,
    UpdateMember,
)
from agent_relay.application.rooms.service import RoomService
from agent_relay.bootstrap.http import create_app
from agent_relay.infrastructure.dispatch.lock import SubmitterLock


def test_publication_replay_and_lookup_keep_frozen_recipients(tmp_path: Path) -> None:
    store = create_room_store(tmp_path / "rooms.sqlite3")
    service = DemoRoomService(store)
    request = CreateMessage(
        publication_id=str(uuid4()),
        content="发布快照",
        topic_ids=["frontend", "frontend"],
        mentioned_member_ids=["test-worker", "backend-worker"],
    )
    published = service.post_message("agent-relay", request)
    service.update_member(
        "agent-relay", "backend-worker", UpdateMember(name="后端成员", topic_ids=["frontend"])
    )
    service.delete_member("agent-relay", "frontend-worker")
    reopened = RoomService(open_room_store(store.path))
    assert reopened.post_message("agent-relay", request) == published
    assert reopened.publication("agent-relay", request.publication_id) == published
    assert len(reopened.snapshot("agent-relay").messages) == 7
    assert len({d.target_session_id for d in published.deliveries}) == 4
    assert (
        next(
            d for d in published.deliveries if d.target_member_id == "frontend-worker"
        ).target_session_id
        == "agent-relay-frontend"
    )


def test_web_publications_reach_original_sessions_and_results_survive_restart(
    tmp_path: Path,
) -> None:
    store = create_room_store(tmp_path / "rooms.sqlite3")
    DemoRoomService(store)
    driver = FakeQueueDriver()
    logger = logging.getLogger("tests.queue")
    # Drain existing fixture messages using the same durable claiming path.
    submitter = DeliveryService(store, driver, logger)
    while work := store.claim_delivery():
        submitter.submit(work)
    driver.calls.clear()
    app = create_app(
        logger, database=store.database, session_driver=FakeSessionDriver(), queue_driver=driver
    )
    publications: list[dict[str, object]] = []
    with TestClient(app) as client:
        for topics, mentions in [
            (["frontend"], []),
            ([], ["backend-worker"]),
            (["backend"], ["backend-worker", "frontend-worker"]),
        ]:
            request = {
                "publicationId": str(uuid4()),
                "content": "仅验证投递",
                "topicIds": topics,
                "mentionedMemberIds": mentions,
            }
            response = client.post("/api/room/agent-relay/message", json=request)
            assert response.status_code == 201
            message = response.json()
            publications.append(message)
            assert (
                client.post("/api/room/agent-relay/message", json=request).json()["id"]
                == message["id"]
            )
        deadline = monotonic() + 5
        while monotonic() < deadline:
            results = [
                client.get(f"/api/room/agent-relay/publication/{m['publicationId']}").json()
                for m in publications
            ]
            if all(d["status"] == "queued" for m in results for d in m["deliveries"]):
                break
            sleep(0.02)
        assert all(d["status"] == "queued" for m in results for d in m["deliveries"])
        assert not SubmitterLock(store.path).acquire()
    assert not app.state.delivery_runner.thread.is_alive()
    lock = SubmitterLock(store.path)
    assert lock.acquire()
    lock.release()
    reopened = RoomService(open_room_store(store.path))
    for result in results:
        saved = reopened.publication("agent-relay", result["publicationId"])
        assert saved.model_dump(mode="json", by_alias=True) == result
        for delivery in saved.deliveries:
            assert delivery.receipt == {
                "id": delivery.queued_submission_id,
                "clientUserMessageId": delivery.client_message_id,
            }
    assert len(driver.calls) == sum(len(m["deliveries"]) for m in results)
    for session_id, client_id, text in driver.calls:
        message = next(
            m for m in results if any(d["clientMessageId"] == client_id for d in m["deliveries"])
        )
        delivery = next(d for d in message["deliveries"] if d["clientMessageId"] == client_id)
        assert session_id == delivery["targetSessionId"]
        assert text == (
            f"roomId: agent-relay\n"
            f"messageId: {message['id']}\n"
            f"seq: {message['seq']}\n"
            f"createdAt: {message['createdAt']}\n"
            "sender: 你（user）\n\n仅验证投递"
        )


def test_human_message_to_the_only_topic_member_reaches_its_original_session(
    tmp_path: Path,
) -> None:
    store = create_room_store(tmp_path / "single.sqlite3")
    service = RoomService(store)
    room = service.create_room(CreateRoom(name="Single", project_path="D:/project"))
    topic = service.add_topic(room.id, CreateTopic(name="Work"))
    sessions = MemberSessions(
        store,
        FakeSessionDriver([SessionInfo("original", "D:/project", "probe", "Original", "idle")]),
    )
    member = sessions.add(
        room.id, CreateMember(session_id="original", name="Target", topic_ids=[topic.id])
    )

    class ConsumingDriver(FakeQueueDriver):
        def enqueue(self, thread_id: str, client_message_id: str, text: str) -> QueueReceipt:
            receipt = super().enqueue(thread_id, client_message_id, text)
            self.heads[thread_id] = QueueHead(receipt.id, client_message_id)
            return receipt

    driver = ConsumingDriver()
    submitter = DeliveryService(store, driver, logging.getLogger("tests.receive"))
    published = service.post_message(
        room.id,
        CreateMessage(
            publication_id=uuid4().hex,
            content="from me",
            topic_ids=[topic.id],
            mentioned_member_ids=[member.id],
        ),
    )
    assert published.sender_id == "user" and published.recipient_ids == [member.id]
    work = store.claim_delivery()
    assert work is not None
    submitter.submit(work)
    submitter.observe("original", {published.deliveries[0].client_message_id})
    saved = RoomService(open_room_store(store.path)).publication(
        room.id, published.publication_id or ""
    )
    assert len(saved.deliveries) == len(driver.calls) == len(driver.activations) == 1
    delivery = saved.deliveries[0]
    assert delivery.status == "received" and delivery.target_session_id == "original"
    assert delivery.queued_at and delivery.received_at and delivery.activation_attempted_at
    assert delivery.received_item_id == "item-" + delivery.client_message_id
    assert delivery.received_turn_id == "turn-" + delivery.client_message_id


def test_older_original_input_is_confirmed_across_history_pages(tmp_path: Path) -> None:
    store = create_room_store(tmp_path / "history.sqlite3")
    service = RoomService(store)
    room = service.create_room(CreateRoom(name="History", project_path="D:/history"))
    topic = service.add_topic(room.id, CreateTopic(name="Work"))
    member = MemberSessions(
        store,
        FakeSessionDriver([SessionInfo("original", "D:/history", "probe", "Original", "idle")]),
    ).add(room.id, CreateMember(session_id="original", name="Target", topic_ids=[topic.id]))
    message = service.post_message(
        room.id,
        CreateMessage(
            publication_id=uuid4().hex, content="earlier input", mentioned_member_ids=[member.id]
        ),
    )
    client_id = message.deliveries[0].client_message_id

    class HistoryDriver(FakeQueueDriver):
        def read_input_page(self, thread_id: str, cursor: str | None = None) -> InputPage:
            assert thread_id == "original"
            if cursor is None:
                return InputPage(
                    (ReceivedInput("recent-input", "recent-item", "recent-turn"),), "older"
                )
            assert cursor == "older"
            return InputPage((ReceivedInput(client_id, "original-item", "original-turn"),), None)

    driver = HistoryDriver()
    submitter = DeliveryService(store, driver, logging.getLogger("tests.history"))
    work = store.claim_delivery()
    assert work is not None
    submitter.submit(work)
    submitter.observe("original", {client_id})
    assert store.unconfirmed_inputs() == {"original": {client_id}}
    submitter.observe("original", {client_id})
    saved = (
        RoomService(open_room_store(store.path))
        .publication(room.id, message.publication_id or "")
        .deliveries[0]
    )
    assert saved.status == "received"
    assert (saved.received_item_id, saved.received_turn_id) == ("original-item", "original-turn")
    assert len(driver.calls) == 1
