from pathlib import Path

from conflua.infrastructure.codex.driver import CodexDriver
from conflua.infrastructure.codex.processes import (
    resumed_session_id,
    resumed_session_ids_in_directory,
)


def test_resumed_session_id_reads_codex_resume_command() -> None:
    assert (
        resumed_session_id(
            ["codex.exe", "--model", "gpt-5", "resume", "01234567-89ab-cdef-0123-456789abcdef"]
        )
        == "01234567-89ab-cdef-0123-456789abcdef"
    )


def test_resumed_session_id_ignores_non_resume_commands() -> None:
    assert resumed_session_id(["codex.exe", "app-server", "proxy"]) is None
    assert resumed_session_id(["codex.exe", "--yolo"]) is None
    assert resumed_session_id(["codex.exe", "resume", "latest"]) is None


def test_resumed_session_ids_require_resume_process_in_requested_directory(
    tmp_path: Path,
) -> None:
    session_id = "01234567-89ab-cdef-0123-456789abcdef"
    observations = [
        (str(tmp_path), ["codex.exe", "resume", session_id]),
        (str(tmp_path.parent), ["codex.exe", "resume", session_id]),
        (str(tmp_path), ["codex.exe", "app-server", "proxy"]),
        (str(tmp_path), ["node.exe", "resume", session_id]),
    ]

    assert resumed_session_ids_in_directory(observations, str(tmp_path)) == {session_id}


def test_session_metadata_preserves_working_directory() -> None:
    session = CodexDriver._session(
        {
            "id": "original-id",
            "modelProvider": "codex",
            "name": "Review",
            "cwd": "D:/SourceCodes/mywork/conflua",
            "status": {"type": "notLoaded"},
        }
    )

    assert session.cwd == "D:/SourceCodes/mywork/conflua"
