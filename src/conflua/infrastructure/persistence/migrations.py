from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Text, column, select, table
from sqlalchemy.engine import Connection

from conflua.resources import resource_root

MIGRATION_HEAD = "schema_governance_20261119"


def check_database_revision(connection: Connection, *, allow_empty: bool = False) -> None:
    objects = set(
        connection.exec_driver_sql(
            "SELECT name FROM sqlite_schema WHERE name NOT GLOB 'sqlite_*'"
        ).scalars()
    )
    if not objects:
        if allow_empty:
            return
        raise RuntimeError("Room database is not migrated; run `python -m conflua.migrate`")
    if "alembic_version" in objects:
        version = table("alembic_version", column("version_num", Text))
        revisions = list(connection.scalars(select(version.c.version_num)))
    else:
        revisions = []
    if revisions != [MIGRATION_HEAD]:
        raise RuntimeError(
            f"Room database revisions are {revisions!r}; expected {MIGRATION_HEAD!r}. "
            "Existing databases are not upgraded in place. Stop Conflua and use the "
            "offline SQLite migration on a backup copy; do not stamp this database."
        )


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
