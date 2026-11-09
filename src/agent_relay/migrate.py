"""Explicit database schema upgrade entry point."""

import argparse
import logging

from agent_relay.bootstrap.config import load_settings
from agent_relay.infrastructure.persistence.migrations import MIGRATION_HEAD, run_migrations


def main() -> None:
    parser = argparse.ArgumentParser(description="Upgrade the room database using SQL migrations")
    parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.info("Database migration started target=%s", MIGRATION_HEAD)
    run_migrations(load_settings().database.path)
    logging.info("Database migration completed target=%s", MIGRATION_HEAD)


if __name__ == "__main__":
    main()
