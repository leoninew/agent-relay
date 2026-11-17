from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
from contextlib import ExitStack, suppress
from dataclasses import replace
from pathlib import Path
from threading import Thread
from time import monotonic, sleep
from typing import Any, cast

from websockets.exceptions import ConnectionClosed
from websockets.sync.client import ClientConnection, connect

from conflua.application.delivery.ports import (
    ActivationRejected,
    InputHistoryUnavailable,
    QueueRejected,
    SubmissionDeferred,
    SubmissionRejected,
    SubmissionUnknown,
)
from conflua.application.dto.capabilities import McpCatalog, SkillCatalog
from conflua.application.dto.delivery import (
    InputPage,
    QueuedInput,
    QueueHead,
    QueuePage,
    QueueReceipt,
    QueueRequest,
    ReceivedInput,
    SteerReceipt,
)
from conflua.application.dto.members import MemberInterruptResult, SessionInfo, SessionStatus
from conflua.application.dto.session_models import SessionModelCatalog, UpdateSessionModel
from conflua.application.members.sessions import (
    SessionInterruptRejected,
    SessionModelRejected,
    SessionUnavailableError,
)
from conflua.domain.rooms.models import SubmissionMethod
from conflua.infrastructure.codex.catalog import decode_skills, server_option
from conflua.infrastructure.codex.models import McpPage, SkillBinding, SkillDiscovery
from conflua.infrastructure.codex.session_models import public_catalog, read_models

SOURCE_KINDS = [
    "cli",
    "vscode",
    "exec",
    "appServer",
    "subAgent",
    "subAgentReview",
    "subAgentCompact",
    "subAgentThreadSpawn",
    "subAgentOther",
    "unknown",
]


class RpcRejected(RuntimeError):
    """The server returned an explicit JSON-RPC error response."""

    def __init__(self, message: str, code: int | None = None, data: object = None) -> None:
        super().__init__(message)
        self.code = code
        self.data = data


class RpcDisconnected(RuntimeError):
    pass


class TargetSessionUnavailable(QueueRejected):
    pass


class ProxyConfigurationError(OSError):
    pass


def _launch_command(command: list[str]) -> list[str]:
    executable = shutil.which(command[0]) or command[0]
    path = Path(executable)
    if path.suffix.lower() not in {".cmd", ".bat", ".ps1"}:
        return [executable, *command[1:]]

    # npm's Windows shims aren't executable by CreateProcess. Start the official
    # package entry with Node, preserving argv without interpreting a shell script.
    if path.stem.lower() != "codex" or path.suffix.lower() == ".bat":
        raise ProxyConfigurationError(
            "Expected a native Codex executable, Node entry or official npm Codex shim"
        )
    entry = path.parent / "node_modules" / "@openai" / "codex" / "bin" / "codex.js"
    if not entry.is_file():
        raise FileNotFoundError(f"Codex npm entry point not found: {entry}")
    node = path.parent / "node.exe"
    if not node.is_file():
        found = shutil.which("node")
        if found is None or Path(found).suffix.lower() in {".cmd", ".bat", ".ps1"}:
            raise FileNotFoundError("Node executable not found for the Codex npm entry point")
        node = Path(found)
    return [str(node), str(entry), *command[1:]]


