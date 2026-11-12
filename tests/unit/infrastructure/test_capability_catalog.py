import hashlib
from copy import deepcopy
from typing import Any

import pytest
from pydantic import ValidationError

from agent_relay.domain.rooms.models import McpServerReference
from agent_relay.infrastructure.codex.catalog import decode_skills, server_option
from agent_relay.infrastructure.codex.models import McpPage


def test_skill_identity_distinguishes_sources_and_paths_without_exposing_native_fields(
    skill_payload: dict[str, Any],
) -> None:
    payload = skill_payload
    skill = payload["data"][0]["skills"][0]
    payload["data"][0]["skills"] += [
        {**skill, "scope": "user", "path": "C:/Users/private/skills/example/SKILL.md"},
        {**skill, "pluginId": "example@local", "path": "C:/plugins/private/example/SKILL.md"},
    ]
    payload["data"][0]["errors"] = [{"path": "C:/private", "message": "secret-token"}]
    first = decode_skills(payload, "d:/PROJECT")
    second = decode_skills(deepcopy(payload), "D:/project/")
    catalog = first.public_catalog()
    assert catalog == second.public_catalog()
    assert len({item.id for item in catalog.skills}) == 3
    assert catalog.skills[0].display_name == "Example"
    assert catalog.skills[0].description == "Short description"
    assert catalog.skills[-1].source == "plugin"
    assert catalog.errors[0].code == "skill_load_failed"
    serialized = catalog.model_dump_json(by_alias=True)
    assert (
        "C:/" not in serialized
        and "SKILL.md" not in serialized
        and "secret-token" not in serialized
    )
    assert first.bindings[0].native_path.endswith("SKILL.md")


def test_empty_skill_catalog_is_success_and_invalid_payloads_are_failures(
    skill_payload: dict[str, Any],
) -> None:
    payload = skill_payload
    payload["data"][0]["skills"] = []
    assert decode_skills(payload, "D:/project").public_catalog().skills == []
    with pytest.raises(ValueError, match="requested directory"):
        decode_skills(payload, "D:/other")
    with pytest.raises(ValidationError):
        decode_skills({"data": [{"cwd": "D:/project", "skills": []}]}, "D:/project")


@pytest.mark.parametrize("runtime", ["connected", "failed", "authenticationRequired", None])
def test_mcp_availability_uses_target_runtime_and_exposes_only_safe_tools(
    runtime: str | None,
    mcp_server: dict[str, Any],
) -> None:
    server = mcp_server
    server["runtimeStatus"] = runtime
    server["tools"]["read"]["inputSchema"] = {"token": "secret-token", "path": "C:/private"}
    server["httpOrigin"] = "https://private.invalid"
    page = McpPage.model_validate({"data": [server], "nextCursor": None})
    option = server_option(page.data[0])
    assert option.available is (runtime == "connected")
    assert option.tools[0].name == "read"
    serialized = option.model_dump_json()
    assert "secret-token" not in serialized and "C:/private" not in serialized
    assert "httpOrigin" not in serialized and "authStatus" not in serialized


def test_mcp_partial_error_is_safe_and_not_a_successful_empty_catalog(
    mcp_server: dict[str, Any],
) -> None:
    server = mcp_server
    server["tools"] = {}
    server["toolsError"] = "secret-token at C:/private"
    page = McpPage.model_validate({"data": [server], "nextCursor": None})
    option = server_option(page.data[0])
    assert not option.available and option.errors[0].code == "mcp_tools_unavailable"
    assert "secret-token" not in option.model_dump_json()


@pytest.mark.parametrize("name", ["_local", "plugin/local server"])
def test_native_mcp_names_round_trip_as_opaque_message_references(
    name: str, mcp_server: dict[str, Any]
) -> None:
    mcp_server["name"] = name
    page = McpPage.model_validate({"data": [mcp_server], "nextCursor": None})
    option = server_option(page.data[0])
    reference = McpServerReference(id=option.id, name=option.name)

    expected_id = "mcp-" + hashlib.sha256(name.encode("utf-8")).hexdigest()
    assert reference.id == expected_id
    assert reference.name == name
