import sys
from pathlib import Path

import pytest
from pytest import MonkeyPatch

from agent_relay.drivers.codex import (
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
    monkeypatch.setattr("agent_relay.drivers.codex.shutil.which", paths.get)
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
    monkeypatch.setattr("agent_relay.drivers.codex.shutil.which", lambda _: str(executable))
    assert _launch_command(command) == [str(executable), *command[1:]]


def test_relative_native_path_keeps_its_directory_prefix(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("agent_relay.drivers.codex.shutil.which", lambda _: None)
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
    monkeypatch.setattr("agent_relay.drivers.codex.shutil.which", paths.get)
    with pytest.raises(FileNotFoundError, match="entry point"):
        _launch_command(["codex", "app-server", "proxy"])


def test_arbitrary_shell_wrapper_is_not_executed(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("agent_relay.drivers.codex.shutil.which", lambda _: "custom.cmd")
    with pytest.raises(OSError, match="official npm Codex shim"):
        _launch_command(["codex", "app-server", "proxy"])


def driver(mode: str = "normal") -> CodexDriver:
    return CodexDriver(
        [sys.executable, str(Path(__file__).with_name("codex_rpc_fixture.py")), mode], 2
    )


def test_metadata_queries_cover_all_pages_providers_sources_and_archives() -> None:
    sessions = driver().list_sessions()
    assert [info.id for info in sessions] == ["one", "two", "archived"]
    assert sessions[0].presence == "busy"
    assert sessions[1].presence == "offline"
    assert sessions[-1].archived is True
    info = driver().inspect("original-id")
    assert info.id == "original-id"
    assert info.cwd == "D:/project"
    assert info.name == "Worker original-id"


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