class ProxyRpc:
    """A short-lived connection to the shared daemon, never its execution host."""

    def __init__(self, command: list[str], timeout: float) -> None:
        self.command = command
        self.timeout = timeout
        self.process: subprocess.Popen[bytes] | None = None
        self.ws: ClientConnection | None = None
        self.sockets: list[socket.socket] = []
        self.bridges: list[Thread] = []
        self._counter = 0
        self._connections = ExitStack()

    def __enter__(self) -> ProxyRpc:
        try:
            process = subprocess.Popen(
                _launch_command(self.command),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            self.process = process
            local, bridge = socket.socketpair()
            self.sockets = [local, bridge]

            def to_proxy() -> None:
                assert process.stdin is not None
                try:
                    while data := bridge.recv(65536):
                        process.stdin.write(data)
                        process.stdin.flush()
                except OSError:
                    pass
                finally:
                    with suppress(OSError):
                        process.stdin.close()

            def from_proxy() -> None:
                assert process.stdout is not None
                try:
                    while data := os.read(process.stdout.fileno(), 65536):
                        bridge.sendall(data)
                except OSError:
                    pass
                finally:
                    with suppress(OSError):
                        bridge.shutdown(socket.SHUT_WR)

            self.bridges = [
                Thread(target=to_proxy, name="conflua-proxy-write", daemon=True),
                Thread(target=from_proxy, name="conflua-proxy-read", daemon=True),
            ]
            for thread in self.bridges:
                thread.start()
            # The public proxy carries WebSocket frames over stdin/stdout, not JSONL.
            self.ws = self._connections.enter_context(
                connect(
                    "ws://localhost/",
                    sock=local,
                    proxy=None,
                    open_timeout=self.timeout,
                    close_timeout=1,
                    max_size=None,
                )
            )
            self.call(
                "initialize",
                {
                    "clientInfo": {"name": "conflua", "version": "0.1.0"},
                    "capabilities": {"experimentalApi": True},
                },
            )
            self.ws.send(json.dumps({"method": "initialized", "params": {}}))
            return self
        except BaseException:
            self.close()
            raise

    def call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if self.ws is None:
            raise RpcDisconnected("Codex proxy is not connected")
        self._counter += 1
        request_id = self._counter
        self.ws.send(json.dumps({"id": request_id, "method": method, "params": params}))
        deadline = monotonic() + self.timeout
        while (remaining := deadline - monotonic()) > 0:
            message = json.loads(self.ws.recv(timeout=remaining))
            if not isinstance(message, dict):
                raise RpcDisconnected("Invalid Codex RPC response")
            if "method" in message:
                if "id" in message:
                    self.ws.send(
                        json.dumps(
                            {
                                "id": message["id"],
                                "error": {
                                    "code": -32601,
                                    "message": "This metadata client has no request handler.",
                                },
                            }
                        )
                    )
                continue
            if message.get("id") != request_id:
                raise RpcDisconnected("Unexpected Codex RPC response ID")
            if "error" in message:
                error = message["error"]
                if (
                    not isinstance(error, dict)
                    or type(error.get("code")) is not int
                    or not isinstance(error.get("message"), str)
                ):
                    raise RpcDisconnected("Invalid Codex RPC error")
                raise RpcRejected(error["message"], error["code"], error.get("data"))
            if not isinstance(message.get("result"), dict):
                raise RpcDisconnected("Invalid Codex RPC result")
            return cast(dict[str, Any], message["result"])
        raise TimeoutError(method)

    def close(self) -> None:
        with suppress(Exception):
            self._connections.close()
        for stream in self.sockets:
            with suppress(OSError):
                stream.shutdown(socket.SHUT_RDWR)
            stream.close()
        if self.process is not None:
            # Let the proxy and its Node launcher exit after WebSocket close.
            # Never terminate the shared daemon or user execution hosts.
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                try:
                    self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=3)
            for thread in self.bridges:
                thread.join(timeout=3)
            for pipe in (self.process.stdin, self.process.stdout):
                if pipe is not None:
                    pipe.close()

    def __exit__(self, *args: object) -> None:
        self.close()


