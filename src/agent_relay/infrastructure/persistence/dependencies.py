from pathlib import Path

from agent_relay.infrastructure.persistence.database import Database
from agent_relay.infrastructure.persistence.migrations import run_migrations


def create_database(path: Path, *, migrate_on_startup: bool = False) -> Database:
    if migrate_on_startup:
        run_migrations(path)
    return Database(path)
