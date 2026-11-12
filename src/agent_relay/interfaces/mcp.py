"""MCP adapter over the same HTTP client used by the Click commands."""

import json
from collections.abc import Awaitable, Callable
from functools import partial, wraps
from typing import Any

from mcp.server.mcpserver import Context, MCPServer
from mcp.types import CallToolResult, TextContent, ToolAnnotations
from starlette.concurrency import run_in_threadpool

from agent_relay.interfaces.client import RelayClient, RelayClientError
from agent_relay.interfaces.dto import ApiResult

READ_TOOLS = frozenset(
    {
        "room_list",
        "room_get",
        "queue_list",
        "room_metadata",
        "room_events",
        "topic_list",
        "member_list",
        "member_catalog",
        "member_positions",
        "message_list",
        "message_get",
        "publication_get",
        "delivery_list",
        "delivery_get",
    }
)

WRITE_TOOLS = frozenset(
    {
        "room_create",
        "queue_clear",
        "topic_create",
        "topic_update",
        "topic_delete",
        "member_sessions",
        "member_add",
        "member_update",
        "member_delete",
        "member_context",
        "message_publish",
    }
)


def _tool_handler(
    action: Callable[..., ApiResult],
) -> Callable[..., Awaitable[CallToolResult]]:
    @wraps(action)
    async def handle(**arguments: Any) -> CallToolResult:
        return await _invoke(partial(action, **arguments))

    return handle


async def _invoke(action: Callable[[], ApiResult]) -> CallToolResult:
    try:
        result = await run_in_threadpool(action)
        payload: dict[str, object] = {"requestId": result.request_id, "data": result.data}
        is_error = False
    except RelayClientError as exc:
        payload = {"requestId": exc.request_id, "error": exc.error}
        is_error = True
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))],
        structured_content=payload,
        is_error=is_error,
    )


def _caller(client: RelayClient, ctx: Context[None, Any]) -> RelayClient:
    try:
        meta = ctx.request_context.meta
    except ValueError:
        meta = None
    session_id = meta.get("threadId") if meta else None
    if not isinstance(session_id, str) or not session_id:
        session_id = client.session_id
    if not session_id:
        raise RelayClientError(2, "session_required", "MCP 调用缺少 Codex 会话上下文")
    return client.for_session(session_id)


def create_mcp_server(client: RelayClient) -> MCPServer[None]:
    server: MCPServer[None] = MCPServer(
        "agent-relay",
        instructions=(
            "Use the agent-relay skill to collaborate. Member tools resolve your identity from "
            "the MCP request's Codex threadId and room_id. Use member_catalog to discover "
            "topics and members, including the human member named 你. Publish explicit messages "
            "using topics and/or member mentions; ordinary model output is not published. "
            "Human recipients never enter the Codex queue. queue_list reads active unfinished "
            "deliveries; delivery_list and delivery_get preserve history, including deletedAt. "
            "queue_clear defaults to Relay only. Set clear_codex=true only when authorized to "
            "delete matching waiting Codex items. It does not interrupt running turns. "
            "Do not infer task completion from queued, received or an empty queue. "
            "Retain publication_id and look up unknown publications without retry; do not blindly "
            "retry a queue_clear with an unknown outcome."
        ),
    )

    async def member_catalog(room_id: str, ctx: Context[None, Any]) -> CallToolResult:
        """Discover your room/project context, member identity, topics, subscriptions and peers."""
        return await _invoke(lambda: _caller(client, ctx).member_catalog(room_id))

    async def member_context(
        room_id: str,
        ctx: Context[None, Any],
        message_id: str | None = None,
        topic_id: str | None = None,
        keyword: str | None = None,
        before_seq: int | None = None,
        after_seq: int | None = None,
        limit: int = 50,
    ) -> CallToolResult:
        """Read recent messages visible to you, optionally filtered by topic, keyword or ID.
        Single-message lookup excludes other filters. Choose one cursor direction; limit 1..200.
        Persists provided messages and advances query positions, which are not read receipts.
        """
        return await _invoke(
            lambda: _caller(client, ctx).member_context(
                room_id,
                message_id=message_id,
                topic_id=topic_id,
                keyword=keyword,
                before_seq=before_seq,
                after_seq=after_seq,
                limit=limit,
            )
        )

    async def member_positions(room_id: str, ctx: Context[None, Any]) -> CallToolResult:
        """Read your topic query positions and later message counts, without advancing them."""
        return await _invoke(lambda: _caller(client, ctx).member_positions(room_id))

    async def message_publish(
        room_id: str,
        publication_id: str,
        content: str,
        ctx: Context[None, Any],
        topic_ids: list[str] | None = None,
        mentioned_member_ids: list[str] | None = None,
        reply_to_message_id: str | None = None,
    ) -> CallToolResult:
        """Publish as yourself to topics and/or members discovered through member_catalog.
        Mention the human member named 你 to reply to the user, even with no other Agent present.
        Human recipients are shown in the room and never enter the Codex queue.
        Retain publication_id for lookup. References do not inherit targets. Saved is not received.
        """
        return await _invoke(
            lambda: _caller(client, ctx).message_publish(
                room_id,
                publication_id,
                content,
                topic_ids,
                mentioned_member_ids,
                reply_to_message_id,
            )
        )

    async def publication_get(
        room_id: str, publication_id: str, ctx: Context[None, Any]
    ) -> CallToolResult:
        """Find your original saved publication without sending again."""
        return await _invoke(lambda: _caller(client, ctx).publication_get(room_id, publication_id))

    member_tools: dict[str, Callable[..., Awaitable[CallToolResult]]] = {
        "member_catalog": member_catalog,
        "member_context": member_context,
        "member_positions": member_positions,
        "message_publish": message_publish,
        "publication_get": publication_get,
    }
    for name in sorted(READ_TOOLS | WRITE_TOOLS):
        handler = (
            member_tools[name] if name in member_tools else _tool_handler(getattr(client, name))
        )
        read_only = name in READ_TOOLS
        server.add_tool(
            handler,
            name=name,
            structured_output=False,
            annotations=ToolAnnotations(
                read_only_hint=read_only,
                destructive_hint=name.endswith(("_update", "_delete")) or name == "queue_clear",
                idempotent_hint=read_only or name == "message_publish",
                open_world_hint=name
                in {"message_publish", "member_sessions", "member_add", "queue_clear"},
            ),
        )
    return server
