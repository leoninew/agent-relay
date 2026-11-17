import json
from pathlib import Path
from unittest.mock import MagicMock, Mock, call

import pytest
from pytest import MonkeyPatch

from conflua.application.delivery.ports import InputHistoryUnavailable
from conflua.application.dto.delivery import InputPage, ReceivedInput
from conflua.infrastructure.codex.driver import (
    CodexDriver,
    ProxyRpc,
    RpcDisconnected,
    RpcRejected,
    _launch_command,
)


@pytest.mark.parametrize("suffix", [".cmd", ".ps1"])
@pytest.mark.parametrize("local_node", [True, False])
def test_npm_codex_uses_node_without_shell_and_preserves_arguments(
    tmp_path: Path, monkeypatch: MonkeyPatch, suffix: str, local_node: bool
) -> None:
    prefix = tmp_path / "Node installation & spaces"
    entry = prefix / "node_modules" / "@openai" / "codex" / "bin" / "codex.js"
    entry.parent.mkdir(parents=True)
    entry.touch()
    shim = prefix / ("codex" + suffix)
    shim.write_text("must never be interpreted as a shell script", encoding="utf-8")
    node = prefix / "node.exe" if local_node else tmp_path / "Node runtime" / "node.exe"
    node.parent.mkdir(parents=True, exist_ok=True)
    node.touch()
    paths = {"codex": str(shim), "node": str(node)}
    monkeypatch.setattr("conflua.infrastructure.codex.driver.shutil.which", paths.get)
    command = ["codex", "app-server", "proxy", "argument with spaces", "&literal"]
    assert _launch_command(command) == [str(node), str(entry), *command[1:]]
    assert command[0] == "codex"


@pytest.mark.parametrize(
    "command",
    [["codex.exe", "app-server", "proxy"], ["node.exe", "Codex entry.js", "app-server", "proxy"]],
)
def test_native_and_explicit_node_commands_keep_their_arguments(
    tmp_path: Path, monkeypatch: MonkeyPatch, command: list[str]
) -> None:
    executable = tmp_path / command[0]
    monkeypatch.setattr(
        "conflua.infrastructure.codex.driver.shutil.which", lambda _: str(executable)
    )
    assert _launch_command(command) == [str(executable), *command[1:]]


