from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import Connection

from agent_relay.resources import resource_root

MIGRATION_HEAD = "delivery_steer_20261112"


def _configuration(path: Path, *, resources: Path | None = None) -> Config:
    active_resources = (resources or resource_root()).resolve()
    config = Config(str(active_resources / "alembic.ini"))
    config.attributes["skip_logging_config"] = True
    config.set_main_option("sqlalchemy.url", f"sqlite:///{path.as_posix()}".replace("%", "%%"))
    config.set_main_option(
        "script_location",
        str(active_resources / "migrations" / "sqlite").replace("%", "%%"),
    )
    config.set_main_option(
        "prepend_sys_path", str(Path(__file__).resolve().parents[3]).replace("%", "%%")
    )
    return config


def run_migrations(
    path: Path,
    *,
    connection: Connection | None = None,
    resources: Path | None = None,
) -> None:
    database_path = path.expanduser().resolve()
    config = _configuration(database_path, resources=resources)
    if connection is None:
        database_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        config.attributes["connection"] = connection
    command.upgrade(config, "head")
