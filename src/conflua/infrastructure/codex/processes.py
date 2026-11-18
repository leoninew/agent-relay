from __future__ import annotations

from collections.abc import Iterable
from time import monotonic
from uuid import UUID

try:
    import psutil
except ModuleNotFoundError:
    psutil = None  # type: ignore[assignment]

from conflua.domain.rooms.rules import normalize_workspace_identity

_VALUE_OPTIONS = {
    "-c",
    "--config",
    "-C",
    "--cd",
    "-m",
    "--model",
    "-p",
    "--profile",
    "-a",
    "--ask-for-approval",
    "-s",
    "--sandbox",
    "--remote",
    "--remote-auth-token-env",
    "--add-dir",
    "--enable",
    "--disable",
    "-i",
    "--image",
    "--local-provider",
    "--listen",
}


def resumed_session_id(arguments: Iterable[str]) -> str | None:
    positional: list[str] = []
    tokens = iter(arguments)
    next(tokens, None)
    for token in tokens:
        if token in {"-h", "--help", "-V", "--version"}:
            return None
        option, separator, _ = token.partition("=")
        if option in _VALUE_OPTIONS:
            if not separator:
                next(tokens, None)
        elif not token.startswith("-"):
            positional.append(token)

    if not positional or positional[0] != "resume" or len(positional) < 2:
        return None
    try:
        return str(UUID(positional[1]))
    except ValueError:
        return None


def resumed_session_ids_in_directory(
    processes: Iterable[tuple[str, list[str]]], working_path: str
) -> set[str]:
    expected_path = normalize_workspace_identity(working_path)
    return {
        session_id
        for process_path, arguments in processes
        if normalize_workspace_identity(process_path) == expected_path
        and (session_id := resumed_session_id(arguments)) is not None
    }


def running_session_ids(working_path: str, timeout: float = 2.0) -> set[str]:
    if psutil is None:
        return set()
    deadline = monotonic() + timeout
    processes: list[tuple[str, list[str]]] = []
    for process in psutil.process_iter(["name"]):
        if monotonic() >= deadline:
            break
        if (process.info["name"] or "").lower() not in {"codex", "codex.exe"}:
            continue
        try:
            processes.append((process.cwd(), process.cmdline()))
        except (psutil.AccessDenied, psutil.NoSuchProcess, OSError, ValueError):
            continue
    return resumed_session_ids_in_directory(processes, working_path)
