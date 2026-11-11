import logging
from collections.abc import Iterator
from pathlib import Path
from time import monotonic, sleep

import pytest
from fastapi.testclient import TestClient
from support.databases import MemoryDatabases
from support.room_fixtures import DemoRoomService
from support.session_fixtures import FakeQueueDriver, FakeSessionDriver

from agent_relay.application.members.contracts import CreateMember
from agent_relay.application.members.service import MemberService
from agent_relay.application.members.sessions import SessionInfo
from agent_relay.application.rooms.contracts import CreateRoom
from agent_relay.application.rooms.service import RoomService
from agent_relay.bootstrap.http import create_app

ROOM = "/api/room/agent-relay"


@pytest.fixture
def driver() -> FakeSessionDriver:
    return FakeSessionDriver(
        [SessionInfo("candidate", "D:/SourceCodes/mywork/agent-relay", "codex", "Original", "idle")]
    )


@pytest.fixture
def client(
    tmp_path: Path, databases: MemoryDatabases, driver: FakeSessionDriver
) -> Iterator[TestClient]:
    service = DemoRoomService(databases.store(tmp_path / "http.sqlite3"))
    client = TestClient(
        create_app(
            logging.getLogger("tests.collaboration"),
            database=service.store.database,
            session_driver=driver,
            queue_driver=FakeQueueDriver(),
        )
    )
    yield client
    client.close()


def test_member_publication_binds_the_path_identity_and_supports_lookup(client: TestClient) -> None:
    route = f"{ROOM}/member/frontend-worker"
    request = {"publicationId": "member-http", "content": "Progress", "topicIds": ["frontend"]}
    response = client.post(f"{route}/message", json=request)
    assert response.status_code == 201
    message = response.json()
    assert message["senderId"] == "frontend-worker"
    assert message["recipientIds"] == ["coordinator", "test-worker"]
    assert client.get(f"{route}/publication/member-http").json() == message


def test_context_catalog_and_provision_use_the_path_member_and_update_positions(
    client: TestClient,
) -> None:
    route = f"{ROOM}/member/frontend-worker"
    catalog = client.get(f"{route}/catalog")
    assert catalog.status_code == 200 and catalog.json()["memberId"] == "frontend-worker"
    response = client.post(f"{route}/context", json={"messageId": "agent-relay-msg-0006"})
    assert response.status_code == 200
    assert response.json()["queryId"]
    assert [message["seq"] for message in response.json()["messages"]] == [6]
    positions = {
        position["topicId"]: position["seq"] for position in client.get(f"{route}/position").json()
    }
    assert positions == {"frontend": 6, "summary": 0}


def test_message_and_queue_routes_pass_filters_and_cursors_to_queries(client: TestClient) -> None:
    params: dict[str, str | int] = {
        "topic_id": "frontend",
        "member_id": "backend-worker",
        "keyword": "跨话题",
        "limit": 1,
    }
    first = client.get(f"{ROOM}/message", params=params).json()
    assert [message["seq"] for message in first["messages"]] == [5]
    older = client.get(
        f"{ROOM}/message", params={**params, "before_seq": first["nextBeforeSeq"]}
    ).json()
    assert [message["seq"] for message in older["messages"]] == [4]
    scope = {"topic_id": "frontend", "member_id": "backend-worker"}
    queued = client.get(f"{ROOM}/queue", params=scope).json()
    cleared = client.delete(f"{ROOM}/queue", params=scope)
    assert cleared.status_code == 200
    assert cleared.json()["removedMessages"] == queued["totalMessages"]
    assert client.get(f"{ROOM}/queue", params=scope).json()["messages"] == []
    assert len(client.get(ROOM).json()["messages"]) == 6


def test_websocket_catches_up_and_streams_subsequent_commits(client: TestClient) -> None:
    cursor = client.get(ROOM).json()["eventId"]
    first = client.post(f"{ROOM}/topic", json={"name": "First"}).json()
    with client.websocket_connect(f"{ROOM}/event/stream?after_event_id={cursor}") as stream:
        assert stream.receive_json()["events"][0]["entityId"] == first["id"]
        second = client.post(f"{ROOM}/topic", json={"name": "Second"}).json()
        stream.send_text("poll")
        assert stream.receive_json()["events"][0]["entityId"] == second["id"]


def test_session_discovery_join_and_upstream_error_mapping(
    client: TestClient, driver: FakeSessionDriver
) -> None:
    candidates = client.get(f"{ROOM}/session")
    assert candidates.status_code == 200 and candidates.json()[0]["id"] == "candidate"
    response = client.post(
        f"{ROOM}/member", json={"sessionId": "candidate", "name": "Worker", "topicIds": []}
    )
    assert response.status_code == 201 and response.json()["sessionId"] == "candidate"
    driver.error = OSError("private upstream detail")
    failed = client.get(f"{ROOM}/session")
    assert failed.status_code == 503 and failed.json()["code"] == "service_unavailable"
    assert "private upstream detail" not in failed.text


def test_http_publication_is_dispatched_to_the_original_session(
    tmp_path: Path, databases: MemoryDatabases
) -> None:
    store = databases.store(tmp_path / "dispatch.sqlite3")
    room = RoomService(store).create_room(CreateRoom(name="Project", project_path="D:/project"))
    driver = FakeSessionDriver([SessionInfo("original", "D:/project", "codex", "Original", "idle")])
    member = MemberService(store, driver).add(
        room.id, CreateMember(name="Worker", session_id="original", topic_ids=[])
    )
    queue = FakeQueueDriver()
    app = create_app(
        logging.getLogger("tests.dispatch"),
        database=store.database,
        session_driver=driver,
        queue_driver=queue,
    )
    with TestClient(app) as client:
        response = client.post(
            f"/api/room/{room.id}/message",
            json={
                "publicationId": "dispatch",
                "content": "Work",
                "mentionedMemberIds": [member.id],
            },
        )
        assert response.status_code == 201
        deadline = monotonic() + 3
        while True:
            saved = client.get(f"/api/room/{room.id}/publication/dispatch").json()
            if saved["deliveries"][0]["status"] == "queued":
                break
            assert monotonic() < deadline
            sleep(0.02)
        assert len(queue.calls) == 1 and queue.calls[0][0] == "original"
    assert not app.state.delivery_runner.thread.is_alive()
