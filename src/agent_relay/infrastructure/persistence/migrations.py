from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

MIGRATION_HEAD = "baseline_20261109"


def _configuration(path: Path) -> Config:
    config = Config(str(Path.cwd() / "alembic.ini"))
    config.attributes["skip_logging_config"] = True
    config.set_main_option("sqlalchemy.url", f"sqlite:///{path.as_posix()}".replace("%", "%%"))
    return config


def run_migrations(path: Path) -> None:
    database_path = path.expanduser().resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    command.upgrade(_configuration(database_path), "head")
