import logging
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from room_fixtures import DemoRoomService, create_room_store
from session_fixtures import FakeQueueDriver, FakeSessionDriver

from agent_relay.application.delivery.service import DeliveryService
from agent_relay.application.members.sessions import SessionInfo
from agent_relay.bootstrap.http import create_app

pytestmark = pytest.mark.usefixtures("migrated_database")

ROOM_ROUTE = "/api/room/agent-relay"


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    service = DemoRoomService(create_room_store(tmp_path / "room.sqlite3"))
    queue = FakeQueueDriver()
    submitter = DeliveryService(service.store, queue, logging.getLogger("tests.queue.seed"))
    while work := service.store.claim_delivery():
        submitter.submit(work)
    # API contract checks read committed fixtures without racing the dispatcher.
    # Dispatcher lifecycle and queued results are exercised in test_delivery_service.
    test_client = TestClient(
        create_app(
            logging.getLogger("tests.agent_relay.room"),
            store=service.store,
            queue_driver=queue,
            session_driver=FakeSessionDriver(
                [
                    SessionInfo("acme-1", "D:/work/acme", "codex", "Acme", "idle"),
                    SessionInfo(
                        "agent-relay-frontend",
                        "D:/SourceCodes/mywork/agent-relay",
                        "codex",
                        "Frontend",
                        "active",
                    ),
                    SessionInfo(
                        "candidate",
                        "D:/SourceCodes/mywork/agent-relay",
                        "codex",
                        "Candidate",
                        "unavailable",
                    ),
                ]
            ),
        )
    )
    yield test_client
    test_client.close()


def test_room_returns_topics_members_messages_and_delivery_summary(client: TestClient) -> None:
    rooms_response = client.get("/api/room")
    response = client.get(ROOM_ROUTE)

    assert response.status_code == 200
    assert rooms_response.status_code == 200
    assert {room["id"] for room in rooms_response.json()} == {"agent-relay", "housekeeper"}
    room = response.json()
    assert room["room"]["name"] == "Agent Relay 开发室"
    assert room["room"]["projectPath"] == "d:/sourcecodes/mywork/agent-relay"
    tester = next(member for member in room["members"] if member["id"] == "test-worker")
    assert {"frontend", "backend"} <= set(tester["topicIds"])
    assert room["summary"]["totalMessages"] == len(room["messages"])
    assert (
        sum(room["summary"][key] for key in ("pendingCount", "submittingCount", "queuedCount")) > 0
    )
    assert all(message["senderId"] not in message["recipientIds"] for message in room["messages"])
    assert response.headers["X-Request-Id"]


def test_topic_filter_keeps_cross_topic_message_once_and_global_counts(client: TestClient) -> None:
    full_room = client.get(ROOM_ROUTE).json()
    response = client.get(ROOM_ROUTE, params={"topic_id": "frontend"})

    assert response.status_code == 200
    room = response.json()
    assert room["messages"]
    assert all("frontend" in message["topicIds"] for message in room["messages"])
    assert len({message["id"] for message in room["messages"]}) == len(room["messages"])
    assert any("backend" in message["topicIds"] for message in room["messages"])
    assert room["topics"] == full_room["topics"]
    assert room["summary"] == full_room["summary"]


def test_post_message_deduplicates_topics_recipients_and_deliveries(client: TestClient) -> None:
    response = client.post(
        f"{ROOM_ROUTE}/message",
        json={
            "publicationId": str(uuid4()),
            "content": "  请核对跨话题消息契约  ",
            "topicIds": ["frontend", "backend", "frontend"],
            "mentionedMemberIds": ["test-worker", "frontend-worker", "test-worker"],
            "replyToMessageId": "agent-relay-msg-0004",
        },
    )

    assert response.status_code == 201
    message = response.json()
    assert message["senderId"] == "user"
    assert message["senderName"] == "你"
    assert message["content"] == "请核对跨话题消息契约"
    assert message["topicIds"] == ["frontend", "backend"]
    assert message["mentionedMemberIds"] == ["test-worker", "frontend-worker"]
    assert message["recipientIds"] == [
        "coordinator",
        "frontend-worker",
        "backend-worker",
        "test-worker",
    ]
    assert message["replyToMessageId"] == "agent-relay-msg-0004"
    assert {
        delivery["targetMemberId"]: delivery["status"] for delivery in message["deliveries"]
    } == {
        "coordinator": "pending",
        "test-worker": "pending",
        "frontend-worker": "pending",
        "backend-worker": "pending",
    }
    snapshot = client.get(ROOM_ROUTE).json()
    assert snapshot["messages"][-1] == message
    assert message["seq"] == snapshot["messages"][-2]["seq"] + 1


