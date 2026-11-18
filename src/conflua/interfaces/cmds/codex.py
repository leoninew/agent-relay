from __future__ import annotations

import os
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

import click

from conflua.interfaces.client import ConfluaClientError
from conflua.interfaces.dto import ApiResult

if TYPE_CHECKING:
    from conflua.application.dto.members import SessionInfo
    from conflua.infrastructure.codex.driver import CodexDriver


@click.group("codex")
def codex_commands() -> None:
    """查询本机共享 Codex daemon。"""


@codex_commands.group("session")
def codex_session_commands() -> None:
    """Codex 会话。"""


def _codex_driver() -> CodexDriver:
    from conflua.infrastructure.codex.driver import CodexDriver

    return CodexDriver(["codex", "app-server", "proxy"], 30.0)


def _codex_session_directory_matches(session: SessionInfo, working_path: str) -> bool:
    from conflua.domain.rooms.rules import normalize_workspace_identity

    if session.cwd is not None:
        with suppress(ValueError):
            return normalize_workspace_identity(session.cwd) == normalize_workspace_identity(
                working_path
            )
    return False


def _codex_status(
    session: SessionInfo, working_path: str | None, live_session_ids: set[str]
) -> tuple[str, str, str | None]:
    daemon_status = "not_loaded" if session.status == "unavailable" else session.status
    if session.archived:
        return "archived", daemon_status, "archive_index"
    if session.status != "unavailable":
        return session.status, daemon_status, "daemon"
    if working_path is not None and _codex_session_directory_matches(session, working_path):
        if session.id == os.environ.get("CODEX_THREAD_ID"):
            return "open", daemon_status, "current_session"
        if session.id in live_session_ids:
            return "open", daemon_status, "process"
    return "unknown", daemon_status, None


def _codex_display(value: str | None) -> str:
    if value is None:
        return "-"
    return "".join(character if character.isprintable() else " " for character in value)


@codex_session_commands.command("list", help="列出指定目录的 Codex 会话及其状态")
@click.option(
    "--cwd",
    type=click.Path(exists=True, file_okay=False, resolve_path=True, path_type=Path),
    default=".",
    show_default=True,
    help="按完整目录匹配，不包含子目录",
)
@click.option(
    "-o", "--output", type=click.Choice(("text", "json")), default="text", show_default=True
)
def codex_session_list(cwd: Path, output: str) -> ApiResult | None:
    from websockets.exceptions import WebSocketException

    from conflua.domain.rooms.rules import normalize_workspace_path
    from conflua.infrastructure.codex.driver import RpcDisconnected, RpcRejected
    from conflua.infrastructure.codex.processes import running_session_ids

    try:
        working_path = normalize_workspace_path(str(cwd))
        sessions = _codex_driver().list_sessions(working_path)
    except (OSError, ValueError, RpcDisconnected, RpcRejected, WebSocketException) as exc:
        raise ConfluaClientError(
            5, "codex_session_list_failed", "无法查询本机共享 Codex daemon 的会话"
        ) from exc

    live_session_ids = running_session_ids(working_path)
    rows = []
    for session in sessions:
        runtime_status, daemon_status, _source = _codex_status(
            session, working_path, live_session_ids
        )
        rows.append(
            {
                "id": session.id,
                "name": session.name,
                "status": runtime_status,
                "daemonStatus": daemon_status,
            }
        )
    rows.sort(key=lambda row: row["id"], reverse=True)
    if output == "json":
        return ApiResult(rows, request_id=None)
    click.echo(f"{'ID':36}  {'DAEMON':10}  {'STATUS':10}  NAME")
    for row in rows:
        name = _codex_display(row["name"])
        click.echo(f"{row['id']:36}  {row['daemonStatus']:10}  {row['status']:10}  {name}")
    return None