class CodexDriver:
    def __init__(self, command: list[str], timeout: float) -> None:
        self.command = command
        self.timeout = timeout

    @staticmethod
    def _session(thread: Any, *, archived: bool = False) -> SessionInfo:
        if not isinstance(thread, dict):
            raise RpcDisconnected("Missing Codex thread metadata")
        values = [thread.get(key) for key in ("id", "modelProvider")]
        if any(not isinstance(value, str) or not value for value in values):
            raise RpcDisconnected("Incomplete Codex session identity")
        status = thread.get("status", {}).get("type")
        if status not in {"notLoaded", "idle", "active", "systemError"}:
            raise RpcDisconnected("Invalid Codex thread status")
        name = thread.get("name")
        if name is not None and not isinstance(name, str):
            raise RpcDisconnected("Invalid Codex thread name")
        name = (name or "").strip()
        preview = thread.get("preview")
        if not name and isinstance(preview, str):
            name = " ".join(preview.split())
        for key in ("model", "reasoningEffort"):
            value = thread.get(key)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise RpcDisconnected("Invalid Codex model settings")
        return SessionInfo(
            id=cast(str, values[0]),
            provider=cast(str, values[1]),
            name=name or "未命名会话",
            status=cast(
                SessionStatus,
                {
                    "notLoaded": "unavailable",
                    "idle": "idle",
                    "active": "active",
                    "systemError": "error",
                }[status],
            ),
            archived=archived,
            model=thread.get("model"),
            reasoning_effort=thread.get("reasoningEffort"),
        )

    def list_sessions(self, working_path: str | None = None) -> list[SessionInfo]:
        result: dict[str, SessionInfo] = {}
        with ProxyRpc(self.command, self.timeout) as rpc:
            for archived in (False, True):
                cursor: str | None = None
                seen: set[str] = set()
                while True:
                    page = rpc.call(
                        "thread/list",
                        {
                            "cursor": cursor,
                            "limit": 100,
                            "modelProviders": [],
                            "sourceKinds": SOURCE_KINDS,
                            "archived": archived,
                            "useStateDbOnly": True,
                            "cwd": working_path,
                        },
                    )
                    data = page.get("data")
                    if not isinstance(data, list):
                        raise RpcDisconnected("Missing Codex session list")
                    for row in data:
                        info = self._session(row, archived=archived)
                        result.setdefault(info.id, info)
                    cursor = page.get("nextCursor")
                    if cursor is None:
                        break
                    if not isinstance(cursor, str) or not cursor or cursor in seen:
                        raise RpcDisconnected("Invalid Codex pagination cursor")
                    seen.add(cursor)
            if working_path is not None and not result:
                return []
            loaded: set[str] = set()
            cursor = None
            seen = set()
            while True:
                page = rpc.call("thread/loaded/list", {"cursor": cursor, "limit": 100})
                ids = page.get("data")
                if not isinstance(ids, list) or any(not isinstance(sid, str) for sid in ids):
                    raise RpcDisconnected("Invalid loaded Codex session list")
                loaded.update(ids)
                cursor = page.get("nextCursor")
                if cursor is None:
                    break
                if not isinstance(cursor, str) or not cursor or cursor in seen:
                    raise RpcDisconnected("Invalid loaded Codex pagination cursor")
                seen.add(cursor)
            if working_path is not None:
                loaded.intersection_update(result)
            for sid, info in tuple(result.items()):
                if sid not in loaded:
                    result[sid] = replace(info, status="unavailable")
            for sid in sorted(loaded):
                row = rpc.call("thread/read", {"threadId": sid, "includeTurns": False})
                info = self._session(row.get("thread"))
                if info.id != sid:
                    raise RpcDisconnected("Loaded Codex session identity mismatch")
                result[sid] = (
                    replace(info, archived=result[sid].archived) if sid in result else info
                )
        return list(result.values())

    def connected_sessions(self, session_ids: frozenset[str]) -> list[SessionInfo]:
        if not session_ids:
            return []
        result = []
        with ProxyRpc(self.command, self.timeout) as rpc:
            cursor: str | None = None
            seen: set[str] = set()
            loaded: set[str] = set()
            while True:
                page = rpc.call("thread/loaded/list", {"cursor": cursor, "limit": 100})
                ids = page.get("data")
                if not isinstance(ids, list) or any(not isinstance(sid, str) for sid in ids):
                    raise RpcDisconnected("Invalid loaded Codex session list")
                loaded.update(session_ids.intersection(ids))
                cursor = page.get("nextCursor")
                if cursor is None or loaded == session_ids:
                    break
                if not isinstance(cursor, str) or not cursor or cursor in seen:
                    raise RpcDisconnected("Invalid loaded Codex pagination cursor")
                seen.add(cursor)
            for session_id in sorted(loaded):
                row = rpc.call("thread/read", {"threadId": session_id, "includeTurns": False})
                info = self._session(row.get("thread"))
                if info.id != session_id:
                    raise RpcDisconnected("Loaded Codex session identity mismatch")
                result.append(info)
        return result

    def inspect(self, thread_id: str) -> SessionInfo:
        with ProxyRpc(self.command, self.timeout) as rpc:
            result = rpc.call("thread/read", {"threadId": thread_id, "includeTurns": False})
            return self._session(result.get("thread"))

    def model_catalog(self, thread_id: str) -> SessionModelCatalog:
        try:
            with ProxyRpc(self.command, self.timeout) as rpc:
                session = self._model_session(rpc, thread_id)
                return public_catalog(session, read_models(rpc, session.provider))
        except (SessionModelRejected, SessionUnavailableError):
            raise
        except Exception as exc:
            raise SessionUnavailableError(
                "无法读取会话模型", code="session_model_unavailable"
            ) from exc

    def _model_session(self, rpc: ProxyRpc, thread_id: str) -> SessionInfo:
        try:
            return self._target_session(rpc, thread_id)
        except QueueRejected as exc:
            raise SessionModelRejected(
                "会话当前不可用", code="session_model_target_unavailable"
            ) from exc

    def update_model(self, thread_id: str, request: UpdateSessionModel) -> SessionModelCatalog:
        attempted = False
        try:
            with ProxyRpc(self.command, self.timeout) as rpc:
                if request.session_id != thread_id:
                    raise SessionModelRejected("成员会话已变化", code="session_binding_changed")
                session = self._model_session(rpc, thread_id)
                models = read_models(rpc, session.provider)
                selected = next((model for model in models if model.model == request.model), None)
                if selected is None:
                    raise SessionModelRejected(
                        "模型已不可用，请刷新列表", code="session_model_not_available"
                    )
                if session.model == request.model:
                    return public_catalog(session, models)
                efforts = {
                    option.reasoning_effort for option in selected.supported_reasoning_efforts
                }
                effort = (
                    session.reasoning_effort
                    if session.reasoning_effort in efforts
                    else selected.default_reasoning_effort
                )
                attempted = True
                try:
                    rpc.call(
                        "thread/settings/update",
                        {"threadId": thread_id, "model": request.model, "effort": effort},
                    )
                except RpcRejected as exc:
                    raise SessionModelRejected(
                        "模型切换请求未被接受", code="session_model_update_rejected"
                    ) from exc
                confirmed = self._target_session(rpc, thread_id)
                if (
                    confirmed.provider != session.provider
                    or confirmed.model != request.model
                    or confirmed.reasoning_effort != effort
                ):
                    raise RpcDisconnected("Codex model settings are not confirmed")
                return public_catalog(confirmed, models)
        except (SessionModelRejected, SessionUnavailableError):
            raise
        except Exception as exc:
            raise SessionUnavailableError(
                "模型切换结果待确认" if attempted else "无法读取会话模型",
                code="session_model_update_unknown" if attempted else "session_model_unavailable",
            ) from exc

    def interrupt(self, thread_id: str) -> MemberInterruptResult:
        try:
            with ProxyRpc(self.command, self.timeout) as rpc:
                try:
                    session = self._target_session(rpc, thread_id)
                except QueueRejected as exc:
                    raise SessionInterruptRejected(
                        "目标会话当前不可用", code="session_unavailable"
                    ) from exc
                if session.status == "idle":
                    return MemberInterruptResult(status="not_running")
                turn_id = self._active_turn(rpc, thread_id)
                if turn_id is None:
                    raise SessionInterruptRejected(
                        "无法定位正在运行的轮次，请刷新会话状态",
                        code="session_interrupt_turn_unavailable",
                    )
                try:
                    rpc.call("turn/interrupt", {"threadId": thread_id, "turnId": turn_id})
                except RpcRejected as exc:
                    raise SessionInterruptRejected(
                        "当前会话不支持打断" if exc.code == -32601 else "打断请求未被接受",
                        code="session_interrupt_unsupported"
                        if exc.code == -32601
                        else "session_interrupt_rejected",
                    ) from exc
                except Exception as exc:
                    raise SessionUnavailableError(
                        "打断结果待确认，请先检查会话状态", code="session_interrupt_unknown"
                    ) from exc
                return self._confirm_interrupt(rpc, thread_id, turn_id)
        except (SessionInterruptRejected, SessionUnavailableError):
            raise
        except Exception as exc:
            raise SessionUnavailableError(
                "无法读取 Codex 会话", code="session_metadata_unavailable"
            ) from exc

    def _confirm_interrupt(
        self, rpc: ProxyRpc, thread_id: str, turn_id: str
    ) -> MemberInterruptResult:
        deadline = monotonic() + min(self.timeout, 5)
        while (remaining := deadline - monotonic()) > 0:
            rpc.timeout = min(remaining, 1)
            try:
                page = rpc.call(
                    "thread/turns/list",
                    {
                        "threadId": thread_id,
                        "limit": 20,
                        "sortDirection": "desc",
                        "itemsView": "notLoaded",
                    },
                )
                turns = page.get("data")
                if not isinstance(turns, list):
                    break
                target = next(
                    (
                        turn
                        for turn in turns
                        if isinstance(turn, dict) and turn.get("id") == turn_id
                    ),
                    None,
                )
                if target is not None:
                    if target.get("status") == "interrupted":
                        return MemberInterruptResult(status="interrupted", turn_id=turn_id)
                    if target.get("status") in {"completed", "failed"}:
                        return MemberInterruptResult(status="not_running", turn_id=turn_id)
            except Exception as exc:
                raise SessionUnavailableError(
                    "无法确认目标轮次已打断，请检查会话状态", code="session_interrupt_unknown"
                ) from exc
            sleep(min(0.1, max(0, deadline - monotonic())))
        raise SessionUnavailableError(
            "无法确认目标轮次已打断，请检查会话状态", code="session_interrupt_unknown"
        )

    def discover_skills(self, project_path: str, *, force_reload: bool = False) -> SkillDiscovery:
        with ProxyRpc(self.command, self.timeout) as rpc:
            payload = rpc.call("skills/list", {"cwds": [project_path], "forceReload": force_reload})
            return decode_skills(payload, project_path)

    def list_skills(self, project_path: str, *, force_reload: bool = False) -> SkillCatalog:
        return self.discover_skills(project_path, force_reload=force_reload).public_catalog()

    def resolve_skill(self, project_path: str, skill_id: str) -> SkillBinding:
        discovery = self.discover_skills(project_path, force_reload=True)
        for binding in discovery.bindings:
            if binding.option.id == skill_id and binding.option.enabled:
                return binding
        raise RpcDisconnected("Selected skill is unavailable")

    def list_mcp_servers(self, thread_id: str) -> McpCatalog:
        with ProxyRpc(self.command, self.timeout) as rpc:
            return self._mcp_catalog(rpc, thread_id)

    @staticmethod
    def _mcp_catalog(
        rpc: ProxyRpc,
        thread_id: str,
        required_ids: frozenset[str] = frozenset(),
        server_name: str | None = None,
    ) -> McpCatalog:
        servers = []
        cursor: str | None = None
        seen_cursors: set[str] = set()
        seen_servers: set[str] = set()
        while True:
            page = McpPage.model_validate(
                rpc.call(
                    "mcpServerStatus/list",
                    {
                        "threadId": thread_id,
                        "cursor": cursor,
                        "limit": 100,
                        "detail": "toolsAndAuthOnly",
                        "serverName": server_name,
                    },
                )
            )
            for server in page.data:
                if server_name is not None and server.name != server_name:
                    raise RpcDisconnected("MCP server does not match the requested name")
                if server.name in seen_servers:
                    raise RpcDisconnected("Duplicate MCP server identity")
                seen_servers.add(server.name)
                option = server_option(server)
                if option.id in required_ids and not option.available:
                    if (
                        server.runtime_status in {"disabled", "authenticationRequired"}
                        or server.auth_status == "notLoggedIn"
                    ):
                        raise QueueRejected("选中的 MCP 服务器已禁用或需要认证")
                    raise SubmissionDeferred("选中的 MCP 服务器暂时未就绪，稍后重试")
                servers.append(option)
            cursor = page.next_cursor
            if cursor is None:
                return McpCatalog(servers=servers)
            if not cursor or cursor in seen_cursors:
                raise RpcDisconnected("Invalid MCP pagination cursor")
            seen_cursors.add(cursor)

    def _target_session(self, rpc: ProxyRpc, thread_id: str) -> SessionInfo:
        metadata = rpc.call("thread/read", {"threadId": thread_id, "includeTurns": False})
        session = self._session(metadata.get("thread"))
        if session.id != thread_id:
            raise QueueRejected("目标 Codex 会话标识与绑定不符")
        if not session.usable:
            raise TargetSessionUnavailable("目标 Codex 会话暂时未接入或状态异常，稍后重试")
        return session

    def _queue_inputs(
        self, rpc: ProxyRpc, thread_id: str, request: QueueRequest
    ) -> list[dict[str, Any]]:
        self._target_session(rpc, thread_id)
        discovery = decode_skills(
            rpc.call("skills/list", {"cwds": [request.project_path], "forceReload": True}),
            request.project_path,
        )
        required = [
            binding
            for binding in discovery.bindings
            if binding.native_name == "conflua:conflua"
            and binding.option.plugin_id == "conflua@conflua-local"
            and binding.option.enabled
        ]
        if len(required) != 1:
            raise QueueRejected("Conflua skill unavailable; run make install for Codex")
        required_skill = required[0]
        inputs: list[dict[str, Any]] = [
            {"type": "text", "text": request.text},
            {
                "type": "skill",
                "name": required_skill.native_name,
                "path": required_skill.native_path,
            },
        ]
        seen = {("skill", required_skill.option.id)}
        skills = {binding.option.id: binding for binding in discovery.bindings}
        mcp_references = {ref.name: ref for ref in request.capabilities if ref.type == "mcp_server"}
        servers = {
            server.id: server
            for name, reference in mcp_references.items()
            for server in self._mcp_catalog(
                rpc, thread_id, frozenset({reference.id}), server_name=name
            ).servers
        }
        for reference in request.capabilities:
            key = (reference.type, reference.id)
            if key in seen:
                continue
            seen.add(key)
            if reference.type == "skill":
                binding = skills.get(reference.id)
                if binding is None or not binding.option.enabled:
                    raise QueueRejected("Selected skill is unavailable")
                inputs.append(
                    {"type": "skill", "name": binding.native_name, "path": binding.native_path}
                )
            else:
                server = servers.get(reference.id)
                if server is None or not server.available:
                    raise QueueRejected("Selected MCP server is unavailable in this session")
                inputs.append(
                    {"type": "mention", "name": server.name, "path": f"mcp://{server.name}"}
                )
        return inputs

    def enqueue(
        self, thread_id: str, client_message_id: str, request: QueueRequest
    ) -> QueueReceipt:
        with ProxyRpc(self.command, self.timeout) as rpc:
            try:
                inputs = self._queue_inputs(rpc, thread_id, request)
            except Exception as exc:
                raise QueueRejected("Capability validation failed before queue submission") from exc
            return self._enqueue(rpc, thread_id, client_message_id, inputs)

    @staticmethod
    def _enqueue(
        rpc: ProxyRpc, thread_id: str, client_message_id: str, inputs: list[dict[str, Any]]
    ) -> QueueReceipt:
        try:
            result = rpc.call(
                "thread/queue/add",
                {
                    "threadId": thread_id,
                    "clientUserMessageId": client_message_id,
                    "input": inputs,
                },
            )
        except RpcRejected as exc:
            if exc.code not in {-32600, -32601, -32602}:
                raise SubmissionUnknown("Queue acceptance is uncertain", "queue") from exc
            raise QueueRejected(str(exc)) from exc
        receipt = result.get("queuedSubmission")
        if (
            not isinstance(receipt, dict)
            or not isinstance(receipt.get("id"), str)
            or not receipt["id"]
            or receipt.get("clientUserMessageId") != client_message_id
        ):
            raise RpcDisconnected("Queue receipt does not match this submission")
        return QueueReceipt(
            receipt["id"], {key: value for key, value in receipt.items() if key != "input"}
        )

    @staticmethod
    def _active_turn(rpc: ProxyRpc, thread_id: str) -> str | None:
        try:
            result = rpc.call(
                "thread/turns/list",
                {
                    "threadId": thread_id,
                    "limit": 1,
                    "sortDirection": "desc",
                    "itemsView": "notLoaded",
                },
            )
        except RpcRejected as exc:
            if exc.code == -32601:
                return None
            raise
        data = result.get("data")
        if not isinstance(data, list):
            raise RpcDisconnected("Missing Codex turn page")
        if not data:
            return None
        turn = data[0]
        if not isinstance(turn, dict):
            raise RpcDisconnected("Invalid Codex turn")
        if turn.get("status") != "inProgress":
            return None
        turn_id = turn.get("id")
        if not isinstance(turn_id, str) or not turn_id.strip():
            raise RpcDisconnected("Missing Codex active turn identity")
        return turn_id

    def _steer_fallback(self, rpc: ProxyRpc, thread_id: str, expected_turn_id: str) -> bool:
        try:
            session = self._target_session(rpc, thread_id)
            if session.status == "idle":
                return True
            turn_id = self._active_turn(rpc, thread_id)
            return turn_id is not None and turn_id != expected_turn_id
        except Exception:
            return False

    def submit(
        self, thread_id: str, client_message_id: str, request: QueueRequest
    ) -> QueueReceipt | SteerReceipt:
        method: SubmissionMethod | None = None
        try:
            with ProxyRpc(self.command, self.timeout) as rpc:
                inputs = self._queue_inputs(rpc, thread_id, request)
                session = self._target_session(rpc, thread_id)
                turn_id = self._active_turn(rpc, thread_id) if session.status == "active" else None
                note = None
                if turn_id is not None:
                    method = "steer"
                    try:
                        result = rpc.call(
                            "turn/steer",
                            {
                                "threadId": thread_id,
                                "expectedTurnId": turn_id,
                                "clientUserMessageId": client_message_id,
                                "input": inputs,
                            },
                        )
                    except RpcRejected as exc:
                        if exc.code == -32601:
                            note = "当前输入通道不支持即时送达，已入队等待接收"
                        elif exc.code in {-32600, -32602}:
                            if not self._steer_fallback(rpc, thread_id, turn_id):
                                raise SubmissionRejected(
                                    "Steer request was not accepted", method
                                ) from exc
                            note = "当前轮次已变化，已入队等待接收"
                        else:
                            raise SubmissionUnknown("Steer result is uncertain", method) from exc
                    else:
                        if result.get("turnId") != turn_id:
                            raise RpcDisconnected("Steer response does not match the active turn")
                        return SteerReceipt(turn_id)
                elif session.status == "active":
                    note = "暂时无法定位当前轮次，已入队等待接收"
                method = "queue"
                return replace(self._enqueue(rpc, thread_id, client_message_id, inputs), note=note)
        except (SubmissionDeferred, SubmissionRejected, SubmissionUnknown):
            raise
        except TargetSessionUnavailable as exc:
            if method is None:
                raise SubmissionDeferred(str(exc)) from exc
            raise SubmissionUnknown("Codex submission result is uncertain", method) from exc
        except QueueRejected as exc:
            raise SubmissionRejected(str(exc), method) from exc
        except (ProxyConfigurationError, FileNotFoundError, PermissionError) as exc:
            if method is None:
                raise SubmissionRejected("Codex 启动配置无效、文件缺失或没有执行权限") from exc
            raise SubmissionUnknown("Codex submission result is uncertain", method) from exc
        except (ConnectionError, TimeoutError, RpcDisconnected, ConnectionClosed) as exc:
            if method is None:
                raise SubmissionDeferred("提交前 Codex 通道暂时不可用，稍后重试") from exc
            raise SubmissionUnknown("Codex submission result is uncertain", method) from exc
        except OSError as exc:
            if method is None:
                raise SubmissionRejected("Codex 启动或连接配置不可用，未提交输入") from exc
            raise SubmissionUnknown("Codex submission result is uncertain", method) from exc
        except RpcRejected as exc:
            if method is None and (
                exc.code == -32603
                or (exc.code == -32600 and str(exc) == f"thread not loaded: {thread_id}")
            ):
                raise SubmissionDeferred("提交前 Codex 服务暂时不可用，稍后重试") from exc
            if method is None:
                raise SubmissionRejected(str(exc)) from exc
            raise SubmissionUnknown("Codex submission result is uncertain", method) from exc
        except Exception as exc:
            if method is None:
                raise SubmissionRejected("Validation failed before submission") from exc
            raise SubmissionUnknown("Codex submission result is uncertain", method) from exc

    def read_queue_page(self, thread_id: str, cursor: str | None = None) -> QueuePage:
        with ProxyRpc(self.command, self.timeout) as rpc:
            page = rpc.call(
                "thread/queue/list", {"threadId": thread_id, "cursor": cursor, "limit": 100}
            )
            data = page.get("data")
            if not isinstance(data, list):
                raise RpcDisconnected("Missing Codex queue page")
            inputs = []
            for row in data:
                if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"]:
                    raise RpcDisconnected("Invalid Codex queued input")
                client_id = row.get("clientUserMessageId")
                if client_id is None:
                    continue
                if not isinstance(client_id, str) or not client_id:
                    raise RpcDisconnected("Invalid Codex queued client identity")
                metadata = {key: value for key, value in row.items() if key != "input"}
                inputs.append(QueuedInput(client_id, QueueReceipt(row["id"], metadata)))
            next_cursor = page.get("nextCursor")
            if next_cursor is not None and (
                not isinstance(next_cursor, str) or not next_cursor or next_cursor == cursor
            ):
                raise RpcDisconnected("Invalid Codex queue pagination cursor")
            return QueuePage(tuple(inputs), next_cursor)

    def delete(self, thread_id: str, queued_submission_id: str) -> bool:
        with ProxyRpc(self.command, self.timeout) as rpc:
            try:
                result = rpc.call(
                    "thread/queue/delete",
                    {"threadId": thread_id, "queuedSubmissionId": queued_submission_id},
                )
            except RpcRejected as exc:
                raise QueueRejected(str(exc)) from exc
            deleted = result.get("deleted")
            if not isinstance(deleted, bool):
                raise RpcDisconnected("Missing Codex queue deletion result")
            return deleted

    def activation_candidate(self, thread_id: str) -> QueueHead | None:
        with ProxyRpc(self.command, self.timeout) as rpc:
            metadata = rpc.call("thread/read", {"threadId": thread_id, "includeTurns": False})
            info = self._session(metadata.get("thread"))
            if info.id != thread_id:
                raise RpcDisconnected("Codex session identity mismatch")
            if info.status != "idle":
                return None
            page = rpc.call("thread/queue/list", {"threadId": thread_id, "limit": 1})
            data = page.get("data")
            if not isinstance(data, list):
                raise RpcDisconnected("Missing Codex queue list")
            if not data:
                return None
            head = data[0]
            if not isinstance(head, dict) or not isinstance(head.get("id"), str) or not head["id"]:
                raise RpcDisconnected("Invalid Codex queue head")
            client_id = head.get("clientUserMessageId")
            return QueueHead(head["id"], client_id if isinstance(client_id, str) else None)

    def activate(self, thread_id: str, queued_submission_id: str) -> str:
        with ProxyRpc(self.command, self.timeout) as rpc:
            try:
                result = rpc.call(
                    "thread/queue/start",
                    {"threadId": thread_id, "queuedSubmissionId": queued_submission_id},
                )
            except RpcRejected as exc:
                raise ActivationRejected(str(exc)) from exc
            turn = result.get("turn")
            if not isinstance(turn, dict) or not isinstance(turn.get("id"), str) or not turn["id"]:
                raise RpcDisconnected("Missing started Codex turn identity")
            return cast(str, turn["id"])

    def read_input_page(self, thread_id: str, cursor: str | None = None) -> InputPage:
        with ProxyRpc(self.command, self.timeout) as rpc:
            try:
                return self._read_input_page(rpc, thread_id, cursor)
            except RpcRejected as exc:
                if exc.code == -32601:
                    raise InputHistoryUnavailable(
                        "Codex input history methods are unsupported"
                    ) from exc
                if exc.code == -32600 and str(exc) == f"thread not loaded: {thread_id}":
                    raise InputHistoryUnavailable("Codex session is not loaded") from exc
                raise

    @staticmethod
    def _read_input_page(rpc: ProxyRpc, thread_id: str, cursor: str | None) -> InputPage:
        source = "items"
        if cursor is not None:
            source, separator, cursor = cursor.partition(":")
            if not separator or source not in {"items", "turns"} or not cursor:
                raise RpcDisconnected("Invalid Codex input history cursor")
        params = {"threadId": thread_id, "cursor": cursor, "limit": 100, "sortDirection": "desc"}
        if source == "items":
            try:
                page = rpc.call("thread/items/list", params)
            except RpcRejected as exc:
                if exc.code != -32601:
                    raise
                source = "turns"
                params = {**params, "cursor": None}
        if source == "turns":
            page = rpc.call("thread/turns/list", {**params, "itemsView": "full"})
        data = page.get("data")
        if not isinstance(data, list):
            raise RpcDisconnected("Missing Codex input history page")
        if source == "turns":
            rows: list[dict[str, Any]] = []
            for turn in data:
                if not isinstance(turn, dict) or not isinstance(turn.get("items"), list):
                    raise RpcDisconnected("Invalid Codex history turn")
                rows.extend({"turnId": turn.get("id"), "item": item} for item in turn["items"])
            data = rows
        inputs = []
        for row in data:
            if not isinstance(row, dict) or not isinstance(row.get("item"), dict):
                raise RpcDisconnected("Invalid Codex history item")
            item = row["item"]
            if item.get("type") != "userMessage" or not item.get("clientId"):
                continue
            values = (item["clientId"], item.get("id"), row.get("turnId"))
            if any(not isinstance(value, str) or not value for value in values):
                raise RpcDisconnected("Incomplete Codex input identity")
            inputs.append(ReceivedInput(*(cast(str, value) for value in values)))
        next_cursor = page.get("nextCursor")
        if next_cursor is not None:
            if not isinstance(next_cursor, str) or not next_cursor:
                raise RpcDisconnected("Invalid Codex input history cursor")
            next_cursor = f"{source}:{next_cursor}"
        return InputPage(tuple(inputs), next_cursor)
