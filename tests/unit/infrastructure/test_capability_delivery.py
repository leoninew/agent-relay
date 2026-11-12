from copy import deepcopy
from typing import Any, Self

import pytest

from agent_relay.application.delivery.ports import QueueRejected, QueueRequest
from agent_relay.domain.rooms.models import McpServerReference, SkillReference
from agent_relay.infrastructure.codex.catalog import McpPage, decode_skills, server_option
from agent_relay.infrastructure.codex.driver import CodexDriver, RpcDisconnected, RpcRejected


class QueueWire:
    def __init__(self, skills: dict[str, Any], server: dict[str, Any]) -> None:
        self.skills = skills
        self.skills["data"][0]["skills"].append(
            {
                "name": "agent-relay:agent-relay",
                "pluginId": "agent-relay@agent-relay-local",
                "path": "C:/plugins/agent-relay/SKILL.md",
                "scope": "user",
                "description": "Relay",
                "enabled": True,
            }
        )
        self.server = server
        self.server["name"] = "plugin/local server"
        self.thread = {
            "id": "original",
            "cwd": "D:/project",
            "modelProvider": "test",
            "status": {"type": "idle"},
        }
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.add_error: Exception | None = None
        self.bad_receipt = False

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        pass

    def call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((method, params))
        if method == "thread/read":
            return {"thread": self.thread}
        if method == "skills/list":
            assert params == {"cwds": ["D:/project"], "forceReload": True}
            return self.skills
        if method == "mcpServerStatus/list":
            assert params["threadId"] == self.thread["id"]
            return {"data": [self.server], "nextCursor": None}
        assert method == "thread/queue/add"
        if self.add_error:
            raise self.add_error
        return {
            "queuedSubmission": {
                "id": "queued",
                "clientUserMessageId": "wrong"
                if self.bad_receipt
                else params["clientUserMessageId"],
            }
        }

    def request(self) -> QueueRequest:
        bindings = decode_skills(self.skills, "D:/project").bindings
        page = McpPage.model_validate({"data": [self.server], "nextCursor": None})
        server = server_option(page.data[0])
        return QueueRequest(
            "Envelope text",
            "d:/PROJECT",
            (
                SkillReference(id=bindings[0].option.id, name="Untrusted display snapshot"),
                SkillReference(id=bindings[1].option.id, name="Relay selected by user"),
                McpServerReference(id=server.id, name="Untrusted MCP snapshot"),
            ),
        )


@pytest.fixture
def wire(
    monkeypatch: pytest.MonkeyPatch,
    skill_payload: dict[str, Any],
    mcp_server: dict[str, Any],
) -> QueueWire:
    wire = QueueWire(skill_payload, mcp_server)
    monkeypatch.setattr("agent_relay.infrastructure.codex.driver.ProxyRpc", lambda *_: wire)
    return wire


def runtime() -> CodexDriver:
    return CodexDriver(["unused"], 1)


def test_native_inputs_resolve_current_bindings_and_include_relay_once(wire: QueueWire) -> None:
    assert runtime().enqueue("original", "client", wire.request()).id == "queued"
    assert [method for method, _ in wire.calls] == [
        "thread/read",
        "skills/list",
        "mcpServerStatus/list",
        "thread/queue/add",
    ]
    assert wire.calls[-1][1] == {
        "threadId": "original",
        "clientUserMessageId": "client",
        "input": [
            {"type": "text", "text": "Envelope text"},
            {
                "type": "skill",
                "name": "agent-relay:agent-relay",
                "path": "C:/plugins/agent-relay/SKILL.md",
            },
            {
                "type": "skill",
                "name": "example",
                "path": "D:/project/.agents/skills/example/SKILL.md",
            },
            {"type": "mention", "name": "plugin/local server", "path": "mcp://plugin/local server"},
        ],
    }


@pytest.mark.parametrize(
    "failure",
    ["missing", "disabled", "ambiguous", "relay", "mcp", "auth", "thread", "cwd", "unloaded"],
)
def test_failed_capability_preflight_never_submits(wire: QueueWire, failure: str) -> None:
    request = wire.request()
    if failure == "missing":
        wire.skills["data"][0]["skills"].pop(0)
    elif failure == "disabled":
        wire.skills["data"][0]["skills"][0]["enabled"] = False
    elif failure == "ambiguous":
        wire.skills["data"][0]["skills"].append(deepcopy(wire.skills["data"][0]["skills"][0]))
    elif failure == "relay":
        wire.skills["data"][0]["skills"].pop()
    elif failure == "mcp":
        wire.server["runtimeStatus"] = "failed"
    elif failure == "auth":
        wire.server["authStatus"] = "notLoggedIn"
    elif failure == "thread":
        wire.thread["id"] = "other"
    elif failure == "cwd":
        wire.thread["cwd"] = "D:/other"
    else:
        wire.thread["status"] = {"type": "notLoaded"}
    with pytest.raises(QueueRejected):
        runtime().enqueue("original", "client", request)
    assert "thread/queue/add" not in [method for method, _ in wire.calls]


@pytest.mark.parametrize("failure", ["timeout", "receipt", "rejected"])
def test_add_outcome_is_not_retried_or_reclassified_as_preflight_failure(
    wire: QueueWire, failure: str
) -> None:
    if failure == "timeout":
        wire.add_error = TimeoutError("Lost acknowledgement")
        error: type[Exception] = TimeoutError
    elif failure == "receipt":
        wire.bad_receipt = True
        error = RpcDisconnected
    else:
        wire.add_error = RpcRejected("Explicit rejection")
        error = QueueRejected
    with pytest.raises(error):
        runtime().enqueue("original", "client", wire.request())
    assert [method for method, _ in wire.calls].count("thread/queue/add") == 1


def test_each_target_rechecks_its_own_mcp_availability(wire: QueueWire) -> None:
    request = wire.request()
    runtime().enqueue("original", "first-client", request)
    wire.thread["id"] = "second"
    wire.server["runtimeStatus"] = "failed"
    with pytest.raises(QueueRejected):
        runtime().enqueue("second", "second-client", request)
    assert [
        params["threadId"] for method, params in wire.calls if method == "mcpServerStatus/list"
    ] == ["original", "second"]
    assert [method for method, _ in wire.calls].count("thread/queue/add") == 1
