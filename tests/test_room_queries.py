import logging
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from room_fixtures import DemoRoomService, create_room_store
from session_fixtures import FakeQueueDriver, FakeSessionDriver

from agent_relay.api import create_app
from agent_relay.delivery_service import DeliveryService
from agent_relay.drivers.codex import SessionInfo
from agent_relay.room_models import RoomEvent
from agent_relay.room_queries import RoomQueries
from agent_relay.room_service import RoomService
from agent_relay.room_store import SQLiteRoomStore

ROOM = "/api/room/agent-relay"


@pytest.fixture
def service(tmp_path: Path) -> DemoRoomService:
    return DemoRoomService(create_room_store(tmp_path / "rooms.sqlite3"))


@pytest.fixture
def client(service: DemoRoomService) -> Iterator[TestClient]:
    # The query tests do not start the background dispatcher; submissions are explicit.
    client = TestClient(
        create_app(
            logging.getLogger("tests.room.queries"),
            room_service=service,
            session_driver=FakeSessionDriver(
                [
                    SessionInfo(
                        "candidate",
                        service.snapshot("agent-relay").room.project_path,
                        "codex",
                        "Candidate",
                        "idle",
                    )
                ]
            ),
            queue_driver=FakeQueueDriver(),
        )
    )
    yield client
    client.close()


def seed_history(service: DemoRoomService) -> None:
    with service.store.write() as connection:
        state = RoomQueries(service.store).resources_in(connection, "agent-relay")
        for seq in range(7, 126):
            sender = "backend-worker" if seq % 2 else "frontend-worker"
            topics = (
                ["frontend", "backend"]
                if seq % 3 == 0
                else ["frontend"]
                if seq % 3 == 1
                else ["backend"]
            )
            message = service._build_message(
                state,
                seq=seq,
                content=f"历史消息 {seq}",
                topic_ids=topics,
                mentioned_member_ids=[],
                sender_id=sender,
                sender_name=sender,
                created_at=datetime.now(UTC),
            )
            service.store.insert_message(connection, state.room.id, message)


def test_keyset_history_keeps_three_pages_stable_during_new_publication(
    service: DemoRoomService,
    client: TestClient,
) -> None:
    seed_history(service)
    latest = client.get(ROOM).json()
    assert [message["seq"] for message in latest["messages"]] == list(range(76, 126))
    assert latest["hasMore"] and not latest["hasNewer"]
    assert latest["summary"]["totalMessages"] == 125

    posted = client.post(
        f"{ROOM}/message",
        json={
            "publicationId": str(uuid4()),
            "content": "分页期间的新消息",
            "topicIds": ["summary"],
        },
    )
    assert posted.status_code == 201
    previous = client.get(f"{ROOM}/message", params={"before_seq": latest["nextBeforeSeq"]}).json()
    earliest = client.get(
        f"{ROOM}/message", params={"before_seq": previous["nextBeforeSeq"]}
    ).json()
    assert previous["hasMore"] and previous["hasNewer"]
    assert not earliest["hasMore"] and earliest["nextBeforeSeq"] is None
    assert [
        message["seq"] for page in [earliest, previous, latest] for message in page["messages"]
    ] == list(range(1, 126))
    assert client.get(ROOM).json()["messages"][-1]["id"] == posted.json()["id"]
    assert client.get(f"{ROOM}/metadata").json()["summary"]["totalMessages"] == 126


def test_topic_and_sender_filter_before_pagination_keep_whole_room_statistics(
    service: DemoRoomService,
    client: TestClient,
) -> None:
    seed_history(service)
    full = client.get(f"{ROOM}/metadata").json()
    params: dict[str, str | int] = {
        "topic_id": "frontend",
        "member_id": "frontend-worker",
        "limit": 9,
    }
    filtered = client.get(ROOM, params=params).json()
    assert filtered["summary"] == full["summary"]
    assert filtered["topics"] == full["topics"]
    pages = [filtered]
    while pages[-1]["hasMore"]:
        params["before_seq"] = pages[-1]["nextBeforeSeq"]
        pages.append(client.get(f"{ROOM}/message", params=params).json())
    messages = [message for page in reversed(pages) for message in page["messages"]]
    assert len(pages) > 2
    assert [message["seq"] for message in messages] == [
        seq for seq in range(7, 126) if seq % 2 == 0 and seq % 3 != 2
    ]
    assert all(
        message["senderId"] == "frontend-worker" and "frontend" in message["topicIds"]
        for message in messages
    )
    assert client.get(f"{ROOM}/metadata").json() == full