def _read_codex_session(
    driver: CodexDriver, session_id: UUID, cwd: Path | None, *, check_archived: bool = False
) -> SessionInfo:
    from websockets.exceptions import WebSocketException

    from conflua.infrastructure.codex.driver import RpcDisconnected, RpcRejected

    try:
        session = driver.inspect(str(session_id), check_archived=check_archived)
    except (OSError, ValueError, RpcDisconnected, RpcRejected, WebSocketException) as exc:
        raise ConfluaClientError(
            5, "codex_session_get_failed", "无法查询指定的 Codex 会话"
        ) from exc
    if session.id != str(session_id):
        raise ConfluaClientError(5, "session_identity_mismatch", "Codex 返回的会话身份不匹配")
    if cwd is not None and not _codex_session_directory_matches(session, str(cwd)):
        raise ConfluaClientError(5, "codex_session_directory_mismatch", "无法确认会话属于指定目录")
    return session


@codex_session_commands.command("get", help="按完整 UUID 查看单个 Codex 会话及状态来源")
@click.argument("session_id", type=click.UUID)
@click.option(
    "--cwd",
    type=click.Path(exists=True, file_okay=False, resolve_path=True, path_type=Path),
    help="核对会话的完整目录",
)
@click.option(
    "-o", "--output", type=click.Choice(("text", "json")), default="text", show_default=True
)
def codex_session_get(session_id: UUID, cwd: Path | None, output: str) -> ApiResult | None:
    from conflua.domain.rooms.rules import normalize_workspace_path
    from conflua.infrastructure.codex.processes import running_session_ids

    session = _read_codex_session(_codex_driver(), session_id, cwd, check_archived=True)
    working_path = normalize_workspace_path(session.cwd) if session.cwd is not None else None
    status, daemon_status, source = _codex_status(session, working_path, set())
    if status == "unknown" and working_path is not None:
        status, daemon_status, source = _codex_status(
            session, working_path, running_session_ids(working_path)
        )
    data = {
        "id": session.id,
        "name": session.name,
        "cwd": session.cwd,
        "daemonStatus": daemon_status,
        "status": status,
        "statusSource": source,
        "modelProvider": session.provider,
        "model": session.model,
        "reasoningEffort": session.reasoning_effort,
    }
    if output == "json":
        return ApiResult(data, request_id=None)
    for label, value in zip(
        ("ID", "NAME", "CWD", "DAEMON", "STATUS", "SOURCE", "PROVIDER", "MODEL", "EFFORT"),
        data.values(),
        strict=True,
    ):
        click.echo(f"{label:8}  {_codex_display(value)}")
    return None


@codex_commands.group("queue")
def codex_queue_commands() -> None:
    """Codex daemon 等待队列，不是 Conflua 投递队列。"""


@codex_queue_commands.command("list", help="按完整会话 UUID 列出 Codex 等待项，不输出正文")
@click.argument("session_id", type=click.UUID)
@click.option(
    "--cwd",
    type=click.Path(exists=True, file_okay=False, resolve_path=True, path_type=Path),
    help="核对会话的完整目录",
)
@click.option(
    "-o", "--output", type=click.Choice(("text", "json")), default="text", show_default=True
)
def codex_queue_list(session_id: UUID, cwd: Path | None, output: str) -> ApiResult | None:
    from websockets.exceptions import WebSocketException

    from conflua.infrastructure.codex.driver import RpcDisconnected, RpcRejected

    driver = _codex_driver()
    session = _read_codex_session(driver, session_id, cwd)
    try:
        entries = driver.list_queue_entries(session.id)
    except (OSError, ValueError, RpcDisconnected, RpcRejected, WebSocketException) as exc:
        if isinstance(exc, RpcRejected) and exc.code == -32601:
            raise ConfluaClientError(
                5, "codex_queue_unsupported", "当前 Codex daemon 不支持查询等待队列"
            ) from exc
        raise ConfluaClientError(5, "codex_queue_list_failed", "无法查询 Codex 等待队列") from exc

    if output == "json":
        return ApiResult(
            {
                "sessionId": session.id,
                "items": [
                    {"id": entry.id, "clientUserMessageId": entry.client_message_id}
                    for entry in entries
                ],
            },
            request_id=None,
        )
    if not entries:
        click.echo("暂无等待项")
        return None
    click.echo(f"{'QUEUED ID':36}  CLIENT USER MESSAGE ID")
    for entry in entries:
        click.echo(f"{_codex_display(entry.id):36}  {_codex_display(entry.client_message_id)}")
    return None
