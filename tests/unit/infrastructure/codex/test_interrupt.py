from typing import Any
from unittest.mock import MagicMock, Mock, call

import pytest
from pytest import MonkeyPatch

from agent_relay.application.members.sessions import (
    SessionInterruptRejected,
    SessionUnavailableError,
)
from agent_relay.infrastructure.codex.driver import CodexDriver, ProxyRpc, RpcRejected


def metadata(status: str = "active", **changes: Any) -> dict[str, Any]:
    return {
        "thread": {
            "id": "thread",
            "cwd": "D:/project",
            "modelProvider": "codex",
            "status": {"type": status},
            **changes,
        }
    }


def turns(status: str, turn_id: str = "target") -> dict[str, Any]:
    return {"data": [{"id": turn_id, "status": status}]}


@pytest.fixture
def interrupt_rpc(monkeypatch: MonkeyPatch) -> Mock:
    rpc = MagicMock(spec=ProxyRpc)
    rpc.__enter__.return_value = rpc
    monkeypatch.setattr("agent_relay.infrastructure.codex.driver.ProxyRpc", lambda *_: rpc)
    return rpc


def test_interrupt_confirms_original_turn_even_when_another_turn_has_started(
    interrupt_rpc: Mock,
) -> None:
    interrupt_rpc.call.side_effect = [
        metadata(),
        turns("inProgress"),
        {},
        {
            "data": [
                {"id": "next", "status": "inProgress"},
                {"id": "target", "status": "interrupted"},
            ]
        },
    ]
    result = CodexDriver(["unused"], 1).interrupt("thread", "d:/project/")
    assert result.status == "interrupted" and result.turn_id == "target"
    assert interrupt_rpc.call.call_args_list == [
        call("thread/read", {"threadId": "thread", "includeTurns": False}),
        call(
            "thread/turns/list",
            {"threadId": "thread", "limit": 1, "sortDirection": "desc", "itemsView": "notLoaded"},
        ),
        call("turn/interrupt", {"threadId": "thread", "turnId": "target"}),
        call(
            "thread/turns/list",
            {"threadId": "thread", "limit": 20, "sortDirection": "desc", "itemsView": "notLoaded"},
        ),
    ]


def test_idle_session_never_sends_interrupt(interrupt_rpc: Mock) -> None:
    interrupt_rpc.call.return_value = metadata("idle")
    result = CodexDriver(["unused"], 1).interrupt("thread", "D:/project")
    assert result.status == "not_running" and result.turn_id is None
    assert interrupt_rpc.call.call_count == 1


@pytest.mark.parametrize(
    "thread",
    [metadata(id="other"), metadata(cwd="D:/other"), metadata("notLoaded")],
)
def test_identity_directory_and_connection_are_verified_before_interrupt(
    interrupt_rpc: Mock, thread: dict[str, Any]
) -> None:
    interrupt_rpc.call.return_value = thread
    with pytest.raises(SessionInterruptRejected):
        CodexDriver(["unused"], 1).interrupt("thread", "D:/project")
    assert interrupt_rpc.call.call_count == 1


def test_active_session_without_resolvable_turn_is_not_interrupted(interrupt_rpc: Mock) -> None:
    interrupt_rpc.call.side_effect = [metadata(), {"data": []}]
    with pytest.raises(SessionInterruptRejected) as caught:
        CodexDriver(["unused"], 1).interrupt("thread", "D:/project")
    assert caught.value.code == "session_interrupt_turn_unavailable"
    assert interrupt_rpc.call.call_count == 2


@pytest.mark.parametrize(
    ("code", "expected"),
    [(-32601, "session_interrupt_unsupported"), (-32600, "session_interrupt_rejected")],
)
def test_explicit_rejection_is_safe_and_never_retried(
    interrupt_rpc: Mock, code: int, expected: str
) -> None:
    interrupt_rpc.call.side_effect = [metadata(), turns("inProgress"), RpcRejected("private", code)]
    with pytest.raises(SessionInterruptRejected) as caught:
        CodexDriver(["unused"], 1).interrupt("thread", "D:/project")
    assert caught.value.code == expected
    assert "private" not in str(caught.value)
    assert interrupt_rpc.call.call_count == 3


@pytest.mark.parametrize("failed_at", ["metadata", "interrupt", "confirmation"])
def test_dependency_failure_preserves_whether_interrupt_was_attempted(
    interrupt_rpc: Mock, failed_at: str
) -> None:
    responses: list[object] = [] if failed_at == "metadata" else [metadata(), turns("inProgress")]
    if failed_at == "confirmation":
        responses.append({})
    responses.append(TimeoutError("private diagnostic"))
    interrupt_rpc.call.side_effect = responses
    with pytest.raises(SessionUnavailableError) as caught:
        CodexDriver(["unused"], 1).interrupt("thread", "D:/project")
    assert caught.value.code == (
        "session_metadata_unavailable" if failed_at == "metadata" else "session_interrupt_unknown"
    )
    assert "private" not in str(caught.value)
    assert sum(
        entry.args[0] == "turn/interrupt" for entry in interrupt_rpc.call.call_args_list
    ) == (failed_at != "metadata")


@pytest.mark.parametrize("status", ["completed", "failed"])
def test_naturally_finished_target_is_not_reported_as_interrupted(
    interrupt_rpc: Mock, status: str
) -> None:
    interrupt_rpc.call.side_effect = [metadata(), turns("inProgress"), {}, turns(status)]
    result = CodexDriver(["unused"], 1).interrupt("thread", "D:/project")
    assert result.status == "not_running" and result.turn_id == "target"


def test_synchronous_confirmation_waits_for_target_without_resending(
    interrupt_rpc: Mock, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr("agent_relay.infrastructure.codex.driver.sleep", lambda *_: None)
    interrupt_rpc.call.side_effect = [
        metadata(),
        turns("inProgress"),
        {},
        turns("inProgress"),
        turns("interrupted"),
    ]
    result = CodexDriver(["unused"], 1).interrupt("thread", "D:/project")
    assert result.status == "interrupted"
    assert (
        sum(entry.args[0] == "turn/interrupt" for entry in interrupt_rpc.call.call_args_list) == 1
    )


def test_missing_target_cannot_turn_an_acknowledgement_into_success(
    interrupt_rpc: Mock, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr("agent_relay.infrastructure.codex.driver.sleep", lambda *_: None)
    monkeypatch.setattr(
        "agent_relay.infrastructure.codex.driver.monotonic", Mock(side_effect=[0, 0.1, 0.2, 2])
    )
    interrupt_rpc.call.side_effect = [
        metadata(),
        turns("inProgress"),
        {},
        turns("interrupted", "other"),
    ]
    with pytest.raises(SessionUnavailableError) as caught:
        CodexDriver(["unused"], 1).interrupt("thread", "D:/project")
    assert caught.value.code == "session_interrupt_unknown"
