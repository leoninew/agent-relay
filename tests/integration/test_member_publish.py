import logging
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from time import monotonic, sleep
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from room_fixtures import DemoRoomService, create_room_store, open_room_store
from session_fixtures import FakeQueueDriver, FakeSessionDriver

from agent_relay.application.delivery.service import DeliveryService
from agent_relay.application.rooms.contracts import UpdateMember
from agent_relay.application.rooms.service import RoomService
from agent_relay.bootstrap.http import create_app


@dataclass
class MemberEnvironment:
    client: TestClient
    service: DemoRoomService
    driver: FakeQueueDriver
    member_urls: dict[str, str]


@pytest.fixture
def members(tmp_path: Path) -> Iterator[MemberEnvironment]:
    service = DemoRoomService(create_room_store(tmp_path / "room.sqlite3"))
    driver = FakeQueueDriver()
    logger = logging.getLogger("tests.member_publish")
    submitter = DeliveryService(service.store, driver, logger)
    while work := service.store.claim_delivery():
        submitter.submit(work)
    member_urls = {
        member.id: f"/api/room/agent-relay/member/{member.id}"
        for member in service.snapshot("agent-relay").members
    }
    with TestClient(
        create_app(
            logger,
            database=service.store.database,
            queue_driver=driver,
            session_driver=FakeSessionDriver(),
        )
    ) as client:
        yield MemberEnvironment(client, service, driver, member_urls)


@pytest.mark.parametrize(
    ("topics", "mentions", "recipients"),
    [
        (["frontend"], [], ["coordinator", "test-worker"]),
        ([], ["frontend-worker", "backend-worker"], ["backend-worker"]),
        (
            ["backend"],
            ["frontend-worker", "backend-worker"],
            ["coordinator", "backend-worker", "test-worker"],
        ),
    ],
)
def test_member_publication_uses_path_member_and_routes_explicit_targets(
    members: MemberEnvironment, topics: list[str], mentions: list[str], recipients: list[str]
) -> None:
    request = {
        "publicationId": str(uuid4()),
        "content": "成员明确发布的协作消息",
        "topicIds": topics,
        "mentionedMemberIds": mentions,
        "replyToMessageId": "agent-relay-msg-0004",
    }
    response = members.client.post(
        f"{members.member_urls['frontend-worker']}/message", json=request
    )

    assert response.status_code == 201
    message = response.json()
    assert (message["senderId"], message["senderName"]) == ("frontend-worker", "前端 Worker")
    assert message["recipientIds"] == recipients
    assert message["replyToMessageId"] == "agent-relay-msg-0004"
    assert [delivery["targetMemberId"] for delivery in message["deliveries"]] == recipients
    snapshot = members.client.get("/api/room/agent-relay").json()
    assert snapshot["messages"][-1]["id"] == message["id"]
    assert snapshot["messages"][-1]["senderId"] == "frontend-worker"


def test_publication_keys_and_lookup_are_scoped_to_each_publisher(
    members: MemberEnvironment,
) -> None:
    request = {
        "publicationId": str(uuid4()),
        "content": "相同编号在不同发布者之间独立",
        "mentionedMemberIds": ["test-worker"],
    }
    message_ids = set()
    for member_id in ("frontend-worker", "backend-worker"):
        member_url = members.member_urls[member_id]
        created = members.client.post(f"{member_url}/message", json=request)
        assert created.status_code == 201
        message = created.json()
        message_ids.add(message["id"])
        replay = members.client.post(f"{member_url}/message", json=request)
        lookup = members.client.get(f"{member_url}/publication/{request['publicationId']}")
        assert replay.json()["id"] == lookup.json()["id"] == message["id"]
        assert lookup.json()["senderId"] == member_id
    console = members.client.post("/api/room/agent-relay/message", json=request)
    assert console.status_code == 201
    message_ids.add(console.json()["id"])
    assert len(message_ids) == 3


def test_member_publication_replay_preserves_original_targets_and_resolves_current_sender_name(
    members: MemberEnvironment,
) -> None:
    request = {
        "publicationId": str(uuid4()),
        "content": "保存本次成员发布事实",
        "topicIds": ["frontend"],
    }
    member_url = members.member_urls["frontend-worker"]
    response = members.client.post(f"{member_url}/message", json=request)
    assert response.status_code == 201
    message = response.json()
    members.service.update_member(
        "agent-relay", "frontend-worker", UpdateMember(name="前端成员", topic_ids=["backend"])
    )
    members.service.delete_member("agent-relay", "test-worker")

    replay = members.client.post(f"{member_url}/message", json=request)

    assert replay.status_code == 201
    assert replay.json()["id"] == message["id"]
    assert replay.json()["senderName"] == "前端成员"
    assert replay.json()["recipientIds"] == ["coordinator", "test-worker"]


def test_member_publish_queue_receipts_and_member_identity_survive_restart(
    members: MemberEnvironment,
) -> None:
    member_url = members.member_urls["frontend-worker"]
    publication_id = str(uuid4())
    request = {
        "publicationId": publication_id,
        "content": "成员消息投递到原会话",
        "mentionedMemberIds": ["backend-worker"],
    }
    response = members.client.post(f"{member_url}/message", json=request)
    assert response.status_code == 201
    deadline = monotonic() + 5
    while monotonic() < deadline:
        result = members.client.get(f"{member_url}/publication/{request['publicationId']}").json()
        if result["deliveries"][0]["status"] == "queued":
            break
        sleep(0.02)
    delivery = result["deliveries"][0]
    assert delivery["status"] == "queued"
    assert delivery["targetSessionId"] == "agent-relay-backend"
    assert delivery["receipt"] == {
        "id": delivery["queuedSubmissionId"],
        "clientUserMessageId": delivery["clientMessageId"],
    }
    delivered = next(
        text
        for _, client_id, text in members.driver.calls
        if client_id == delivery["clientMessageId"]
    )
    assert delivered == (
        f"roomId: agent-relay\n"
        f"messageId: {result['id']}\n"
        f"seq: {result['seq']}\n"
        f"createdAt: {result['createdAt']}\n"
        "sender: 前端 Worker（frontend-worker）\n\n成员消息投递到原会话"
    )
    store = open_room_store(members.service.store.path)
    restored = RoomService(store).publication(
        "agent-relay", publication_id, member_id="frontend-worker"
    )
    assert restored.model_dump(mode="json", by_alias=True) == result
