from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, event, pool

from agent_relay.bootstrap.config import load_settings

config = context.config
if config.config_file_name and not config.attributes.get("skip_logging_config", False):
    fileConfig(config.config_file_name, disable_existing_loggers=False)


def database_url() -> str:
    configured = config.get_main_option("sqlalchemy.url")
    if configured:
        return configured
    return f"sqlite:///{load_settings().database.path.expanduser().resolve().as_posix()}"


def run_migrations_offline() -> None:
    context.configure(
        url=database_url(),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        transactional_ddl=True,
    )
    context.execute("PRAGMA foreign_keys=ON")
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    supplied_connection = config.attributes.get("connection")
    if supplied_connection is not None:
        context.configure(
            connection=supplied_connection, target_metadata=None, transactional_ddl=True
        )
        with context.begin_transaction():
            context.run_migrations()
        return
    config.set_main_option("sqlalchemy.url", database_url().replace("%", "%%"))
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    @event.listens_for(connectable, "connect")
    def enable_foreign_keys(dbapi_connection: object, _connection_record: object) -> None:
        # Explicit BEGIN keeps DDL, data changes and revision markers in one transaction.
        dbapi_connection.isolation_level = None  # type: ignore[attr-defined]
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()

    @event.listens_for(connectable, "begin")
    def begin_transaction(connection: object) -> None:
        connection.exec_driver_sql("BEGIN IMMEDIATE")  # type: ignore[attr-defined]

    try:
        with connectable.connect() as connection:
            context.configure(connection=connection, target_metadata=None, transactional_ddl=True)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
