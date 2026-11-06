import logging.config
import sys
from pathlib import Path
from typing import Any

import yaml


def configure_logging(project_root: Path | None = None, *, include_files: bool = True) -> None:
    configure_console_encoding()
    config_path = Path(__file__).with_name("logging.yaml")
    config: dict[str, Any] = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    handlers = config["handlers"]

    removed_handlers: set[str] = set()
    if sys.stdout is None:
        removed_handlers.add("console")
    for name, handler in handlers.items():
        filename = handler.get("filename")
        if filename is None:
            continue
        if not include_files:
            removed_handlers.add(name)
            continue
        path = Path(filename)
        if not path.is_absolute():
            path = (project_root or Path.cwd()) / path
        path.parent.mkdir(parents=True, exist_ok=True)
        handler["filename"] = str(path)

    if removed_handlers:
        for name in removed_handlers:
            handlers.pop(name, None)
        logger_configs = [config["root"], *config["loggers"].values()]
        for logger_config in logger_configs:
            logger_config["handlers"] = [
                name for name in logger_config["handlers"] if name not in removed_handlers
            ]

    logging.config.dictConfig(config)


def configure_console_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="backslashreplace")
