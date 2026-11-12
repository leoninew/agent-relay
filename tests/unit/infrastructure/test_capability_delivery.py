from copy import deepcopy
from typing import Any, Self

import pytest

from agent_relay.application.delivery.ports import (
    QueueRejected,
    SubmissionRejected,
    SubmissionUnknown,
)
from agent_relay.application.dto.delivery import QueueReceipt, QueueRequest, SteerReceipt
from agent_relay.domain.rooms.models import McpServerReference, SkillReference
from agent_relay.infrastructure.codex.catalog import decode_skills, server_option
from agent_relay.infrastructure.codex.driver import CodexDriver, RpcDisconnected, RpcRejected
from agent_relay.infrastructure.codex.models import McpPage


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
        self.turns: list[dict[str, Any]] = [{"id": "active-turn", "status": "inProgress"}]
        self.turn_error: Exception | None = None
        self.steer_error: Exception | None = None
        self.steer_reply: dict[str, Any] = {"turnId": "active-turn"}
        self.after_steer_status: str | None = None
        self.after_steer_turn: str | None = None
        self.recheck_error = False
        self.steer_attempted = False

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        pass

    def call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((method, params))
        if method == "thread/read":
            if self.steer_attempted and self.recheck_error:
                raise TimeoutError("Recheck unavailable")
            return {"thread": self.thread}
        if method == "thread/turns/list":
            assert params == {
                "threadId": self.thread["id"],
                "limit": 1,
                "sortDirection": "desc",
                "itemsView": "notLoaded",
            }
            if self.turn_error:
                raise self.turn_error
            return {"data": self.turns}
        if method == "turn/steer":
            self.steer_attempted = True
            if self.after_steer_status:
                self.thread["status"] = {"type": self.after_steer_status}
            if self.after_steer_turn:
                self.turns = [{"id": self.after_steer_turn, "status": "inProgress"}]
            if self.steer_error:
                raise self.steer_error
            return self.steer_reply
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


def test_busy_submission_steers_original_turn_with_client_identity_and_native_inputs(
    wire: QueueWire,
) -> None:
    wire.thread["status"] = {"type": "active", "activeFlags": ["waitingOnApproval"]}
    result = runtime().submit("original", "client", wire.request())
    assert result == SteerReceipt("active-turn")
    method, params = wire.calls[-1]
    assert method == "turn/steer"
    assert params["threadId"] == "original" and params["clientUserMessageId"] == "client"
    assert params["expectedTurnId"] == "active-turn"
    assert [item["type"] for item in params["input"]] == ["text", "skill", "skill", "mention"]
    assert params["input"][1]["name"] == "agent-relay:agent-relay"
    assert params["input"][-1]["path"] == "mcp://plugin/local server"
    assert [method for method, _ in wire.calls].count("skills/list") == 1
    assert not any(
        method in {"thread/queue/add", "thread/queue/start", "turn/start"}
        for method, _ in wire.calls
    )


@pytest.mark.parametrize(
    "fallback", ["idle", "no-turn", "turn-api", "steer-api", "ended", "changed"]
)
def test_only_known_unaccepted_or_unattempted_steering_can_fall_back_to_queue(
    wire: QueueWire, fallback: str
) -> None:
    wire.thread["status"] = {"type": "active"}
    if fallback == "idle":
        wire.thread["status"] = {"type": "idle"}
    elif fallback == "no-turn":
        wire.turns = []
    elif fallback == "turn-api":
        wire.turn_error = RpcRejected("Method not found", -32601)
    elif fallback == "steer-api":
        wire.steer_error = RpcRejected("Method not found", -32601)
    else:
        wire.steer_error = RpcRejected("Turn no longer matches", -32600)
        if fallback == "ended":
            wire.after_steer_status = "idle"
        else:
            wire.after_steer_turn = "next-turn"
    result = runtime().submit("original", "client", wire.request())
    assert isinstance(result, QueueReceipt)
    assert result.id == "queued"
    assert (result.note is not None) == (fallback != "idle")
    writes = [
        (method, params)
        for method, params in wire.calls
        if method in {"turn/steer", "thread/queue/add"}
    ]
    assert [method for method, _ in writes].count("thread/queue/add") == 1
    assert [method for method, _ in writes].count("turn/steer") <= 1
    assert all(params["clientUserMessageId"] == "client" for _, params in writes)
    if len(writes) == 2:
        assert writes[0][1]["input"] == writes[1][1]["input"]


@pytest.mark.parametrize(
    "failure",
    ["timeout", "disconnect", "bad-receipt", "internal", "unchanged", "recheck", "unavailable"],
)
def test_steering_failure_never_blindly_adds_another_input(wire: QueueWire, failure: str) -> None:
    wire.thread["status"] = {"type": "active"}
    expected: type[Exception] = SubmissionUnknown
    if failure == "timeout":
        wire.steer_error = TimeoutError("Lost acknowledgement")
    elif failure == "disconnect":
        wire.steer_error = RpcDisconnected("Disconnected")
    elif failure == "bad-receipt":
        wire.steer_reply = {"turnId": "another-turn"}
    elif failure == "internal":
        wire.steer_error = RpcRejected("Internal failure", -32603)
    else:
        wire.steer_error = RpcRejected("Invalid steer request", -32602)
        expected = SubmissionRejected
        if failure == "recheck":
            wire.recheck_error = True
        elif failure == "unavailable":
            wire.after_steer_status = "notLoaded"
    with pytest.raises(expected) as raised:
        runtime().submit("original", "client", wire.request())
    assert isinstance(raised.value, (SubmissionRejected, SubmissionUnknown))
    assert raised.value.method == "steer"
    assert [method for method, _ in wire.calls].count("turn/steer") == 1
    assert not any(method.startswith("thread/queue/") for method, _ in wire.calls)


@pytest.mark.parametrize("rejected", [False, True])
def test_queue_failure_after_steer_fallback_is_not_sent_again(
    wire: QueueWire, rejected: bool
) -> None:
    wire.thread["status"] = {"type": "active"}
    wire.steer_error = RpcRejected("Method not found", -32601)
    wire.add_error = RpcRejected("Rejected") if rejected else TimeoutError("Unknown")
    with pytest.raises(SubmissionRejected if rejected else SubmissionUnknown) as raised:
        runtime().submit("original", "client", wire.request())
    assert isinstance(raised.value, (SubmissionRejected, SubmissionUnknown))
    assert raised.value.method == "queue"
    assert [method for method, _ in wire.calls].count("turn/steer") == 1
    assert [method for method, _ in wire.calls].count("thread/queue/add") == 1


def test_submit_preflight_failure_is_definite_and_has_no_input_write(wire: QueueWire) -> None:
    request = wire.request()
    wire.server["runtimeStatus"] = "failed"
    with pytest.raises(SubmissionRejected) as raised:
        runtime().submit("original", "client", request)
    assert raised.value.method is None
    assert not any(method in {"turn/steer", "thread/queue/add"} for method, _ in wire.calls)
