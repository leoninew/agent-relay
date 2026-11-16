import argparse

import uvicorn
from fastapi import FastAPI

from conflua.bootstrap.config import load_settings
from conflua.bootstrap.http import build_app
from conflua.bootstrap.logging import configure_logging
from conflua.bootstrap.reload import run_development
from conflua.bootstrap.settings import ServerSettings


def create_server_app() -> FastAPI:
    configure_logging()
    return build_app()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Conflua API service.")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--reload", action="store_true", default=None)
    args = parser.parse_args()
    configure_logging(include_files=False)
    settings = load_settings()
    server = ServerSettings.model_validate(
        {
            **settings.server.model_dump(),
            **{name: value for name, value in vars(args).items() if value is not None},
        }
    )
    if server.reload:
        run_development(server, settings.profile)
        return
    uvicorn.run(
        "conflua.server:create_server_app",
        host=server.host,
        port=server.port,
        reload=server.reload,
        factory=True,
        # Windows Proactor socket resets can prevent Server.wait_closed() from finishing.
        loop="asyncio:SelectorEventLoop",
        access_log=False,
        log_config=None,
    )


if __name__ == "__main__":
    main()
