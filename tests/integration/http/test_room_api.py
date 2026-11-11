import logging
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from support.databases import MemoryDatabases
from support.room_fixtures import DemoRoomService
from support.session_fixtures import FakeQueueDriver, FakeSessionDriver

from agent_relay.application.delivery.service import DeliveryService
from agent_relay.application.members.sessions import SessionInfo
from agent_relay.bootstrap.http import create_app

ROOM_ROUTE = "/api/room/agent-relay"


@pytest.fixture
def client(tmp_path: Path, databases: MemoryDatabases) -> Iterator[TestClient]:
    service = DemoRoomService(databases.store(tmp_path / "room.sqlite3"))
    queue = FakeQueueDriver()
    submitter = DeliveryService(service.store, queue, logging.getLogger("tests.queue.seed"))
    while work := service.store.claim_delivery():
        submitter.submit(work)
    test_client = TestClient(
        create_app(
            logging.getLogger("tests.agent_relay.room"),
            database=service.store.database,
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
    assert response.headers["X-Request-Id"]


def test_room_deletion_removes_history_and_allows_recreating_the_project(
    client: TestClient,
) -> None:
    original = client.get(ROOM_ROUTE).json()
    other_room = client.get("/api/room/housekeeper").json()
    context = client.post(
        f"{ROOM_ROUTE}/member/frontend-worker/context", json={"topicId": "frontend", "limit": 1}
    )
    assert context.status_code == 200
    assert context.json()["messages"]

    response = client.delete(ROOM_ROUTE)

    assert response.status_code == 204
    assert response.content == b""
    assert client.get(ROOM_ROUTE).status_code == 404
    assert [room["id"] for room in client.get("/api/room").json()] == ["housekeeper"]
    assert client.get("/api/room/housekeeper").json() == other_room
    recreated = client.post(
        "/api/room",
        json={"name": "重新创建", "projectPath": original["room"]["projectPath"]},
    )
    assert recreated.status_code == 201
    snapshot = client.get(f"/api/room/{recreated.json()['id']}").json()
    assert snapshot["messages"] == []
    assert [member["id"] for member in snapshot["members"]] == ["user"]


def test_deleting_an_absent_room_uses_the_standard_error_contract(client: TestClient) -> None:
    response = client.delete("/api/room/missing", headers={"X-Request-Id": "delete-room-request"})

    assert response.status_code == 404
    assert response.json() == {
        "code": "not_found",
        "error": "聊天室不存在",
        "requestId": "delete-room-request",
    }
    assert response.headers["X-Request-Id"] == "delete-room-request"


def test_room_rename_keeps_project_path_and_rejects_other_fields(client: TestClient) -> None:
    original = client.get(ROOM_ROUTE).json()["room"]

    response = client.patch(ROOM_ROUTE, json={"name": "  Renamed Room  "})

    assert response.status_code == 200
    renamed = response.json()
    assert renamed["name"] == "Renamed Room"
    assert renamed["projectPath"] == original["projectPath"]
    assert client.get(ROOM_ROUTE).json()["room"]["name"] == "Renamed Room"
    assert (
        client.post(
            "/api/room",
            json={"name": "Duplicate", "projectPath": original["projectPath"]},
        ).status_code
        == 409
    )
    assert client.patch(ROOM_ROUTE, json={"name": "   "}).status_code == 422
    assert (
        client.patch(
            ROOM_ROUTE,
            json={"name": "Renamed Room", "projectPath": "D:/elsewhere"},
        ).status_code
        == 422
    )


def test_message_validation_uses_the_standard_http_error(client: TestClient) -> None:
    response = client.post(
        f"{ROOM_ROUTE}/message",
        json={"publicationId": "invalid", "content": "   ", "topicIds": ["frontend"]},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_unknown_topic_returns_standard_not_found(client: TestClient) -> None:
    response = client.get(ROOM_ROUTE, params={"topic_id": "missing"})

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
    assert response.json()["error"] == "话题不存在"


def test_create_room_add_topic_and_invite_member(client: TestClient) -> None:
    created = client.post("/api/room", json={"name": "Acme", "projectPath": "D:/work/acme"})

    assert created.status_code == 201
    room = created.json()
    room_route = f"/api/room/{room['id']}"
    assert room["name"] == "Acme"
    assert room["projectPath"] == "d:/work/acme"
    snapshot = client.get(room_route).json()
    assert snapshot["messages"] == []
    topics = snapshot["topics"]
    assert [topic["name"] for topic in topics] == ["产品", "架构", "开发", "测试"]
    assert len({topic["id"] for topic in topics}) == 4
    assert all(topic["createdAt"] and "messageCount" not in topic for topic in topics)
    assert [session["id"] for session in client.get(f"{room_route}/session").json()] == ["acme-1"]

    member_response = client.post(
        f"{room_route}/member",
        json={"sessionId": "acme-1", "name": "集成 Worker", "topicIds": [topics[2]["id"]]},
    )
    assert member_response.status_code == 201
    member = member_response.json()
    assert member["sessionId"] == "acme-1"
    assert member["topicIds"] == [topics[2]["id"]]
    topic_response = client.post(
        f"{room_route}/topic", json={"name": "集成", "description": "端到端联调"}
    )
    assert topic_response.status_code == 201
    assert topic_response.json()["metadata"] == client.get(f"{room_route}/metadata").json()
    message_response = client.post(
        f"{room_route}/message",
        json={"publicationId": str(uuid4()), "content": "开始联调", "topicIds": [topics[2]["id"]]},
    )
    assert message_response.status_code == 201
    assert len(message_response.json()["deliveries"]) == 1
    assert message_response.json()["deliveries"][0]["targetMemberId"] == member["id"]
    assert len(client.get(ROOM_ROUTE).json()["messages"]) == 6


def test_edit_and_delete_nodes_preserve_history_and_release_names_and_bindings(
    client: TestClient,
) -> None:
    original = client.get(ROOM_ROUTE).json()
    edited = client.patch(
        f"{ROOM_ROUTE}/topic/frontend", json={"name": "界面", "description": "界面交互讨论"}
    )
    assert edited.status_code == 200
    assert edited.json()["name"] == "界面"
    assert edited.json()["description"] == "界面交互讨论"
    assert edited.json()["metadata"] == client.get(f"{ROOM_ROUTE}/metadata").json()

    deleted_topic = client.delete(f"{ROOM_ROUTE}/topic/frontend")
    deleted_member = client.delete(f"{ROOM_ROUTE}/member/frontend-worker")
    assert deleted_topic.status_code == deleted_member.status_code == 200
    assert deleted_topic.json()["deletedAt"]
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
