from pathlib import Path

from agent_relay.infrastructure.persistence.migrations import run_migrations
from agent_relay.infrastructure.persistence.store import SQLiteRoomStore


def create_database(path: Path, *, migrate_on_startup: bool = False) -> SQLiteRoomStore:
    if migrate_on_startup:
        run_migrations(path)
    return SQLiteRoomStore(path)
