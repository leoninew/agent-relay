import json
from pathlib import Path

import pytest

from conflua.application.dto.delivery import QueueEntry
from conflua.application.dto.members import SessionInfo
from conflua.domain.rooms.rules import normalize_workspace_path
from conflua.infrastructure.codex import processes
from conflua.infrastructure.codex.driver import CodexDriver, RpcDisconnected, RpcRejected
from conflua.interfaces.cli import main


def test_codex_session_list_uses_current_directory_and_reports_daemon_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def list_sessions(driver: CodexDriver, working_path: str) -> list[SessionInfo]:
        assert driver.command == ["codex", "app-server", "proxy"]
        assert working_path == normalize_workspace_path(str(tmp_path))
        return [
            SessionInfo("01", "codex", "Idle", "idle"),
            SessionInfo("02", "codex", "Active", "active"),
            SessionInfo("03", "codex", "History", "unavailable", cwd=working_path),
            SessionInfo("04", "codex", "Archived", "unavailable", archived=True),
            SessionInfo("05", "codex", "Error", "error"),
            SessionInfo("06", "codex", "New Session", "idle"),
        ]

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CONFLUA_CHANNEL_ID", raising=False)
    monkeypatch.setenv("CONFLUA_URL", "invalid-http-address")
    monkeypatch.setattr(CodexDriver, "list_sessions", list_sessions)
    monkeypatch.setattr(processes, "running_session_ids", lambda _cwd: {"03"})

    assert main(["codex", "session", "list", "-o", "json"]) == 0
    output = capsys.readouterr()
    assert not output.err
    assert json.loads(output.out) == {
        "requestId": None,
        "data": [
            {"id": "06", "name": "New Session", "status": "idle", "daemonStatus": "idle"},
            {"id": "05", "name": "Error", "status": "error", "daemonStatus": "error"},
            {
                "id": "04",
                "name": "Archived",
                "status": "archived",
                "daemonStatus": "not_loaded",
            },
            {
                "id": "03",
                "name": "History",
                "status": "open",
                "daemonStatus": "not_loaded",
            },
            {"id": "02", "name": "Active", "status": "active", "daemonStatus": "active"},
            {"id": "01", "name": "Idle", "status": "idle", "daemonStatus": "idle"},
        ],
    }


