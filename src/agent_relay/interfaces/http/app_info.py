from fastapi import APIRouter
from pydantic import BaseModel

from agent_relay import __version__

router = APIRouter(tags=["application"])


class AppInfo(BaseModel):
    version: str


@router.get("/app", response_model=AppInfo)
def get_app_info() -> AppInfo:
    return AppInfo(version=__version__)