def test_topic_message_routes_to_subscribers_without_parsing_body_mentions(
    client: TestClient,
) -> None:
    response = client.post(
        f"{ROOM_ROUTE}/message",
        json={
            "publicationId": str(uuid4()),
            "content": "同步前端进展 @后端 Worker #后端",
            "topicIds": ["frontend"],
        },
    )

    assert response.status_code == 201
    assert response.json()["mentionedMemberIds"] == []
    assert response.json()["recipientIds"] == ["coordinator", "frontend-worker", "test-worker"]
    assert {delivery["targetMemberId"] for delivery in response.json()["deliveries"]} == {
        "coordinator",
        "frontend-worker",
        "test-worker",
    }
    assert client.get(ROOM_ROUTE, params={"topic_id": "frontend"}).json()["messages"][-1] == (
        response.json()
    )


@pytest.mark.parametrize("topic_payload", [{}, {"topicIds": []}])
def test_direct_mention_does_not_require_a_topic(
    client: TestClient, topic_payload: dict[str, object]
) -> None:
    response = client.post(
        f"{ROOM_ROUTE}/message",
        json={
            "publicationId": str(uuid4()),
            "content": "请核对界面",
            "mentionedMemberIds": ["frontend-worker"],
            **topic_payload,
        },
    )

    assert response.status_code == 201
    message = response.json()
    assert message["topicIds"] == []
    assert message["mentionedMemberIds"] == ["frontend-worker"]
    assert message["recipientIds"] == ["frontend-worker"]
    assert len(message["deliveries"]) == 1
    assert message["deliveries"][0]["status"] == "pending"
    assert client.get(ROOM_ROUTE).json()["messages"][-1] == message
    assert message["id"] not in {
        item["id"]
        for item in client.get(ROOM_ROUTE, params={"topic_id": "frontend"}).json()["messages"]
    }


def test_mentions_combine_with_topic_subscribers_without_subscription_restrictions(
    client: TestClient,
) -> None:
    response = client.post(
        f"{ROOM_ROUTE}/message",
        json={
            "publicationId": str(uuid4()),
            "content": "请前后端一起核对",
            "topicIds": ["backend"],
            "mentionedMemberIds": ["frontend-worker"],
        },
    )

    assert response.status_code == 201
    assert response.json()["mentionedMemberIds"] == ["frontend-worker"]
    assert set(response.json()["recipientIds"]) == {
        "coordinator",
        "frontend-worker",
        "backend-worker",
        "test-worker",
    }
    assert len(response.json()["deliveries"]) == 4


@pytest.mark.parametrize(
    "targets",
    [
        {"topicIds": ["backend"], "mentionedMemberIds": ["test-worker", "missing"]},
        {"topicIds": ["backend", "missing"], "mentionedMemberIds": ["test-worker"]},
    ],
)
def test_invalid_target_rejects_entire_message_without_partial_write(
    client: TestClient,
    targets: dict[str, object],
) -> None:
    before = client.get(ROOM_ROUTE).json()
    response = client.post(
        f"{ROOM_ROUTE}/message",
        headers={"X-Request-Id": "req_routing"},
        json={
            "publicationId": str(uuid4()),
            "content": "检查后端接口",
            **targets,
        },
    )

    assert response.status_code == 422
    assert "不存在" in response.json()["error"]
    assert response.json()["requestId"] == "req_routing"
    assert client.get(ROOM_ROUTE).json() == before


