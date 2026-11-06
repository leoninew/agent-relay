from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import Scope

from agent_relay.dependencies import application_settings


class SpaStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404 and not Path(path).suffix:
                return await super().get_response("index.html", scope)
            raise


def mount_static_files(app: FastAPI, *, directory: Path | None = None) -> None:
    app.mount(
        "/static",
        SpaStaticFiles(
            directory=directory or application_settings(app).static.directory,
            html=True,
            check_dir=False,
        ),
        name="static",
    )