def test_codex_session_list_defaults_to_text_for_the_specified_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    older_id = "01a1ec71-76c7-7770-a13c-89b8379bf6d1"
    newer_id = "01a1ec8f-5e4b-7db1-a81b-ad4de5dad3bb"

    def list_sessions(_driver: CodexDriver, working_path: str) -> list[SessionInfo]:
        assert working_path == normalize_workspace_path(str(tmp_path))
        return [
            SessionInfo(older_id, "codex", "Running", "active"),
            SessionInfo(newer_id, "codex", "Review", "unavailable"),
        ]

    monkeypatch.setattr(CodexDriver, "list_sessions", list_sessions)

    assert main(["codex", "session", "list", "--cwd", str(tmp_path)]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert [line.split() for line in lines] == [
        ["ID", "DAEMON", "STATUS", "NAME"],
        [newer_id, "not_loaded", "unknown", "Review"],
        [older_id, "active", "active", "Running"],
    ]

    assert main(["codex", "session", "list", "--cwd", str(tmp_path), "-o", "text"]) == 0
    assert capsys.readouterr().out.splitlines() == lines


def test_codex_session_list_only_marks_same_directory_process_as_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    session_id = "01234567-89ab-cdef-0123-456789abcdef"

    def list_sessions(_driver: CodexDriver, working_path: str) -> list[SessionInfo]:
        return [SessionInfo(session_id, "codex", "Review", "unavailable", cwd=working_path)]

    monkeypatch.setattr(CodexDriver, "list_sessions", list_sessions)
    monkeypatch.setattr(processes, "running_session_ids", lambda _cwd: {session_id})

    assert main(["codex", "session", "list", "--cwd", str(tmp_path), "-o", "json"]) == 0
    data = json.loads(capsys.readouterr().out)["data"]
    assert data == [
        {
            "id": session_id,
            "name": "Review",
            "status": "open",
            "daemonStatus": "not_loaded",
        }
    ]


def test_codex_session_list_uses_current_codex_thread_as_runtime_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    session_id = "01234567-89ab-cdef-0123-456789abcdef"

    def list_sessions(_driver: CodexDriver, working_path: str) -> list[SessionInfo]:
        return [SessionInfo(session_id, "codex", "Current", "unavailable", cwd=working_path)]

    monkeypatch.setattr(CodexDriver, "list_sessions", list_sessions)
    monkeypatch.setattr(processes, "running_session_ids", lambda _cwd: set())
    monkeypatch.setenv("CODEX_THREAD_ID", session_id)

    assert main(["codex", "session", "list", "--cwd", str(tmp_path), "-o", "json"]) == 0
    data = json.loads(capsys.readouterr().out)["data"]
    assert data[0]["status"] == "open"
    assert data[0]["daemonStatus"] == "not_loaded"


def test_codex_session_list_reports_daemon_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def list_sessions(_driver: CodexDriver, _working_path: str) -> list[SessionInfo]:
        raise RpcDisconnected("internal connection detail")

    monkeypatch.setattr(CodexDriver, "list_sessions", list_sessions)

    assert main(["codex", "session", "list"]) == 5
    output = capsys.readouterr()
    assert not output.out
    assert json.loads(output.err)["error"]["code"] == "codex_session_list_failed"
    assert "internal connection detail" not in output.err


def test_codex_session_get_reports_directory_model_and_runtime_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    session_id = "01a1ec8f-5e4b-7db1-a81b-ad4de5dad3bb"
    working_path = normalize_workspace_path(str(tmp_path))

    def inspect(_driver: CodexDriver, thread_id: str, *, check_archived: bool) -> SessionInfo:
        assert thread_id == session_id and check_archived
        return SessionInfo(
            thread_id, "codex", "Review", "unavailable", model="model", cwd=working_path
        )

    def running_sessions(cwd: str) -> set[str]:
        assert cwd == working_path
        return {session_id}

    monkeypatch.setattr(CodexDriver, "inspect", inspect)
    monkeypatch.setattr(processes, "running_session_ids", running_sessions)
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.setenv("CONFLUA_URL", "invalid-http-address")

    assert main(["codex", "session", "get", session_id, "--cwd", str(tmp_path), "-o", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["data"] == {
        "id": session_id,
        "name": "Review",
        "cwd": working_path,
        "daemonStatus": "not_loaded",
        "status": "open",
        "statusSource": "process",
        "modelProvider": "codex",
        "model": "model",
        "reasoningEffort": None,
    }


def test_codex_session_get_defaults_to_text(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    session_id = "01a1ec8f-5e4b-7db1-a81b-ad4de5dad3bb"
    monkeypatch.setattr(
        CodexDriver,
        "inspect",
        lambda _driver, thread_id, **_kwargs: SessionInfo(
            thread_id, "codex", "Review", "idle", model="model"
        ),
    )

    assert main(["codex", "session", "get", session_id]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == f"ID        {session_id}"
    assert "NAME      Review" in lines
    assert "STATUS    idle" in lines
    assert not lines[0].lstrip().startswith("{")


def test_codex_queue_list_keeps_unlinked_waiting_entries(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    session_id = "01a1ec8f-5e4b-7db1-a81b-ad4de5dad3bb"
    monkeypatch.setattr(
        CodexDriver,
        "inspect",
        lambda _driver, thread_id, **_kwargs: SessionInfo(thread_id, "codex", "Review", "idle"),
    )

    def list_entries(_driver: CodexDriver, thread_id: str) -> list[QueueEntry]:
        assert thread_id == session_id
        return [QueueEntry("first", None), QueueEntry("second", "client")]

    monkeypatch.setattr(CodexDriver, "list_queue_entries", list_entries)
    monkeypatch.setenv("CONFLUA_URL", "invalid-http-address")

    assert main(["codex", "queue", "list", session_id, "-o", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["data"] == {
        "sessionId": session_id,
        "items": [
            {"id": "first", "clientUserMessageId": None},
            {"id": "second", "clientUserMessageId": "client"},
        ],
    }


def test_codex_queue_list_defaults_to_text(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    session_id = "01a1ec8f-5e4b-7db1-a81b-ad4de5dad3bb"
    monkeypatch.setattr(
        CodexDriver,
        "inspect",
        lambda _driver, thread_id, **_kwargs: SessionInfo(thread_id, "codex", "Review", "idle"),
    )
    monkeypatch.setattr(
        CodexDriver,
        "list_queue_entries",
        lambda _driver, _thread_id: [QueueEntry("queued-id", "client-id")],
    )

    assert main(["codex", "queue", "list", session_id]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "QUEUED ID                             CLIENT USER MESSAGE ID",
        "queued-id                             client-id",
    ]


def test_codex_queue_list_rejects_a_different_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    session_id = "01a1ec8f-5e4b-7db1-a81b-ad4de5dad3bb"
    other_path = normalize_workspace_path(str(tmp_path / "other"))
    monkeypatch.setattr(
        CodexDriver,
        "inspect",
        lambda _driver, thread_id, **_kwargs: SessionInfo(
            thread_id, "codex", "Review", "idle", cwd=other_path
        ),
    )

    def unexpected_query(_driver: CodexDriver, _thread_id: str) -> list[QueueEntry]:
        pytest.fail("The queue must not be read when the directory does not match")

    monkeypatch.setattr(CodexDriver, "list_queue_entries", unexpected_query)

    assert main(["codex", "queue", "list", session_id, "--cwd", str(tmp_path)]) == 5
    output = capsys.readouterr()
    assert not output.out
    assert json.loads(output.err)["error"]["code"] == "codex_session_directory_mismatch"


def test_codex_queue_list_distinguishes_empty_queue_and_unsupported_protocol(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    session_id = "01a1ec8f-5e4b-7db1-a81b-ad4de5dad3bb"
    monkeypatch.setattr(
        CodexDriver,
        "inspect",
        lambda _driver, thread_id, **_kwargs: SessionInfo(thread_id, "codex", "Review", "idle"),
    )
    monkeypatch.setattr(CodexDriver, "list_queue_entries", lambda _driver, _thread_id: [])
    assert main(["codex", "queue", "list", session_id]) == 0
    assert capsys.readouterr().out.strip() == "暂无等待项"

    def unsupported_query(_driver: CodexDriver, _thread_id: str) -> list[QueueEntry]:
        raise RpcRejected("Method not found", -32601)

    monkeypatch.setattr(CodexDriver, "list_queue_entries", unsupported_query)
    assert main(["codex", "queue", "list", session_id]) == 5
    output = capsys.readouterr()
    assert not output.out
    assert json.loads(output.err)["error"]["code"] == "codex_queue_unsupported"