@pytest.mark.parametrize(
    "payload",
    [
        {"publicationId": str(uuid4()), "content": "   ", "topicIds": ["frontend"]},
        {
            "publicationId": str(uuid4()),
            "content": "必须选择投递目标",
            "topicIds": [],
            "mentionedMemberIds": [],
        },
    ],
)
def test_message_requires_content_and_targets(
    client: TestClient, payload: dict[str, object]
) -> None:
    response = client.post(f"{ROOM_ROUTE}/message", json=payload)

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_empty_topic_requires_an_additional_member_and_does_not_save_an_unroutable_message(
    client: TestClient,
) -> None:
    topic = client.post(f"{ROOM_ROUTE}/topic", json={"name": "新话题"}).json()
    before = client.get(ROOM_ROUTE).json()
    response = client.post(
        f"{ROOM_ROUTE}/message",
        json={
            "publicationId": str(uuid4()),
            "content": "同步进展",
            "topicIds": [topic["id"]],
        },
    )

    assert response.status_code == 422
    assert "所选话题暂无成员" in response.json()["error"]
    assert client.get(ROOM_ROUTE).json() == before

    routed = client.post(
        f"{ROOM_ROUTE}/message",
        json={
            "publicationId": str(uuid4()),
            "content": "同步进展",
            "topicIds": [topic["id"]],
            "mentionedMemberIds": ["backend-worker"],
        },
    )
    assert routed.status_code == 201
    assert routed.json()["recipientIds"] == ["backend-worker"]


def test_unknown_topic_returns_standard_not_found(client: TestClient) -> None:
    response = client.get(ROOM_ROUTE, params={"topic_id": "missing"})

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
    assert response.json()["error"] == "话题不存在"


def test_different_database_paths_isolate_room_state(client: TestClient) -> None:
    client.post(
        f"{ROOM_ROUTE}/message",
        json={"publicationId": str(uuid4()), "content": "本库消息", "topicIds": ["summary"]},
    )
    with TestClient(create_app(logging.getLogger("tests.agent_relay.other_room"))) as other_client:
        assert other_client.get("/api/room").json() == []
        assert other_client.get(ROOM_ROUTE).status_code == 404


def test_create_room_add_topic_and_invite_member(client: TestClient) -> None:
    created = client.post("/api/room", json={"name": "Acme", "projectPath": "D:/work/acme"})

    assert created.status_code == 201
    room = created.json()
    room_route = f"/api/room/{room['id']}"
    assert room["name"] == "Acme"
    assert room["projectPath"] == "d:/work/acme"
    assert client.get(room_route).json()["messages"] == []
    assert client.get(room_route).json()["topics"] == []
    assert [s["id"] for s in client.get(f"{room_route}/session").json()] == ["acme-1"]

    topic_response = client.post(
        f"{room_route}/topic", json={"name": "集成", "description": "端到端联调"}
    )
    assert topic_response.status_code == 201
    member_response = client.post(
        f"{room_route}/member",
        json={
            "sessionId": "acme-1",
            "name": "集成 Worker",
            "topicIds": [topic_response.json()["id"]],
        },
    )
    assert member_response.status_code == 201
    member = member_response.json()
    assert member["sessionId"] == "acme-1"
    message_response = client.post(
        f"{room_route}/message",
        json={
            "publicationId": str(uuid4()),
            "content": "开始联调",
            "topicIds": [topic_response.json()["id"]],
            "mentionedMemberIds": [member["id"]],
        },
    )
    assert message_response.status_code == 201
    assert len(message_response.json()["deliveries"]) == 1
    assert message_response.json()["deliveries"][0]["targetMemberId"] == member["id"]
    assert len(client.get(ROOM_ROUTE).json()["messages"]) == 6


def test_topic_creation_time_is_preserved_in_metadata_updates_and_deletion(
    client: TestClient,
) -> None:
    started_at = datetime.now(UTC)
    response = client.post(f"{ROOM_ROUTE}/topic", json={"name": "有创建时间的话题"})
    assert response.status_code == 201
    topic = response.json()
    created_at = topic["createdAt"]
    assert started_at <= datetime.fromisoformat(created_at) <= datetime.now(UTC)

    for route in (ROOM_ROUTE, f"{ROOM_ROUTE}/metadata"):
        saved = next(
            item for item in client.get(route).json()["topics"] if item["id"] == topic["id"]
        )
        assert saved["createdAt"] == created_at

    updated = client.patch(f"{ROOM_ROUTE}/topic/{topic['id']}", json={"name": "已改名的话题"})
    assert updated.status_code == 200
    assert updated.json()["createdAt"] == created_at
    deleted = client.delete(f"{ROOM_ROUTE}/topic/{topic['id']}")
    assert deleted.status_code == 200
    assert deleted.json()["createdAt"] == created_at
    assert deleted.json()["deletedAt"]
    saved = next(
        item
        for item in client.get(f"{ROOM_ROUTE}/metadata").json()["topics"]
        if item["id"] == topic["id"]
    )
    assert saved["createdAt"] == created_at