def test_exact_reference_loads_a_page_ending_at_the_target_and_preserves_delivery_details(
    service: DemoRoomService,
    client: TestClient,
) -> None:
    seed_history(service)
    target = client.get(f"{ROOM}/message/agent-relay-msg-0012").json()
    history = client.get(ROOM, params={"before_seq": target["seq"] + 1, "limit": 5}).json()
    assert [message["seq"] for message in history["messages"]] == list(range(8, 13))
    assert history["messages"][-1] == target
    assert history["hasMore"] and history["hasNewer"]
    assert target["deliveries"]
    assert {delivery["targetMemberId"] for delivery in target["deliveries"]} == set(
        target["recipientIds"]
    )
    assert history["summary"]["totalMessages"] == 125


def test_persistent_event_catchup_covers_resources_subscriptions_and_queue_results(
    service: DemoRoomService,
    client: TestClient,
) -> None:
    cursor = client.get(ROOM).json()["eventId"]
    topic = client.post(f"{ROOM}/topic", json={"name": "联调"}).json()
    member = client.post(
        f"{ROOM}/member",
        json={
            "sessionId": "candidate",
            "name": "联调成员",
            "topicIds": [topic["id"]],
        },
    ).json()
    client.patch(
        f"{ROOM}/member/{member['id']}",
        json={"name": "接口成员", "topicIds": ["backend", topic["id"]]},
    )
    message = client.post(
        f"{ROOM}/message",
        json={
            "publicationId": str(uuid4()),
            "content": "提交到原会话",
            "mentionedMemberIds": [member["id"]],
        },
    ).json()
    submitter = DeliveryService(
        service.store, FakeQueueDriver(), logging.getLogger("tests.events"), 1
    )
    while work := service.store.claim_delivery():
        submitter.submit(work)
    client.delete(f"{ROOM}/topic/{topic['id']}")
    client.delete(f"{ROOM}/member/{member['id']}")

    events: list[RoomEvent] = []
    while True:
        page = client.get(f"{ROOM}/event", params={"after_event_id": cursor, "limit": 7}).json()
        assert not page["resyncRequired"]
        events.extend(RoomEvent.model_validate(event) for event in page["events"])
        cursor = page["nextEventId"]
        if not page["hasMore"]:
            break
    assert len(events) > 7
    assert [event.event_id for event in events] == sorted({event.event_id for event in events})
    assert {event.kind for event in events} == {"topic", "member", "session", "message", "delivery"}
    assert any(event.kind == "message" and event.message_id == message["id"] for event in events)
    assert any(event.kind == "delivery" and event.message_id == message["id"] for event in events)
    metadata = client.get(f"{ROOM}/metadata").json()
    assert metadata["eventId"] == cursor
    assert next(saved for saved in metadata["topics"] if saved["id"] == topic["id"])["deletedAt"]
    saved_member = next(saved for saved in metadata["members"] if saved["id"] == member["id"])
    assert saved_member["deletedAt"] and saved_member["topicIds"] == []
    stored = client.get(f"{ROOM}/message/{message['id']}").json()
    assert stored["deliveries"][0]["status"] == "queued"

    reopened = RoomQueries(SQLiteRoomStore(service.store.path))
    recovered = reopened.events("agent-relay", events[-8].event_id, limit=200)
    assert recovered.events == events[-7:]
    assert RoomService(reopened.store).snapshot("agent-relay").event_id == cursor


def test_websocket_uses_persistent_catchup_and_streams_subsequent_commits(
    client: TestClient,
) -> None:
    cursor = client.get(ROOM).json()["eventId"]
    first = client.post(f"{ROOM}/topic", json={"name": "首次变化"}).json()
    with client.websocket_connect(f"{ROOM}/event/stream?after_event_id={cursor}") as stream:
        catchup = stream.receive_json()
        assert catchup["events"][0]["entityId"] == first["id"]
        second = client.post(f"{ROOM}/topic", json={"name": "持续变化"}).json()
        stream.send_text("poll")
        live = stream.receive_json()
        assert live["events"][0]["entityId"] == second["id"]
        resumed_cursor = live["nextEventId"]
    third = client.post(f"{ROOM}/topic", json={"name": "重连补取"}).json()
    with client.websocket_connect(f"{ROOM}/event/stream?after_event_id={resumed_cursor}") as stream:
        assert stream.receive_json()["events"][0]["entityId"] == third["id"]
