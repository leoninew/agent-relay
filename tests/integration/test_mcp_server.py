import asyncio
import json
import logging
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from urllib.request import Request

import pytest
from fastapi.testclient import TestClient
from mcp.server.context import ServerRequestContext
from mcp.server.mcpserver import Context, MCPServer
from mcp.types import CallToolResult, TextContent
from room_fixtures import DemoRoomService, create_room_store
from session_fixtures import FakeQueueDriver, FakeSessionDriver

from agent_relay.application.members.sessions import SessionInfo
from agent_relay.bootstrap.http import create_app
from agent_relay.interfaces.client import HttpResponse, RelayClient
from agent_relay.interfaces.mcp import create_mcp_server

ROOM = "agent-relay"


@dataclass
class BufferedResponse:
    status: int
    headers: Mapping[str, str]
    content: bytes

    def read(self) -> bytes:
        return self.content

    def close(self) -> None:
        pass


@dataclass
class McpHarness:
    server: MCPServer[None]
    http: RelayClient
    service: DemoRoomService
    queue_driver: FakeQueueDriver

    def call(
        self, tool_name: str, *, _session: str = "agent-relay-coordinator", **arguments: object
    ) -> Any:
        context: Context[None, Any] = Context(
            request_context=ServerRequestContext(
                session=cast(Any, None),
                lifespan_context=None,
                protocol_version="2025-06-18",
                method="tools/call",
                meta=cast(Any, {"threadId": _session}),
            )
        )
        result = asyncio.run(self.server.call_tool(tool_name, arguments, context=context))
        assert isinstance(result, CallToolResult) and not result.is_error
        payload = result.structured_content
        assert isinstance(payload, dict) and payload["requestId"]
        assert isinstance(result.content[0], TextContent)
        assert json.loads(result.content[0].text) == payload
        return payload["data"]


@pytest.fixture
def mcp(tmp_path: Path) -> Iterator[McpHarness]:
    service = DemoRoomService(create_room_store(tmp_path / "mcp.sqlite3"))
    queue_driver = FakeQueueDriver()
    web = TestClient(
        create_app(
            logging.getLogger("tests.mcp"),
            store=service.store,
            session_driver=FakeSessionDriver(
                [SessionInfo("candidate", "D:/work/mcp", "codex", "MCP candidate", "idle")]
            ),
            queue_driver=queue_driver,
        )
    )

    def open_request(request: Request, *, timeout: float) -> HttpResponse:
        assert timeout == 10
        body = request.data
        assert body is None or isinstance(body, bytes)
        response = web.request(
            request.get_method(),
            request.full_url,
            headers=dict(request.header_items()),
            content=body,
        )
        return BufferedResponse(response.status_code, response.headers, response.content)

    http = RelayClient("http://testserver", 10, opener=open_request)
    yield McpHarness(create_mcp_server(http), http, service, queue_driver)
    web.close()


