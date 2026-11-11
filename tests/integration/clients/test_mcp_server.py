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
from support.databases import MemoryDatabases
from support.room_fixtures import DemoRoomService
from support.session_fixtures import FakeQueueDriver, FakeSessionDriver

from agent_relay.bootstrap.http import create_app
from agent_relay.interfaces.client import HttpResponse, RelayClient
from agent_relay.interfaces.mcp import create_mcp_server


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

    def call(
        self, tool_name: str, *, session: str = "agent-relay-frontend", **arguments: object
    ) -> Any:
        context: Context[None, Any] = Context(
            request_context=ServerRequestContext(
                session=cast(Any, None),
                lifespan_context=None,
                protocol_version="2025-06-18",
                method="tools/call",
                meta=cast(Any, {"threadId": session}),
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
def mcp(tmp_path: Path, databases: MemoryDatabases) -> Iterator[McpHarness]:
    service = DemoRoomService(databases.store(tmp_path / "mcp.sqlite3"))
    client = TestClient(
        create_app(
            logging.getLogger("tests.mcp"),
            database=service.store.database,
            session_driver=FakeSessionDriver(),
            queue_driver=FakeQueueDriver(),
        )
    )

    def open_request(request: Request, *, timeout: float) -> HttpResponse:
        assert request.data is None or isinstance(request.data, bytes)
        response = client.request(
            request.get_method(),
            request.full_url,
            headers=dict(request.header_items()),
            content=request.data,
        )
        return BufferedResponse(response.status_code, response.headers, response.content)

    yield McpHarness(create_mcp_server(RelayClient("http://testserver", 10, opener=open_request)))
    client.close()


def test_mcp_manages_resources_through_http(mcp: McpHarness) -> None:
    room = mcp.call("room_create", name="Tool room", project_path="D:/tools")
    assert room in mcp.call("room_list")
    topic = mcp.call("topic_create", room_id=room["id"], name="Tool topic")
    assert topic["id"] in {item["id"] for item in mcp.call("topic_list", room_id=room["id"])}
    assert mcp.call("topic_delete", room_id=room["id"], topic_id=topic["id"])["deletedAt"]


def test_mcp_uses_each_call_session_for_publication_and_context(mcp: McpHarness) -> None:
    message = mcp.call(
        "message_publish",
        room_id="agent-relay",
        publication_id="claim",
        content="I will take this",
        mentioned_member_ids=["backend-worker"],
    )
    assert message["senderId"] == "frontend-worker"
    assert mcp.call("publication_get", room_id="agent-relay", publication_id="claim") == message
    recent = mcp.call(
        "member_context", room_id="agent-relay", session="agent-relay-backend", limit=1
    )
    assert recent["messages"][0]["id"] == message["id"]
    assert mcp.call("member_catalog", room_id="agent-relay")["memberId"] == "frontend-worker"
