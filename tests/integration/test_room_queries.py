import logging
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from room_fixtures import DemoRoomService, create_room_store
from session_fixtures import FakeQueueDriver, FakeSessionDriver

from agent_relay.application.delivery.ports import QueueHead, ReceivedInput
from agent_relay.application.delivery.service import DeliveryService
from agent_relay.application.members.context import ContextQuery
from agent_relay.application.members.sessions import SessionInfo
from agent_relay.application.rooms.contracts import CreateMessage, RoomEvent, UpdateMember
from agent_relay.application.rooms.service import RoomService
from agent_relay.bootstrap.http import create_app
from agent_relay.domain.rooms.rules import build_message
from agent_relay.infrastructure.persistence.context import SQLiteMemberContext as MemberContext
from agent_relay.infrastructure.persistence.queries import SQLiteRoomQueries as RoomQueries
from agent_relay.infrastructure.persistence.store import SQLiteRoomStore

ROOM = "/api/room/agent-relay"


@pytest.fixture
def service(tmp_path: Path) -> DemoRoomService:
    return DemoRoomService(create_room_store(tmp_path / "rooms.sqlite3"))


@pytest.fixture
def queue_driver() -> FakeQueueDriver:
    return FakeQueueDriver()


@pytest.fixture
def client(service: DemoRoomService, queue_driver: FakeQueueDriver) -> Iterator[TestClient]:
    # The query tests do not start the background dispatcher; submissions are explicit.
    client = TestClient(
        create_app(
            logging.getLogger("tests.room.queries"),
            store=service.store,
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
            queue_driver=queue_driver,
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
            message = build_message(
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


def test_queue_includes_old_messages_once_and_pages_before_chat_history(
    service: DemoRoomService, client: TestClient
) -> None:
    seed_history(service)
    with service.store.write() as connection:
        connection.execute("UPDATE deliveries SET status = 'queued'")

    assert client.get(ROOM).json()["messages"][0]["seq"] == 76
    first = client.get(f"{ROOM}/queue").json()
    assert [message["seq"] for message in first["messages"]] == list(range(125, 75, -1))
    assert first["totalMessages"] == 125
    assert first["hasMore"] and first["nextBeforeSeq"] == 76
    second = client.get(f"{ROOM}/queue", params={"before_seq": 76}).json()
    last = client.get(f"{ROOM}/queue", params={"before_seq": second["nextBeforeSeq"]}).json()
    messages = first["messages"] + second["messages"] + last["messages"]
    assert [message["seq"] for message in messages] == list(range(125, 0, -1))
    assert len({message["id"] for message in messages}) == 125
    assert not last["hasMore"] and last["nextBeforeSeq"] is None
    assert all(message["deliveries"] for message in messages)
    assert client.get(f"{ROOM}/metadata").json()["summary"]["queuedCount"] > 125
    assert client.get("/api/room/housekeeper/queue").json() == {
        "messages": [],
        "totalMessages": 0,
        "hasMore": False,
        "nextBeforeSeq": None,
    }


def test_queue_includes_active_dispatches_and_partial_receipts_but_excludes_failed_messages(
    service: DemoRoomService, client: TestClient
) -> None:
    first = "agent-relay-msg-0001"
    with service.store.write() as connection:
        connection.execute("UPDATE deliveries SET status = 'received'")
        connection.execute(
            "UPDATE deliveries SET status = 'queued' WHERE message_id = ? "
            "AND target_member_id = 'frontend-worker'",
            (first,),
        )
        for seq, status in ((2, "pending"), (3, "submitting"), (4, "rejected"), (5, "unknown")):
            connection.execute(
                "UPDATE deliveries SET status = ? WHERE message_id = ?",
                (status, f"agent-relay-msg-{seq:04d}"),
            )

    partial = client.get(f"{ROOM}/queue").json()
    assert partial["totalMessages"] == 3
    assert [message["seq"] for message in partial["messages"]] == [3, 2, 1]
    assert {delivery["status"] for delivery in partial["messages"][-1]["deliveries"]} == {
        "queued",
        "received",
    }
    assert not partial["hasMore"]
    with service.store.write() as connection:
        connection.execute(
            "UPDATE deliveries SET status = 'received' WHERE message_id = ?", (first,)
        )
    assert client.get(f"{ROOM}/queue").json()["totalMessages"] == 2
    with service.store.write() as connection:
        connection.execute("UPDATE deliveries SET status = 'received'")
    assert client.get(f"{ROOM}/queue").json()["messages"] == []
    assert client.get(f"{ROOM}/queue").json()["totalMessages"] == 0
    assert client.get(f"{ROOM}/message/{first}").json()["deliveries"]


def test_queue_validates_room_and_pagination(client: TestClient) -> None:
    assert client.get("/api/room/missing/queue").status_code == 404
    assert client.get(f"{ROOM}/queue", params={"limit": 201}).status_code == 422
    assert client.get(f"{ROOM}/queue", params={"before_seq": 0}).status_code == 422
    assert client.get(f"{ROOM}/queue", params={"topic_id": "missing"}).status_code == 404
    assert client.get(f"{ROOM}/queue", params={"member_id": "missing"}).status_code == 404
    assert (
        client.get("/api/room/housekeeper/queue", params={"topic_id": "frontend"}).status_code
        == 404
    )


def test_queue_filters_scope_before_pagination_and_counts_the_entire_scope(
    service: DemoRoomService, client: TestClient
) -> None:
    seed_history(service)
    with service.store.write() as connection:
        connection.execute(
            "UPDATE deliveries SET status = 'received' WHERE message_id = 'agent-relay-msg-0124'"
        )
    expected = [
        seq
        for seq in range(125, 0, -1)
        if seq in (4, 5, 6) or (seq >= 7 and seq % 3 != 2 and seq != 124)
    ]
    params: dict[str, str | int] = {
        "topic_id": "frontend",
        "member_id": "frontend-worker",
        "limit": 9,
    }
    messages = []
    while True:
        response = client.get(f"{ROOM}/queue", params=params)
        assert response.status_code == 200
        page = response.json()
        assert page["totalMessages"] == len(expected)
        messages.extend(page["messages"])
        if not page["hasMore"]:
            assert page["nextBeforeSeq"] is None
            break
        assert page["nextBeforeSeq"] == page["messages"][-1]["seq"]
        params["before_seq"] = page["nextBeforeSeq"]
    assert [message["seq"] for message in messages] == expected
    assert all(
        "frontend" in message["topicIds"]
        and (
            message["senderId"] == "frontend-worker" or "frontend-worker" in message["recipientIds"]
        )
        for message in messages
    )


def test_queue_member_scope_matches_senders_and_resolved_recipients(
    service: DemoRoomService, client: TestClient
) -> None:
    publications = [
        ("frontend-worker", ["backend-worker", "user"]),
        ("backend-worker", ["frontend-worker"]),
        ("backend-worker", ["test-worker"]),
        (None, ["frontend-worker"]),
    ]
    for index, (sender_id, mentioned_member_ids) in enumerate(publications):
        service.post_message(
            "agent-relay",
            CreateMessage(
                publication_id=f"queue-scope-{index}",
                content=f"队列范围消息 {index}",
                mentioned_member_ids=mentioned_member_ids,
            ),
            member_id=sender_id,
        )
    cases = [
        ({"member_id": "frontend-worker"}, [10, 8, 7, 6, 5, 4, 2, 1]),
        ({"member_id": "user"}, [10, 7]),
        ({"topic_id": "frontend"}, [6, 5, 4]),
        ({"topic_id": "frontend", "member_id": "user"}, []),
    ]
    for scope, expected in cases:
        response = client.get(f"{ROOM}/queue", params=scope)
        assert response.status_code == 200
        page = response.json()
        assert [message["seq"] for message in page["messages"]] == expected
        assert page["totalMessages"] == len(expected)


def test_clear_queue_marks_every_page_in_scope_and_preserves_history_and_receipts(
    service: DemoRoomService, client: TestClient, queue_driver: FakeQueueDriver
) -> None:
    seed_history(service)
    with service.store.write() as connection:
        connection.execute("UPDATE deliveries SET status = 'queued'")
        connection.execute(
            "UPDATE deliveries SET status = 'received', received_at = updated_at "
            "WHERE message_id = 'agent-relay-msg-0004' AND target_member_id = 'frontend-worker'"
        )
    original = client.get(f"{ROOM}/message/agent-relay-msg-0004").json()
    cursor = client.get(f"{ROOM}/metadata").json()["eventId"]
    scope = {"topic_id": "frontend"}
    total = client.get(f"{ROOM}/queue", params={**scope, "limit": 1}).json()["totalMessages"]
    assert total > 50
    cleared = client.delete(f"{ROOM}/queue", params=scope)
    assert cleared.status_code == 200
    assert cleared.json() == {"removedMessages": total}
    assert client.get(f"{ROOM}/queue", params=scope).json()["messages"] == []
    assert all(
        "frontend" not in message["topicIds"]
        for message in client.get(f"{ROOM}/queue", params={"limit": 200}).json()["messages"]
    )
    saved = client.get(f"{ROOM}/message/{original['id']}").json()
    assert saved["content"] == original["content"]
    for before, after in zip(original["deliveries"], saved["deliveries"], strict=True):
        assert after["status"] == before["status"]
        assert after["queuedAt"] == before["queuedAt"]
        assert after["receivedAt"] == before["receivedAt"]
        assert after["receipt"] == before["receipt"]
        assert bool(after["deletedAt"]) == (before["status"] != "received")
    metadata = client.get(f"{ROOM}/metadata").json()
    assert metadata["summary"]["totalMessages"] == 125
    assert metadata["summary"]["receivedCount"] == 1
    events = client.get(f"{ROOM}/event", params={"after_event_id": cursor}).json()["events"]
    assert events and all(event["kind"] == "delivery" for event in events)
    assert client.delete(f"{ROOM}/queue", params=scope).json() == {"removedMessages": 0}
    assert client.get(f"{ROOM}/metadata").json()["eventId"] == metadata["eventId"]
    assert queue_driver.calls == []
    assert queue_driver.activations == []


def test_clear_queue_excludes_removed_deliveries_from_background_processing(
    service: DemoRoomService, client: TestClient
) -> None:
    work = service.store.claim_delivery()
    assert work is not None
    with service.store.write() as connection:
        connection.execute("UPDATE deliveries SET status = 'queued' WHERE status = 'pending'")
    assert client.delete(f"{ROOM}/queue").status_code == 200
    removed = RoomQueries(service.store).message(work.room_id, work.message.id)
    assert all(delivery.deleted_at is not None for delivery in removed.deliveries)
    assert service.store.claim_delivery() is None
    assert service.store.unconfirmed_inputs() == {}
    assert not service.store.claim_activation(
        work.delivery.target_session_id, QueueHead("queued", work.delivery.client_message_id)
    )
    work.delivery.status = "queued"
    assert not service.store.finish_delivery(work.room_id, work.delivery)
    for delivery in removed.deliveries:
        service.store.confirm_input(
            delivery.target_session_id,
            ReceivedInput(delivery.client_message_id, "late-input", "late-turn"),
        )
        service.store.delivery_note(delivery.target_session_id, delivery.client_message_id, "late")
    service.store.interrupt_submissions()
    assert RoomQueries(service.store).message(work.room_id, work.message.id) == removed
    assert client.get(f"{ROOM}/queue").json()["totalMessages"] == 0


def test_clear_queue_validates_scope_and_leaves_unrelated_messages(
    client: TestClient,
) -> None:
    assert client.delete("/api/room/missing/queue").status_code == 404
    assert client.delete(f"{ROOM}/queue", params={"member_id": "missing"}).status_code == 404
    assert client.delete(f"{ROOM}/queue", params={"topic_id": "missing"}).status_code == 404
    cleared = client.delete(f"{ROOM}/queue", params={"member_id": "frontend-worker"})
    assert cleared.status_code == 200
    assert cleared.json() == {"removedMessages": 5}
    assert [message["seq"] for message in client.get(f"{ROOM}/queue").json()["messages"]] == [3]


def test_message_names_follow_members_across_history_context_and_delivery(
    service: DemoRoomService, client: TestClient
) -> None:
    request = CreateMessage(
        publication_id=str(uuid4()),
        content="成员改名后仍属于同一会话",
        mentioned_member_ids=["backend-worker"],
    )
    message = service.post_message("agent-relay", request, member_id="frontend-worker")
    renamed = service.update_member(
        "agent-relay", "frontend-worker", UpdateMember(name="界面开发", topic_ids=["frontend"])
    )
    for route in (ROOM, f"{ROOM}/message"):
        saved = next(
            saved for saved in client.get(route).json()["messages"] if saved["id"] == message.id
        )
        assert saved["senderId"] == renamed.id
        assert saved["senderName"] == renamed.name
    assert client.get(f"{ROOM}/message/{message.id}").json()["senderName"] == renamed.name
    assert (
        service.publication("agent-relay", request.publication_id, member_id=renamed.id).sender_name
        == renamed.name
    )
    assert service.post_message("agent-relay", request, member_id=renamed.id).sender_name == (
        renamed.name
    )
    context = MemberContext(service.store).query(
        "agent-relay", "backend-worker", ContextQuery(message_id=message.id)
    )
    assert context.messages[0].sender_name == renamed.name
    claimed_names = []
    while work := service.store.claim_delivery():
        if work.message.id == message.id:
            claimed_names.append(work.message.sender_name)
        work.delivery.status = "queued"
        service.store.finish_delivery(work.room_id, work.delivery)
    assert claimed_names == [renamed.name]

    service.delete_member("agent-relay", renamed.id)
    restored = RoomQueries(SQLiteRoomStore(service.store.path)).message("agent-relay", message.id)
    assert restored.sender_id == renamed.id
    assert restored.sender_name == renamed.name


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


def test_topic_and_member_filter_before_pagination_keep_whole_room_statistics(
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
    assert [message["seq"] for message in messages] == [4, 5, 6] + [
        seq for seq in range(7, 126) if seq % 3 != 2
    ]
    assert all(
        "frontend" in message["topicIds"]
        and (
            message["senderId"] == "frontend-worker" or "frontend-worker" in message["recipientIds"]
        )
        for message in messages
    )
    assert client.get(f"{ROOM}/metadata").json() == full


def test_keyword_search_filters_history_before_pagination_and_keeps_room_totals(
    service: DemoRoomService, client: TestClient
) -> None:
    seed_history(service)
    full = client.get(f"{ROOM}/metadata").json()
    params: dict[str, str | int] = {
        "keyword": "历史消息 1",
        "topic_id": "frontend",
        "member_id": "frontend-worker",
        "limit": 3,
    }
    snapshot = client.get(ROOM, params=params).json()
    assert snapshot["summary"] == full["summary"]
    assert snapshot["topics"] == full["topics"]
    pages = [snapshot]
    while pages[-1]["hasMore"]:
        params["before_seq"] = pages[-1]["nextBeforeSeq"]
        pages.append(client.get(f"{ROOM}/message", params=params).json())
    messages = [message for page in reversed(pages) for message in page["messages"]]
    assert [message["seq"] for message in messages] == [
        seq for seq in range(7, 126) if str(seq).startswith("1") and seq % 3 != 2
    ]
    assert messages[0]["seq"] == 10
    assert len(pages) > 1


def test_keyword_search_is_literal_and_blank_keywords_restore_the_list(
    service: DemoRoomService, client: TestClient
) -> None:
    for index, content in enumerate(["Search%_ Exact", "Searchxy Exact", "search%_ Exact"]):
        service.post_message(
            "agent-relay",
            CreateMessage(
                publication_id=f"search-{index}", content=content, topic_ids=["frontend"]
            ),
        )
    for route in (ROOM, f"{ROOM}/message"):
        response = client.get(route, params={"keyword": " Search%_ "})
        assert response.status_code == 200
        assert [message["content"] for message in response.json()["messages"]] == ["Search%_ Exact"]
        assert client.get(route, params={"keyword": "不存在的关键词"}).json()["messages"] == []
        assert client.get(route, params={"keyword": " "}).json() == client.get(route).json()
        invalid = client.get(route, params={"keyword": "字" * 201})
        assert invalid.status_code == 422
        assert invalid.json()["code"] == "validation_error"
        assert invalid.json()["requestId"]


def test_topic_and_member_filters_use_explicit_topics_and_resolved_recipients(
    service: DemoRoomService, client: TestClient
) -> None:
    publications = [
        ("frontend-worker", ["frontend"], ["user"]),
        ("backend-worker", ["frontend"], []),
        ("backend-worker", [], ["frontend-worker"]),
        ("backend-worker", [], ["user"]),
        ("backend-worker", ["backend"], ["user"]),
        ("backend-worker", [], ["test-worker"]),
        (None, [], ["frontend-worker"]),
    ]
    for index, (sender_id, topic_ids, mentioned_member_ids) in enumerate(publications):
        service.post_message(
            "agent-relay",
            CreateMessage(
                publication_id=f"filter-{index}",
                content=f"筛选消息 {index}",
                topic_ids=topic_ids,
                mentioned_member_ids=mentioned_member_ids,
            ),
            member_id=sender_id,
        )
    cases = [
        ({}, list(range(1, 14))),
        ({"topic_id": "frontend"}, [4, 5, 6, 7, 8]),
        ({"member_id": "frontend-worker"}, [1, 2, 4, 5, 6, 7, 8, 9, 13]),
        ({"member_id": "user"}, [7, 10, 11, 13]),
        ({"topic_id": "frontend", "member_id": "frontend-worker"}, [4, 5, 6, 7, 8]),
        ({"topic_id": "frontend", "member_id": "user"}, [7]),
        ({"topic_id": "backend", "member_id": "user"}, [11]),
        ({"topic_id": "summary", "member_id": "user"}, []),
    ]
    for filters, expected in cases:
        snapshot = client.get(ROOM, params=filters).json()
        assert [message["seq"] for message in snapshot["messages"]] == expected
        page = client.get(f"{ROOM}/message", params={**filters, "before_seq": 10}).json()
        assert [message["seq"] for message in page["messages"]] == [
            seq for seq in expected if seq < 10
        ]
        assert page["hasNewer"] == any(seq >= 10 for seq in expected)
        assert not page["hasMore"]
        assert snapshot["summary"]["totalMessages"] == 13


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
    submitter = DeliveryService(service.store, FakeQueueDriver(), logging.getLogger("tests.events"))
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