def test_tool_catalog_exposes_typed_collaboration_and_management(mcp: McpHarness) -> None:
    tools = {tool.name: tool for tool in asyncio.run(mcp.server.list_tools())}
    assert set(tools) == {
        "room_list",
        "room_create",
        "room_get",
        "queue_list",
        "queue_clear",
        "room_metadata",
        "room_events",
        "topic_list",
        "topic_create",
        "topic_update",
        "topic_delete",
        "member_list",
        "member_sessions",
        "member_add",
        "member_update",
        "member_delete",
        "member_catalog",
        "member_context",
        "member_positions",
        "message_list",
        "message_get",
        "message_publish",
        "publication_get",
        "delivery_list",
        "delivery_get",
    }
    publish = tools["message_publish"]
    assert set(publish.input_schema["required"]) == {"room_id", "publication_id", "content"}
    assert {"topic_ids", "mentioned_member_ids"} <= set(publish.input_schema["properties"])
    assert "to_console" not in publish.input_schema["properties"]
    assert "as_member" not in publish.input_schema["properties"]
    assert "member_id" not in tools["member_catalog"].input_schema["properties"]
    assert publish.annotations and publish.annotations.idempotent_hint
    for name in ("member_context", "member_sessions"):
        annotations = tools[name].annotations
        assert annotations and not annotations.read_only_hint
    position_annotations = tools["member_positions"].annotations
    assert position_annotations and position_annotations.read_only_hint
    queue_list = tools["queue_list"]
    assert queue_list.annotations
    assert queue_list.annotations.read_only_hint
    assert queue_list.annotations.idempotent_hint
    assert not queue_list.annotations.destructive_hint
    queue_clear = tools["queue_clear"]
    assert queue_clear.annotations
    assert not queue_clear.annotations.read_only_hint
    assert not queue_clear.annotations.idempotent_hint
    assert queue_clear.annotations.destructive_hint
    assert queue_clear.annotations.open_world_hint
    clear_schema = queue_clear.input_schema["properties"]["clear_codex"]
    assert clear_schema["type"] == "boolean" and clear_schema["default"] is False

    def schema_objects(value: object) -> list[dict[str, object]]:
        if isinstance(value, dict):
            nested = [schema for item in value.values() for schema in schema_objects(item)]
            return [value, *nested]
        if isinstance(value, list):
            return [schema for item in value for schema in schema_objects(item)]
        return []

    for tool_name in ("room_get", "message_list", "queue_list"):
        schema = tools[tool_name].input_schema["properties"]
        before_schemas = schema_objects(schema["before_seq"])
        limit_schemas = schema_objects(schema["limit"])
        assert any(schema.get("minimum") == 1 for schema in before_schemas)
        assert any(schema.get("minimum") == 1 for schema in limit_schemas)
        assert any(schema.get("maximum") == 200 for schema in limit_schemas)
    for tool_name in ("room_get", "message_list"):
        schema = tools[tool_name].input_schema["properties"]
        assert any(schema.get("maxLength") == 200 for schema in schema_objects(schema["keyword"]))


def test_mcp_room_message_and_queue_scopes_share_http_semantics(mcp: McpHarness) -> None:
    room = mcp.call(
        "room_get",
        room_id=ROOM,
        topic_id="frontend",
        member_id="backend-worker",
        keyword="跨话题",
    )
    assert [message["seq"] for message in room["messages"]] == [4, 5]

    messages = mcp.call(
        "message_list",
        room_id=ROOM,
        topic_id="frontend",
        member_id="backend-worker",
        keyword="跨话题",
    )
    assert [message["seq"] for message in messages["messages"]] == [4, 5]

    first = mcp.call(
        "queue_list",
        room_id=ROOM,
        topic_id="backend",
        member_id="backend-worker",
        limit=2,
    )
    assert [message["seq"] for message in first["messages"]] == [6, 5]
    assert first["totalMessages"] == 4
    assert first["hasMore"] and first["nextBeforeSeq"] == 5
    second = mcp.call(
        "queue_list",
        room_id=ROOM,
        topic_id="backend",
        member_id="backend-worker",
        before_seq=first["nextBeforeSeq"],
        limit=2,
    )
    assert [message["seq"] for message in second["messages"]] == [4, 3]
    assert not second["hasMore"] and second["nextBeforeSeq"] is None


