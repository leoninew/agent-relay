import json
import logging
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from room_fixtures import DemoRoomService, create_room_store
from session_fixtures import FakeQueueDriver, FakeSessionDriver

from agent_relay.api import create_app
from agent_relay.delivery_service import DeliveryService
from agent_relay.member_context import MemberContext
from agent_relay.member_context_models import ContextQuery, ContextResult, MemberCatalog
from agent_relay.room_models import CreateMessage, TopicPosition, UpdateMember
from agent_relay.room_queries import RoomQueries
from agent_relay.room_store import SQLiteRoomStore


@dataclass
class ContextEnvironment:
    client: TestClient
    service: DemoRoomService
    member_urls: dict[str, str]

    def query(
        self, request: dict[str, str | int], member: str = "frontend-worker"
    ) -> ContextResult:
        response = self.client.post(f"{self.member_urls[member]}/context", json=request)
        assert response.status_code == 200, response.text
        return ContextResult.model_validate(response.json())


@pytest.fixture
def context(tmp_path: Path) -> Iterator[ContextEnvironment]:
    service = DemoRoomService(create_room_store(tmp_path / "context.sqlite3"))
    member_urls = {}
    for member in service.snapshot("agent-relay").members:
        member_urls[member.id] = f"/api/room/agent-relay/member/{member.id}"
    client = TestClient(
        create_app(
            logging.getLogger("tests.member_context"),
            room_service=service,
            session_driver=FakeSessionDriver(),
            queue_driver=FakeQueueDriver(),
        )
    )
    yield ContextEnvironment(client, service, member_urls)
    client.close()


def positions(result: ContextResult) -> dict[str, TopicPosition]:
    return {position.topic_id: position for position in result.positions}


def seed_history(context: ContextEnvironment) -> None:
    with context.service.store.write() as connection:
        state = RoomQueries(context.service.store).resources_in(connection, "agent-relay")
        for seq in range(7, 91):
            message = context.service._build_message(
                state,
                seq=seq,
                content=f"Context%_ marker {seq}",
                topic_ids=["frontend", "backend"] if seq % 10 == 0 else ["frontend"],
                mentioned_member_ids=[],
                sender_id="coordinator",
                sender_name="主会话",
                created_at=datetime.now(UTC),
            )
            context.service.store.insert_message(connection, state.room.id, message)


def test_catalog_and_position_queries_return_lightweight_routing_context(
    context: ContextEnvironment,
) -> None:
    cursor = RoomQueries(context.service.store).metadata("agent-relay").event_id
    member_url = context.member_urls["frontend-worker"]
    response = context.client.get(f"{member_url}/catalog")
    assert response.status_code == 200
    catalog = MemberCatalog.model_validate(response.json())
    assert catalog.room_id == "agent-relay" and catalog.member_id == "frontend-worker"
    assert {topic.id for topic in catalog.topics if topic.subscribed} == {"frontend", "summary"}
    assert {topic.id for topic in catalog.topics} == {"frontend", "backend", "summary"}
    assert {member.id for member in catalog.members} == set(context.member_urls)
    response = context.client.get(f"{member_url}/position")
    assert response.status_code == 200
    current = {row["topicId"]: row for row in response.json()}
    assert {topic: row["seq"] for topic, row in current.items()} == {"frontend": 0, "summary": 0}
    assert current["frontend"]["laterCount"] == 3
    assert current["summary"]["laterCount"] == 1
    assert RoomQueries(context.service.store).metadata("agent-relay").event_id == cursor


def test_topic_context_pages_in_both_directions_and_allows_history_below_position(
    context: ContextEnvironment,
) -> None:
    seed_history(context)
    backwards = []
    request: dict[str, str | int] = {"topicId": "frontend", "limit": 20}
    while True:
        page = context.query(request)
        backwards.append(page)
        assert positions(page)["frontend"].seq == 90
        if page.next_before_seq is None:
            break
        request["beforeSeq"] = page.next_before_seq
    assert len(backwards) == 5
    assert [message.seq for page in reversed(backwards) for message in page.messages] == list(
        range(4, 91)
    )
    forward: list[int] = []
    request = {"topicId": "frontend", "afterSeq": 0, "limit": 20}
    while True:
        page = context.query(request)
        forward.extend(message.seq for message in page.messages)
        if page.next_after_seq is None:
            break
        request["afterSeq"] = page.next_after_seq
    assert forward == list(range(4, 91))
    assert positions(page)["summary"].seq == 0


def test_keyword_search_uses_literal_body_text_and_member_visible_messages(
    context: ContextEnvironment,
) -> None:
    seed_history(context)
    direct = context.service.post_message(
        "agent-relay",
        CreateMessage(
            publication_id=str(uuid4()),
            content="Context%_ 定向背景",
            topic_ids=["backend"],
            mentioned_member_ids=["frontend-worker"],
        ),
    )
    result = context.query({"keyword": "Context%_", "limit": 200})
    assert [message.seq for message in result.messages] == list(range(7, 92))
    assert result.messages[-1].id == direct.id
    assert {topic: position.seq for topic, position in positions(result).items()} == {
        "frontend": 90,
        "summary": 0,
    }
    tester = context.query(
        {"keyword": "Context%_", "topicId": "frontend", "limit": 200}, "test-worker"
    )
    assert [message.seq for message in tester.messages] == list(range(7, 91))
    assert positions(tester)["frontend"].seq == 90
    assert positions(tester)["backend"].seq == 0


