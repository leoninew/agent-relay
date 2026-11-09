import logging
from collections.abc import Callable
from glob import iglob
from pathlib import Path
from socket import socket

import uvicorn
from uvicorn.supervisors.basereload import BaseReload
from watchfiles import Change, DefaultFilter

from agent_relay.bootstrap.config import ServerSettings


class DevelopmentReload(BaseReload):
    def __init__(
        self,
        config: uvicorn.Config,
        target: Callable[[list[socket] | None], None],
        sockets: list[socket],
        *,
        paths: list[str],
    ) -> None:
        super().__init__(config, target, sockets)
        self.reloader_name = "ConfiguredPathReload"
        self.paths = [str(Path(path).absolute()) for path in paths]
        self.file_filter = DefaultFilter(ignore_dirs=(*DefaultFilter.ignore_dirs, "tests"))
        self.stamps = self._snapshot()

    def _snapshot(self) -> dict[Path, tuple[int, int, int]]:
        stamps: dict[Path, tuple[int, int, int]] = {}
        for pattern in self.paths:
            if Path(pattern).is_dir():
                pattern = str(Path(pattern) / "**" / "*")
            for name in iglob(pattern, recursive=True, include_hidden=True):
                if not self.file_filter(Change.modified, name):
                    continue
                path = Path(name)
                try:
                    if path.is_file():
                        stat = path.stat()
                        stamps[path] = stat.st_mtime_ns, stat.st_size, stat.st_ino
                except FileNotFoundError:
                    # A save may replace the file between the glob and stat calls.
                    continue
        return stamps

    def should_restart(self) -> list[Path] | None:
        self.pause()
        current = self._snapshot()
        changes = [
            path
            for path in self.stamps.keys() | current.keys()
            if self.stamps.get(path) != current.get(path)
        ]
        self.stamps = current
        return sorted(changes) or None


def run_development(settings: ServerSettings, profile: str) -> None:
    paths = [path.replace("{profile}", profile) for path in settings.reload_paths]
    config = uvicorn.Config(
        "agent_relay.server:create_server_app",
        host=settings.host,
        port=settings.port,
        factory=True,
        loop="asyncio:SelectorEventLoop",
        access_log=False,
        log_config=None,
    )
    # This supervisor selects files itself instead of Uvicorn inferring watch directories.
    config.reload = True
    logging.getLogger("uvicorn.error").info("Will reload on changes matching: %s", paths)
    server = uvicorn.Server(config)
    DevelopmentReload(
        config,
        target=server.run,
        sockets=[config.bind_socket()],
        paths=paths,
    ).run()