def test_mcp_queue_clear_preserves_history_and_only_changes_relay_queue(mcp: McpHarness) -> None:
    with mcp.service.store.write() as connection:
        connection.execute("UPDATE deliveries SET status = 'queued'")
        connection.execute(
            "UPDATE deliveries SET queued_submission_id = 'queue-receipt' "
            "WHERE message_id = 'agent-relay-msg-0006' AND target_member_id = 'frontend-worker'"
        )
    target = ("agent-relay-frontend", "queue-receipt")
    mcp.queue_driver.delete_results[target] = True

    queued = mcp.call("queue_list", room_id=ROOM, member_id="frontend-worker")
    assert [message["seq"] for message in queued["messages"]] == [6, 5, 4, 2, 1]

    cleared = mcp.call("queue_clear", room_id=ROOM, member_id="frontend-worker")
    assert cleared == {"removedMessages": 5}
    assert mcp.call("queue_list", room_id=ROOM, member_id="frontend-worker")["messages"] == []
    assert [
        message["seq"]
        for message in mcp.call("queue_list", room_id=ROOM, member_id="backend-worker")["messages"]
    ] == [3]

    message = mcp.call("message_get", room_id=ROOM, message_id="agent-relay-msg-0006")
    assert all(
        delivery["status"] == "queued" and delivery["deletedAt"]
        for delivery in message["deliveries"]
    )
    history = mcp.call(
        "delivery_list",
        room_id=ROOM,
        message_id=message["id"],
        status="queued",
    )
    assert len(history["deliveries"]) == len(message["deliveries"])
    assert all(delivery["deletedAt"] for delivery in history["deliveries"])
    assert mcp.queue_driver.deletions == []

    external = mcp.call("queue_clear", room_id=ROOM, member_id="frontend-worker", clear_codex=True)
    assert external["removedMessages"] == 0
    assert external["codexQueue"]["deleted"] == 1
    assert mcp.queue_driver.deletions == [target]
    assert mcp.queue_driver.calls == [] and mcp.queue_driver.activations == []


def test_mcp_manages_resources_and_zero_subscriptions(mcp: McpHarness) -> None:
    room = mcp.call("room_create", name="MCP room", project_path="D:/work/mcp")
    room_id = room["id"]
    assert room in mcp.call("room_list")
    assert mcp.call("room_get", room_id=room_id)["messages"] == []
    assert mcp.call("member_sessions", room_id=room_id)[0]["id"] == "candidate"
    member = mcp.call("member_add", room_id=room_id, session_id="candidate", name="MCP member")
    assert member["topicIds"] == []
    topic = mcp.call("topic_create", room_id=room_id, name="MCP topic")
    updated = mcp.call(
        "member_update",
        room_id=room_id,
        member_id=member["id"],
        name="MCP member",
        topic_ids=[topic["id"]],
    )
    assert updated["metadata"] == mcp.call("room_metadata", room_id=room_id)
    edited = mcp.call(
        "topic_update",
        room_id=room_id,
        topic_id=topic["id"],
        name="Updated topic",
        description="Shared description",
    )
    assert edited["description"] == "Shared description"
    topics = mcp.call("topic_list", room_id=room_id)
    assert next(item for item in topics if item["id"] == topic["id"])["name"] == "Updated topic"
    deleted = mcp.call("topic_delete", room_id=room_id, topic_id=topic["id"])
    assert deleted["deletedAt"]
    members = mcp.call("member_list", room_id=room_id)
    assert next(item for item in members if item["id"] == member["id"])["topicIds"] == []
    assert mcp.call("member_delete", room_id=room_id, member_id=member["id"])["deletedAt"]
    assert mcp.call("room_events", room_id=room_id)["events"]


def test_mcp_publication_and_lookup_share_the_http_facts(mcp: McpHarness) -> None:
    message = mcp.call(
        "message_publish",
        room_id=ROOM,
        publication_id="mcp-publication",
        content="MCP 协作",
        topic_ids=["frontend"],
        mentioned_member_ids=["backend-worker"],
        reply_to_message_id="agent-relay-msg-0004",
    )
    assert message["senderId"] == "coordinator"
    assert "frontend-worker" in message["recipientIds"]
    assert "coordinator" not in message["recipientIds"]
    assert mcp.call("publication_get", room_id=ROOM, publication_id="mcp-publication") == message
    assert mcp.http.message_get(ROOM, message["id"]).data == message
    assert mcp.call("message_get", room_id=ROOM, message_id=message["id"]) == message
    assert mcp.call("message_list", room_id=ROOM, limit=1)["messages"] == [message]
    delivery = message["deliveries"][0]
    assert mcp.call(
        "delivery_list",
        room_id=ROOM,
        message_id=message["id"],
        status="pending",
        member_id=delivery["targetMemberId"],
    )["deliveries"] == [delivery]
    assert (
        mcp.call("delivery_get", room_id=ROOM, message_id=message["id"], delivery_id=delivery["id"])
        == delivery
    )


