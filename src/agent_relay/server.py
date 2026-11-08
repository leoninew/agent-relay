import argparse

import uvicorn
from fastapi import FastAPI

from agent_relay.api import build_app
from agent_relay.config import ServerSettings, load_settings
from agent_relay.development_reload import run_development
from agent_relay.logging_setup import configure_logging


def create_server_app() -> FastAPI:
    configure_logging()
    return build_app()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Agent Relay API service.")
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
        "agent_relay.server:create_server_app",
        host=server.host,
        port=server.port,
        reload=server.reload,
        factory=True,
        access_log=False,
        log_config=None,
    )


if __name__ == "__main__":
    main()
