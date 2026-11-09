from dataclasses import dataclass
from typing import Literal, Protocol

type SessionStatus = Literal["unavailable", "idle", "active", "error"]


class SessionUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class SessionInfo:
    id: str
    cwd: str
    provider: str
    name: str
    status: SessionStatus
    archived: bool = False

    @property
    def usable(self) -> bool:
        return not self.archived and self.status in {"idle", "active"}

    @property
    def unavailable_reason(self) -> str | None:
        if self.archived:
            return "会话已归档；请在 Codex 中恢复并接入共享 daemon 后刷新"
        if self.status == "error":
            return "会话状态异常；请在原 Codex 会话处理后刷新"
        if not self.usable:
            return (
                "未接入当前消息通道，可能未运行或在独立实例中运行；"
                "请使用共享 daemon 打开此会话后刷新"
            )
        return None

    @property
    def presence(self) -> Literal["available", "busy", "offline", "unknown"]:
        if not self.usable:
            return "unknown"
        return "available" if self.status == "idle" else "busy"


class SessionDriver(Protocol):
    def list_sessions(self) -> list[SessionInfo]: ...
    def inspect(self, thread_id: str) -> SessionInfo: ...
