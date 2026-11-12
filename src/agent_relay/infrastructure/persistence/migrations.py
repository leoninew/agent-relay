from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import Connection

MIGRATION_HEAD = "delivery_steer_20261112"


def _configuration(path: Path) -> Config:
    config = Config(str(Path.cwd() / "alembic.ini"))
    config.attributes["skip_logging_config"] = True
    config.set_main_option("sqlalchemy.url", f"sqlite:///{path.as_posix()}".replace("%", "%%"))
    return config


def run_migrations(path: Path, *, connection: Connection | None = None) -> None:
    database_path = path.expanduser().resolve()
    config = _configuration(database_path)
    if connection is None:
        database_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        config.attributes["connection"] = connection
    command.upgrade(config, "head")