def test_single_context_records_exact_results_and_advances_each_subscribed_topic(
    context: ContextEnvironment,
) -> None:
    before = RoomQueries(context.service.store).metadata("agent-relay").summary
    result = context.query({"messageId": "agent-relay-msg-0004"}, "test-worker")
    assert [message.seq for message in result.messages] == [4]
    assert {topic: position.seq for topic, position in positions(result).items()} == {
        "frontend": 4,
        "backend": 4,
        "summary": 0,
    }
    topic_page = context.query({"topicId": "frontend"}, "test-worker")
    assert positions(topic_page)["frontend"].seq == 6
    assert positions(topic_page)["backend"].seq == 4
    older = context.query({"messageId": "agent-relay-msg-0004"}, "test-worker")
    assert positions(older)["frontend"].seq == 6
    assert positions(older)["backend"].seq == 4
    with context.service.store.read() as connection:
        record = connection.execute(
            "SELECT messages, provided_at FROM member_context_queries WHERE id = ?",
            (result.query_id,),
        ).fetchone()
    assert json.loads(record["messages"]) == [
        {
            "messageId": result.messages[0].id,
            "seq": 4,
            "topicIds": ["frontend", "backend"],
        }
    ]
    assert datetime.fromisoformat(record["provided_at"]).tzinfo is not None
    assert RoomQueries(context.service.store).metadata("agent-relay").summary == before


def test_member_without_subscriptions_can_read_an_actual_direct_message(
    context: ContextEnvironment,
) -> None:
    context.service.delete_topic("agent-relay", "frontend")
    context.service.delete_topic("agent-relay", "summary")
    direct = context.query({"messageId": "agent-relay-msg-0002"})
    assert direct.messages[0].seq == 2
    assert direct.query_id is not None
    assert direct.positions == []
    searched = context.query({"keyword": "请把聊天室"})
    assert [message.seq for message in searched.messages] == [2]
    assert searched.positions == []


def test_subscription_changes_determine_current_context_and_keep_previous_positions(
    context: ContextEnvironment,
) -> None:
    context.query({"topicId": "frontend"})
    context.service.update_member(
        "agent-relay",
        "frontend-worker",
        UpdateMember(
            name="前端成员",
            topic_ids=["backend", "summary"],
        ),
    )
    result = context.query({"messageId": "agent-relay-msg-0003"})
    assert result.messages[0].seq == 3
    assert {topic: position.seq for topic, position in positions(result).items()} == {
        "backend": 3,
        "summary": 0,
    }
    context.service.update_member(
        "agent-relay",
        "frontend-worker",
        UpdateMember(
            name="前端成员",
            topic_ids=["frontend", "summary"],
        ),
    )
    result = context.query({"messageId": "agent-relay-msg-0004"})
    assert positions(result)["frontend"].seq == 6


def test_positions_survive_reopening_and_reach_the_web_through_persistent_events(
    context: ContextEnvironment,
) -> None:
    queries = RoomQueries(context.service.store)
    cursor = queries.metadata("agent-relay").event_id
    result = context.query({"messageId": "agent-relay-msg-0006"})
    page = queries.events("agent-relay", cursor)
    assert [(event.kind, event.entity_id) for event in page.events] == [
        ("position", "frontend-worker")
    ]
    assert (
        next(
            position
            for position in queries.metadata("agent-relay").positions
            if position.member_id == "frontend-worker" and position.topic_id == "frontend"
        ).seq
        == 6
    )
    context.service.post_message(
        "agent-relay",
        CreateMessage(
            publication_id=str(uuid4()),
            content="位置之后的新消息",
            topic_ids=["frontend"],
        ),
    )
    reopened = MemberContext(SQLiteRoomStore(context.service.store.path))
    saved = {
        position.topic_id: position
        for position in reopened.positions("agent-relay", "frontend-worker")
    }
    assert saved["frontend"].seq == 6 and saved["frontend"].later_count == 1
    assert saved["frontend"].updated_at == positions(result)["frontend"].updated_at
    assert reopened.query(
        "agent-relay",
        "frontend-worker",
        ContextQuery(message_id="agent-relay-msg-0004"),
    ).positions == list(saved.values())


def test_concurrent_context_queries_keep_the_maximum_provided_sequence(
    context: ContextEnvironment,
) -> None:
    service = MemberContext(context.service.store)
    member_id = "frontend-worker"
    with ThreadPoolExecutor(max_workers=2) as pool:
        tasks = [
            pool.submit(
                service.query,
                "agent-relay",
                member_id,
                ContextQuery(message_id=f"agent-relay-msg-{seq:04d}"),
            )
            for seq in (6, 4)
        ]
        results = [task.result() for task in tasks]
    assert sorted(result.messages[0].seq for result in results) == [4, 6]
    assert (
        next(
            position
            for position in service.positions("agent-relay", member_id)
            if position.topic_id == "frontend"
        ).seq
        == 6
    )


def test_delivery_envelope_exposes_member_scoped_context_calls_without_credentials(
    context: ContextEnvironment,
) -> None:
    driver = FakeQueueDriver()
    work = context.service.store.claim_delivery()
    assert work is not None
    DeliveryService(
        context.service.store,
        driver,
        logging.getLogger("tests.context.envelope"),
        1,
        "http://testserver",
    ).submit(work)
    envelope = json.loads(driver.calls[0][2].split("\n", 1)[1])
    assert envelope["context"]["headers"] == {"Content-Type": "application/json"}
    catalog = context.client.get(envelope["context"]["catalogUrl"])
    assert catalog.status_code == 200
    assert catalog.json()["memberId"] == work.delivery.target_member_id
    response = context.client.post(
        envelope["context"]["queryUrl"],
        headers=envelope["context"]["headers"],
        json={"messageId": work.message.id},
    )
    assert response.status_code == 200
    assert response.json()["messages"][0]["id"] == work.message.id
    positions_response = context.client.get(envelope["context"]["positionsUrl"])
    assert positions_response.status_code == 200
    assert any(position["seq"] == work.message.seq for position in positions_response.json())