def test_relative_native_path_keeps_its_directory_prefix(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("conflua.infrastructure.codex.driver.shutil.which", lambda _: None)
    command = ["./codex", "app-server", "proxy"]
    assert _launch_command(command) == command


@pytest.mark.parametrize("missing", ["entry", "node"])
def test_incomplete_npm_install_fails_without_another_codex_fallback(
    tmp_path: Path, monkeypatch: MonkeyPatch, missing: str
) -> None:
    shim = tmp_path / "codex.cmd"
    if missing == "node":
        entry = tmp_path / "node_modules" / "@openai" / "codex" / "bin" / "codex.js"
        entry.parent.mkdir(parents=True)
        entry.touch()
    paths = {"codex": str(shim)}
    monkeypatch.setattr("conflua.infrastructure.codex.driver.shutil.which", paths.get)
    with pytest.raises(FileNotFoundError, match="entry point"):
        _launch_command(["codex", "app-server", "proxy"])


def test_arbitrary_shell_wrapper_is_not_executed(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("conflua.infrastructure.codex.driver.shutil.which", lambda _: "custom.cmd")
    with pytest.raises(OSError, match="official npm Codex shim"):
        _launch_command(["codex", "app-server", "proxy"])


@pytest.mark.parametrize(
    ("name", "preview", "expected"),
    [
        ("会话名称", "首条消息", "会话名称"),
        (None, "  首条消息\n的预览  ", "首条消息 的预览"),
        ("  ", "首条消息", "首条消息"),
        ("", "", "未命名会话"),
        (None, None, "未命名会话"),
    ],
)
def test_session_display_name_uses_preview_before_an_unnamed_label(
    name: str | None, preview: str | None, expected: str
) -> None:
    info = CodexDriver._session(
        {
            "id": "original-id",
            "modelProvider": "test-provider",
            "status": {"type": "idle"},
            "name": name,
            "preview": preview,
        }
    )
    assert info.name == expected
    assert info.id == "original-id"


def test_rpc_rejection_retains_code_and_data_for_safe_fallback_classification() -> None:
    socket = Mock()
    socket.recv.return_value = json.dumps(
        {"id": 1, "error": {"code": -32600, "message": "Invalid turn", "data": {"reason": "ended"}}}
    )
    rpc = ProxyRpc(["unused"], 1)
    rpc.ws = socket
    with pytest.raises(RpcRejected) as raised:
        rpc.call("turn/steer", {})
    assert raised.value.code == -32600
    assert raised.value.data == {"reason": "ended"}


@pytest.mark.parametrize(
    "error", ["invalid", {"message": "Missing code"}, {"code": True, "message": "Bad code"}]
)
def test_malformed_rpc_error_is_uncertain_instead_of_an_explicit_rejection(error: object) -> None:
    socket = Mock()
    socket.recv.return_value = json.dumps({"id": 1, "error": error})
    rpc = ProxyRpc(["unused"], 1)
    rpc.ws = socket
    with pytest.raises(RpcDisconnected):
        rpc.call("turn/steer", {})


@pytest.fixture
def history_rpc(monkeypatch: MonkeyPatch) -> Mock:
    rpc = MagicMock(spec=ProxyRpc)
    rpc.__enter__.return_value = rpc
    monkeypatch.setattr("conflua.infrastructure.codex.driver.ProxyRpc", lambda *_: rpc)
    return rpc


@pytest.mark.parametrize("working_path", [None, "D:/Work/project"])
def test_session_discovery_keeps_directory_filter_across_pages_and_loaded_refresh(
    history_rpc: Mock, working_path: str | None
) -> None:
    active = {
        "id": "active",
        "modelProvider": "codex",
        "name": "Active",
        "status": {"type": "idle"},
    }
    archived = {**active, "id": "archived"}
    other = {**active, "id": "other"}
    history_rpc.call.side_effect = [
        {"data": [active], "nextCursor": "active-page"},
        {"data": [{**active, "id": "not-loaded"}]},
        {"data": [], "nextCursor": "archived-page"},
        {"data": [archived]},
        {"data": ["active", "other"], "nextCursor": "loaded-page"},
        {"data": ["archived"]},
        {"thread": {**active, "name": "Refreshed", "status": {"type": "active"}}},
        {"thread": archived},
        {"thread": other},
    ]

    sessions = CodexDriver(["unused"], 1).list_sessions(working_path)

    expected = {
        "active": ("active", False),
        "not-loaded": ("unavailable", False),
        "archived": ("idle", True),
    }
    if working_path is None:
        expected["other"] = ("idle", False)
    assert {info.id: (info.status, info.archived) for info in sessions} == expected
    assert sessions[0].name == "Refreshed"
    list_requests = [
        request.args[1]
        for request in history_rpc.call.call_args_list
        if request.args[0] == "thread/list"
    ]
    assert [(params["archived"], params["cursor"], params["cwd"]) for params in list_requests] == [
        (False, None, working_path),
        (False, "active-page", working_path),
        (True, None, working_path),
        (True, "archived-page", working_path),
    ]
    read_ids = [
        request.args[1]["threadId"]
        for request in history_rpc.call.call_args_list
        if request.args[0] == "thread/read"
    ]
    expected_read_ids = ["active", "archived"]
    if working_path is None:
        expected_read_ids.append("other")
    assert read_ids == expected_read_ids


def test_input_history_only_returns_correlatable_user_messages(history_rpc: Mock) -> None:
    history_rpc.call.return_value = {
        "data": [
            {"turnId": "turn", "item": {"type": "userMessage", "clientId": "client", "id": "item"}},
            {"turnId": "turn", "item": {"type": "userMessage", "id": "unrelated"}},
            {"turnId": "turn", "item": {"type": "agentMessage", "id": "reply"}},
        ],
        "nextCursor": "older",
    }
    page = CodexDriver(["unused"], 1).read_input_page("original")
    assert page == InputPage((ReceivedInput("client", "item", "turn"),), "items:older")
    history_rpc.call.assert_called_once_with(
        "thread/items/list",
        {"threadId": "original", "cursor": None, "limit": 100, "sortDirection": "desc"},
    )


def test_queue_page_preserves_exact_identity_and_excludes_input_content(history_rpc: Mock) -> None:
    history_rpc.call.return_value = {
        "data": [{"id": "queued", "clientUserMessageId": "client", "input": [{"type": "text"}]}],
        "nextCursor": "older",
    }
    page = CodexDriver(["unused"], 1).read_queue_page("original", "previous")
    assert page.next_cursor == "older" and len(page.inputs) == 1
    assert page.inputs[0].client_message_id == "client"
    assert page.inputs[0].receipt.metadata == {"id": "queued", "clientUserMessageId": "client"}
    history_rpc.call.assert_called_once_with(
        "thread/queue/list", {"threadId": "original", "cursor": "previous", "limit": 100}
    )


@pytest.mark.parametrize("row", [{"id": ""}, {"id": "q", "clientUserMessageId": 123}])
def test_malformed_queue_evidence_cannot_confirm_original_input(
    history_rpc: Mock, row: object
) -> None:
    history_rpc.call.return_value = {"data": [row]}
    with pytest.raises(RpcDisconnected):
        CodexDriver(["unused"], 1).read_queue_page("original")


def test_unsupported_items_history_falls_back_to_full_turn_pages(history_rpc: Mock) -> None:
    history_rpc.call.side_effect = [
        RpcRejected("thread/items/list is not supported yet", -32601),
        {
            "data": [
                {
                    "id": "turn",
                    "items": [
                        {"type": "userMessage", "clientId": "client", "id": "item"},
                        {"type": "userMessage", "id": "unrelated"},
                        {"type": "agentMessage", "id": "reply"},
                    ],
                }
            ],
            "nextCursor": "older",
        },
    ]
    page = CodexDriver(["unused"], 1).read_input_page("original", "items:previous")
    assert page == InputPage((ReceivedInput("client", "item", "turn"),), "turns:older")
    history_rpc.call.assert_has_calls(
        [
            call(
                "thread/items/list",
                {
                    "threadId": "original",
                    "cursor": "previous",
                    "limit": 100,
                    "sortDirection": "desc",
                },
            ),
            call(
                "thread/turns/list",
                {
                    "threadId": "original",
                    "cursor": None,
                    "limit": 100,
                    "sortDirection": "desc",
                    "itemsView": "full",
                },
            ),
        ]
    )


@pytest.mark.parametrize("source", ["items", "turns"])
def test_input_history_cursor_continues_with_its_original_method(
    history_rpc: Mock, source: str
) -> None:
    history_rpc.call.return_value = {"data": [], "nextCursor": None}
    assert CodexDriver(["unused"], 1).read_input_page("original", f"{source}:older") == InputPage(
        (), None
    )
    params = {"threadId": "original", "cursor": "older", "limit": 100, "sortDirection": "desc"}
    history_rpc.call.assert_called_once_with(
        f"thread/{source}/list", {**params, "itemsView": "full"} if source == "turns" else params
    )


@pytest.mark.parametrize(
    "error",
    [
        TimeoutError("Lost response"),
        RpcDisconnected("Disconnected"),
        RpcRejected("Invalid request", -32600),
        RpcRejected("Invalid parameters", -32602),
        RpcRejected("Internal error", -32603),
        RpcRejected("thread not loaded: another", -32600),
    ],
)
def test_other_history_failures_are_not_hidden_or_read_using_another_method(
    history_rpc: Mock, error: Exception
) -> None:
    history_rpc.call.side_effect = error
    with pytest.raises(type(error)) as raised:
        CodexDriver(["unused"], 1).read_input_page("original")
    assert raised.value is error
    history_rpc.call.assert_called_once()


@pytest.mark.parametrize(
    "error",
    [
        RpcRejected("thread/turns/list is not supported yet", -32601),
        RpcRejected("thread not loaded: original", -32600),
    ],
)
def test_unavailable_input_history_has_a_typed_outcome(
    history_rpc: Mock, error: RpcRejected
) -> None:
    history_rpc.call.side_effect = [RpcRejected("Not supported yet", -32601), error]
    with pytest.raises(InputHistoryUnavailable):
        CodexDriver(["unused"], 1).read_input_page("original")
    assert [entry.args[0] for entry in history_rpc.call.call_args_list] == [
        "thread/items/list",
        "thread/turns/list",
    ]


@pytest.mark.parametrize("source", ["items", "turns"])
@pytest.mark.parametrize("failure", ["page", "row", "identity", "cursor"])
def test_invalid_history_is_not_accepted_as_receipt_evidence(
    history_rpc: Mock, source: str, failure: str
) -> None:
    item = {"type": "userMessage", "clientId": "client", "id": "item"}
    row: object = (
        {"turnId": "turn", "item": item} if source == "items" else {"id": "turn", "items": [item]}
    )
    if failure == "identity":
        item.pop("id")
    if failure == "row":
        row = {"turnId": "turn", "item": None} if source == "items" else {"id": "turn"}
    history_rpc.call.return_value = {
        "data": None if failure == "page" else [row],
        "nextCursor": "" if failure == "cursor" else None,
    }
    with pytest.raises(RpcDisconnected):
        CodexDriver(["unused"], 1).read_input_page("original", f"{source}:older")


@pytest.mark.parametrize("cursor", ["untagged", "unknown:older", "turns:"])
def test_invalid_history_cursor_is_never_forwarded(history_rpc: Mock, cursor: str) -> None:
    with pytest.raises(RpcDisconnected, match="cursor"):
        CodexDriver(["unused"], 1).read_input_page("original", cursor)
    history_rpc.call.assert_not_called()
