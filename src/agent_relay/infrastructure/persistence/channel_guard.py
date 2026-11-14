from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from hashlib import sha256
from pathlib import Path

from agent_relay.domain.rooms.errors import RoomConflictError
from agent_relay.infrastructure.dispatch.lock import SubmitterLock

_held: ContextVar[frozenset[str]] = ContextVar("relay_channel_guards", default=frozenset())


@contextmanager
def room_operation(database_path: Path, room_id: str) -> Iterator[None]:
    directory = database_path.parent / "locks"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / sha256(room_id.encode()).hexdigest()
    key = str(path.resolve())
    if key in _held.get():
        yield
        return
    lock = SubmitterLock(path)
    if not lock.acquire():
        raise RoomConflictError("聊天室操作正在进行，请稍后重试", code="channel_operation_busy")
    token = _held.set(_held.get() | {key})
    try:
        yield
    finally:
        _held.reset(token)
        lock.release()