def test_mcp_user_only_message_is_visible_without_leaking_into_unrelated_topics(
    mcp: McpHarness,
) -> None:
    message = mcp.call(
        "message_publish",
        _session="agent-relay-frontend",
        room_id=ROOM,
        publication_id="mcp-console-only",
        content="流程测试已就绪",
        mentioned_member_ids=["user"],
    )

    assert message["senderId"] == "frontend-worker"
    assert message["mentionedMemberIds"] == ["user"]
    assert message["recipientIds"] == ["user"]
    assert message["deliveries"] == []
    assert mcp.call("message_get", room_id=ROOM, message_id=message["id"]) == message
    page = mcp.http.message_list(ROOM, topic_id="backend", limit=50).data
    assert isinstance(page, dict)
    page_messages = page.get("messages")
    assert isinstance(page_messages, list) and message not in page_messages
    private_context = mcp.call(
        "member_context",
        _session="agent-relay-backend",
        room_id=ROOM,
        keyword="流程测试已就绪",
    )
    assert private_context["messages"] == []


def test_mcp_member_context_returns_messages_and_persists_positions(mcp: McpHarness) -> None:
    member_id = "frontend-worker"
    catalog = mcp.call("member_catalog", room_id=ROOM, _session="agent-relay-frontend")
    assert catalog["memberId"] == member_id
    result = mcp.call(
        "member_context",
        room_id=ROOM,
        _session="agent-relay-frontend",
        topic_id="frontend",
        keyword="契约",
        before_seq=7,
        limit=2,
    )
    assert result["queryId"] and result["messages"]
    assert all("契约" in message["content"] for message in result["messages"])
    positions = mcp.call("member_positions", room_id=ROOM, _session="agent-relay-frontend")
    assert next(row["seq"] for row in positions if row["topicId"] == "frontend") == max(
        message["seq"] for message in result["messages"]
    )


def test_members_claim_report_progress_and_handoff_using_mcp(mcp: McpHarness) -> None:
    catalog = mcp.call("member_catalog", room_id=ROOM, _session="agent-relay-frontend")
    assert catalog["projectPath"] == "d:/sourcecodes/mywork/agent-relay"
    assert catalog["roomDescription"] == "聊天室界面与消息路由开发"
    request = mcp.http.message_publish(
        ROOM,
        publication_id="work-request",
        content="请认领接口联调并与后端配合",
        mentioned_member_ids=["frontend-worker"],
    ).data
    assert isinstance(request, dict)
    claim = mcp.call(
        "message_publish",
        room_id=ROOM,
        _session="agent-relay-frontend",
        publication_id="work-claim",
        content="我认领前端联调，后端请准备接口",
        mentioned_member_ids=["backend-worker"],
        reply_to_message_id=request["id"],
    )
    progress = mcp.call(
        "message_publish",
        room_id=ROOM,
        _session="agent-relay-backend",
        publication_id="work-progress",
        content="接口已就绪，请继续验证并同步结果",
        mentioned_member_ids=["frontend-worker"],
        reply_to_message_id=claim["id"],
    )
    recent = mcp.call(
        "member_context", room_id=ROOM, _session="agent-relay-frontend", after_seq=6, limit=20
    )
    assert [message["id"] for message in recent["messages"]] == [
        request["id"],
        claim["id"],
        progress["id"],
    ]
    assert claim["recipientIds"] == ["backend-worker"]
    assert progress["recipientIds"] == ["frontend-worker"]
    assert mcp.call("member_catalog", room_id=ROOM)["memberId"] == "coordinator"
    assert mcp.http.session_id is None
