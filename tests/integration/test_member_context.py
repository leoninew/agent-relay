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
from sqlalchemy import select

from agent_relay.application.delivery.service import DeliveryService
from agent_relay.application.members.context import ContextQuery, ContextResult, MemberCatalog
from agent_relay.application.rooms.contracts import CreateMessage, UpdateMember
from agent_relay.bootstrap.http import create_app
from agent_relay.domain.rooms.models import TopicPosition
from agent_relay.domain.rooms.rules import build_message
from agent_relay.infrastructure.persistence.database import Database
from agent_relay.infrastructure.persistence.member_context import (
    SQLAlchemyMemberContext as MemberContext,
)
from agent_relay.infrastructure.persistence.models import ContextMessageRecord, ContextQueryRecord
from agent_relay.infrastructure.persistence.room_queries import SQLAlchemyRoomQueries as RoomQueries


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
            database=service.store.database,
            session_driver=FakeSessionDriver(),
            queue_driver=FakeQueueDriver(),
        )
    )
    yield ContextEnvironment(client, service, member_urls)
    client.close()


def positions(result: ContextResult) -> dict[str, TopicPosition]:
    return {position.topic_id: position for position in result.positions}


def seed_history(context: ContextEnvironment) -> None:
    with context.service.store.write_rooms() as repository:
        state = repository.resources("agent-relay")
        for seq in range(7, 91):
            message = build_message(
                state,
                seq=seq,
                content=f"Context%_ marker {seq}",
                topic_ids=["frontend", "backend"] if seq % 10 == 0 else ["frontend"],
                mentioned_member_ids=[],
                sender_id="coordinator",
                sender_name="主会话",
                created_at=datetime.now(UTC),
            )
            repository.insert_message(state.room.id, message)


def test_catalog_and_position_queries_return_lightweight_routing_context(
    context: ContextEnvironment,
) -> None:
    cursor = RoomQueries(context.service.store.database).metadata("agent-relay").event_id
    member_url = context.member_urls["frontend-worker"]
    response = context.client.get(f"{member_url}/catalog")
    assert response.status_code == 200
    catalog = MemberCatalog.model_validate(response.json())
    assert catalog.room_id == "agent-relay" and catalog.member_id == "frontend-worker"
    assert catalog.room_description == "聊天室界面与消息路由开发"
    assert catalog.project_path == "d:/sourcecodes/mywork/agent-relay"
    assert {topic.id for topic in catalog.topics if topic.subscribed} == {"frontend", "summary"}
    assert {topic.id for topic in catalog.topics} == {"frontend", "backend", "summary"}
    assert {member.id for member in catalog.members} == set(context.member_urls)
    response = context.client.get(f"{member_url}/position")
    assert response.status_code == 200
    current = {row["topicId"]: row for row in response.json()}
    assert {topic: row["seq"] for topic, row in current.items()} == {"frontend": 0, "summary": 0}
    assert current["frontend"]["laterCount"] == 3
    assert current["summary"]["laterCount"] == 1
    assert RoomQueries(context.service.store.database).metadata("agent-relay").event_id == cursor


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
    before = RoomQueries(context.service.store.database).metadata("agent-relay").summary
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
    with context.service.store.database.read() as session:
        record = session.get(ContextQueryRecord, result.query_id)
        provided = list(
            session.scalars(
                select(ContextMessageRecord)
                .where(ContextMessageRecord.query_id == result.query_id)
                .order_by(ContextMessageRecord.position)
            )
        )
    assert record is not None and record.message_id == result.messages[0].id
    assert [(row.message_id, row.position) for row in provided] == [(result.messages[0].id, 0)]
    assert record.provided_at.tzinfo is not None
    assert RoomQueries(context.service.store.database).metadata("agent-relay").summary == before


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
    queries = RoomQueries(context.service.store.database)
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
    reopened = MemberContext(Database(context.service.store.path))
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
    service = MemberContext(context.service.store.database)
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


def test_delivery_context_identifies_member_for_catalog_messages_and_positions(
    context: ContextEnvironment,
) -> None:
    driver = FakeQueueDriver()
    work = context.service.store.claim_delivery()
    assert work is not None
    DeliveryService(
        context.service.store,
        driver,
        logging.getLogger("tests.context.envelope"),
    ).submit(work)
    assert f"roomId: {work.room_id}\n" in driver.calls[0][2]
    member_url = f"/api/room/{work.room_id}/member/{work.delivery.target_member_id}"
    catalog = context.client.get(f"{member_url}/catalog")
    assert catalog.status_code == 200
    assert catalog.json()["memberId"] == work.delivery.target_member_id
    response = context.client.post(
        f"{member_url}/context",
        json={"messageId": work.message.id},
    )
    assert response.status_code == 200
    assert response.json()["messages"][0]["id"] == work.message.id
    positions_response = context.client.get(f"{member_url}/position")
    assert positions_response.status_code == 200
    assert any(position["seq"] == work.message.seq for position in positions_response.json())


def test_recent_member_context_includes_own_publications_and_direct_collaboration(
    context: ContextEnvironment,
) -> None:
    member_id = "frontend-worker"
    context.service.update_member(
        "agent-relay", member_id, UpdateMember(name="Frontend", topic_ids=[])
    )
    claim = context.service.post_message(
        "agent-relay",
        CreateMessage(
            publication_id=uuid4().hex,
            content="我认领接口联调，稍后同步结果",
            mentioned_member_ids=["backend-worker"],
        ),
        member_id=member_id,
    )
    progress = context.service.post_message(
        "agent-relay",
        CreateMessage(
            publication_id=uuid4().hex,
            content="后端已准备好，请开始联调",
            mentioned_member_ids=[member_id],
            reply_to_message_id=claim.id,
        ),
        member_id="backend-worker",
    )
    recent = context.query({"limit": 2})
    assert [message.id for message in recent.messages] == [claim.id, progress.id]
    assert recent.query_id and recent.positions == []
    assert context.query({"messageId": claim.id}).messages[0].sender_id == member_id
