import sys
from pathlib import Path

import pytest

from agent_relay.application.delivery.ports import QueueRejected
from agent_relay.infrastructure.codex.driver import (
    CodexDriver,
    ProxyRpc,
    RpcDisconnected,
    RpcRejected,
)


def driver(mode: str = "normal") -> CodexDriver:
    return CodexDriver(
        [sys.executable, str(Path(__file__).parents[2] / "support" / "codex_rpc_fixture.py"), mode],
        2,
    )


def test_metadata_queries_cover_all_pages_providers_sources_and_archives() -> None:
    sessions = driver().list_sessions()
    assert [info.id for info in sessions] == ["one", "two", "archived"]
    assert [info.name for info in sessions] == [
        "Worker one",
        "First message two",
        "Worker archived",
    ]
    assert sessions[0].presence == "busy"
    assert sessions[1].presence == "unknown"
    assert sessions[0].usable and not sessions[1].usable
    assert sessions[-1].archived is True
    info = driver().inspect("original-id")
    assert info.id == "original-id"
    assert info.cwd == "D:/project"
    assert info.name == "Worker original-id"


def test_queue_submits_to_original_thread_and_preserves_receipt() -> None:
    receipt = driver().enqueue("original-id", "stable-client-id", "hello from Relay")
    assert receipt.id == "queued-original"
    assert receipt.metadata == {"id": "queued-original", "clientUserMessageId": "stable-client-id"}


def test_queue_activation_and_input_receipt_use_original_identities() -> None:
    runtime = driver("delivery")
    head = runtime.activation_candidate("original-id")
    assert head is not None and head.client_message_id == "stable-client-id"
    assert runtime.activate("original-id", head.id) == "turn-original"
    page = runtime.read_input_page("original-id")
    assert page.next_cursor is None
    assert [(item.client_message_id, item.item_id, item.turn_id) for item in page.inputs] == [
        ("stable-client-id", "input-original", "turn-original")
    ]


def test_queue_delete_targets_exact_submission_in_original_thread() -> None:
    assert driver().delete("original-id", "queued-original") is True
    assert driver("missing").delete("original-id", "queued-original") is False
    with pytest.raises(QueueRejected):
        driver("reject").delete("original-id", "queued-original")
    with pytest.raises(RpcDisconnected):
        driver("malformed").delete("original-id", "queued-original")


@pytest.mark.parametrize(
    ("mode", "error"),
    [
        ("reject", RpcRejected),
        ("timeout", TimeoutError),
        ("cursor", RpcDisconnected),
        ("malformed", RpcDisconnected),
    ],
)
def test_read_errors_never_return_a_partial_list(mode: str, error: type[Exception]) -> None:
    with pytest.raises(error):
        driver(mode).list_sessions()


def test_proxy_scope_closes_its_child_and_bridge_threads() -> None:
    runtime = driver()
    with ProxyRpc(runtime.command, runtime.timeout) as rpc:
        assert rpc.call("thread/read", {"threadId": "one", "includeTurns": False})["thread"]
    assert rpc.process is not None and rpc.process.poll() is not None
    assert rpc.process.returncode == 0
    assert all(not thread.is_alive() for thread in rpc.bridges)