def test_member_edit_updates_subscriptions_used_by_message_routing(client: TestClient) -> None:
    previous = client.post(
        f"{ROOM_ROUTE}/message",
        json={
            "publicationId": str(uuid4()),
            "content": "此前的后端约定",
            "topicIds": ["backend"],
        },
    ).json()
    assert "frontend-worker" not in previous["recipientIds"]
    updated = client.patch(
        f"{ROOM_ROUTE}/member/frontend-worker",
        json={"name": "联调 Worker", "topicIds": ["frontend", "backend"]},
    )

    assert updated.status_code == 200
    assert updated.json()["sessionId"] == "agent-relay-frontend"
    assert updated.json()["name"] == "联调 Worker"
    assert updated.json()["topicIds"] == ["frontend", "backend"]
    sent = client.post(
        f"{ROOM_ROUTE}/message",
        json={
            "publicationId": str(uuid4()),
            "content": "请检查后端契约",
            "topicIds": ["backend"],
        },
    )
    assert sent.status_code == 201
    assert "frontend-worker" in sent.json()["recipientIds"]
    stored_previous = next(
        message
        for message in client.get(ROOM_ROUTE).json()["messages"]
        if message["id"] == previous["id"]
    )
    assert stored_previous == previous
    assert [member["id"] for member in client.get("/api/room/housekeeper").json()["members"]] == [
        "user"
    ]


def test_zero_and_multiple_subscriptions_keep_direct_mentions_and_saved_metadata(
    client: TestClient,
) -> None:
    room = client.post("/api/room", json={"name": "Acme", "projectPath": "D:/work/acme"}).json()
    route = f"/api/room/{room['id']}"
    joined = client.post(
        f"{route}/member",
        json={"sessionId": "acme-1", "name": "协作成员", "topicIds": []},
    )
    assert joined.status_code == 201
    member = joined.json()
    member_id = member["id"]
    assert member["topicIds"] == []
    assert member["metadata"] == client.get(f"{route}/metadata").json()
    assert member["metadata"]["topics"] == member["metadata"]["positions"] == []
    assert member["metadata"]["sessions"] == [member["session"]]
    message = client.post(
        f"{route}/message",
        json={
            "publicationId": str(uuid4()),
            "content": "直接协作",
            "mentionedMemberIds": [member_id],
        },
    )
    assert message.status_code == 201
    assert message.json()["recipientIds"] == [member_id]

    topics = [
        client.post(f"{route}/topic", json={"name": name}).json() for name in ["实现", "联调"]
    ]
    subscribed = client.patch(
        f"{route}/member/{member_id}",
        json={"name": "协作成员", "topicIds": [topic["id"] for topic in topics]},
    )
    assert subscribed.status_code == 200
    assert subscribed.json()["metadata"] == client.get(f"{route}/metadata").json()
    assert [position["topicId"] for position in subscribed.json()["metadata"]["positions"]] == [
        topic["id"] for topic in topics
    ]
    for topic in topics:
        removed = client.delete(f"{route}/topic/{topic['id']}")
        assert removed.status_code == 200
        assert removed.json()["metadata"] == client.get(f"{route}/metadata").json()
    metadata = removed.json()["metadata"]
    assert metadata["members"][0]["topicIds"] == metadata["positions"] == []
    assert metadata["summary"]["totalMessages"] == 1
    assert metadata["summary"]["pendingCount"] == 1
    assert client.get(f"{route}/message/{message.json()['id']}").json() == message.json()

    renamed = client.patch(
        f"{route}/member/{member_id}", json={"name": "直接协作成员", "topicIds": []}
    )
    assert renamed.status_code == 200
    assert renamed.json()["metadata"]["members"][0]["name"] == "直接协作成员"
    assert renamed.json()["metadata"] == client.get(f"{route}/metadata").json()
    mentioned = client.post(
        f"{route}/message",
        json={
            "publicationId": str(uuid4()),
            "content": "继续直接协作",
            "mentionedMemberIds": [member_id],
        },
    )
    assert mentioned.status_code == 201
    assert mentioned.json()["recipientIds"] == [member_id]
    assert mentioned.json()["deliveries"][0]["targetSessionId"] == "acme-1"


