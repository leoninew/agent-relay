import asyncio
from urllib.request import Request

from agent_relay.interfaces.client import HttpResponse, RelayClient
from agent_relay.interfaces.mcp import create_mcp_server


def test_tool_catalog_exposes_typed_collaboration_and_management() -> None:
    def reject_request(request: Request, *, timeout: float) -> HttpResponse:
        raise AssertionError("Tool discovery must not send HTTP requests")

    server = create_mcp_server(RelayClient("http://unused", 10, opener=reject_request))
    tools = {tool.name: tool for tool in asyncio.run(server.list_tools())}
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