def test_member_creation_rejects_foreign_topic_and_duplicate_name(client: TestClient) -> None:
    topic = client.post("/api/room/housekeeper/topic", json={"name": "foreign"}).json()
    invalid = client.post(
        f"{ROOM_ROUTE}/member",
        json={
            "sessionId": "candidate",
            "name": "Other",
            "topicIds": [topic["id"]],
        },
    )
    duplicate = client.post(
        f"{ROOM_ROUTE}/member",
        json={
            "sessionId": "candidate",
            "name": "前端 Worker",
            "topicIds": ["frontend"],
        },
    )
    old_request = client.post(
        f"{ROOM_ROUTE}/member",
        json={
            "operationId": "old-create",
            "name": "Old",
            "topicIds": ["frontend"],
        },
    )
    assert invalid.status_code == old_request.status_code == 422
    assert duplicate.status_code == 409
    assert len(client.get(ROOM_ROUTE).json()["members"]) == 5


def test_project_path_is_unique_across_slashes_and_case(client: TestClient) -> None:
    response = client.post(
        "/api/room",
        json={"name": "Duplicate", "projectPath": "D:\\SOURCECODES\\MYWORK\\AGENT-RELAY\\"},
    )

    assert response.status_code == 409
    assert response.json()["code"] == "conflict"
    assert len(client.get("/api/room").json()) == 2


def test_session_discovery_is_scoped_and_marks_joined_sessions(client: TestClient) -> None:
    candidates = client.get(f"{ROOM_ROUTE}/session")
    assert candidates.status_code == 200
    assert [s["id"] for s in candidates.json()] == ["agent-relay-frontend", "candidate"]
    assert candidates.json()[0]["memberId"] == "frontend-worker"
    assert candidates.json()[1]["memberId"] is None
    duplicate = client.post(
        f"{ROOM_ROUTE}/member",
        json={
            "sessionId": "agent-relay-frontend",
            "name": "Other",
            "topicIds": ["frontend"],
        },
    )
    assert duplicate.status_code == 409
    assert client.get("/api/room/missing/session").status_code == 404


def test_edit_and_delete_nodes_preserve_history_and_release_names_and_bindings(
    client: TestClient,
) -> None:
    original = client.get(ROOM_ROUTE).json()
    assert all(topic["createdAt"] is None for topic in original["topics"])
    edited = client.patch(
        f"{ROOM_ROUTE}/topic/frontend", json={"name": "界面", "description": "界面交互讨论"}
    )
    assert edited.status_code == 200
    assert edited.json()["name"] == "界面"
    assert edited.json()["description"] == "界面交互讨论"
    assert edited.json()["createdAt"] is None
    assert edited.json()["metadata"] == client.get(f"{ROOM_ROUTE}/metadata").json()

    deleted_topic = client.delete(f"{ROOM_ROUTE}/topic/frontend")
    deleted_member = client.delete(f"{ROOM_ROUTE}/member/frontend-worker")
    assert deleted_topic.status_code == deleted_member.status_code == 200
    assert deleted_topic.json()["deletedAt"]
    assert deleted_topic.json()["createdAt"] is None
    assert deleted_member.json()["deletedAt"]
    assert deleted_member.json()["metadata"] == client.get(f"{ROOM_ROUTE}/metadata").json()
    snapshot = client.get(ROOM_ROUTE).json()
    assert snapshot["messages"] == original["messages"]
    assert all("frontend" not in member["topicIds"] for member in snapshot["members"])

    topic = client.post(f"{ROOM_ROUTE}/topic", json={"name": "界面", "description": "新话题"})
    assert topic.status_code == 201
    joined = client.post(
        f"{ROOM_ROUTE}/member",
        json={
            "sessionId": "agent-relay-frontend",
            "name": "前端 Worker",
            "topicIds": [topic.json()["id"]],
        },
    )
    assert joined.status_code == 201
    published = client.post(
        f"{ROOM_ROUTE}/message",
        json={
            "publicationId": str(uuid4()),
            "content": "新的界面讨论",
            "topicIds": [topic.json()["id"]],
        },
    )
    assert published.status_code == 201
    assert published.json()["recipientIds"] == [joined.json()["id"]]
    assert client.get(ROOM_ROUTE).json()["messages"][-1] == published.json()
