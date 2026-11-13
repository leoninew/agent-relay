from importlib.metadata import PackageNotFoundError, version

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["application"])


class AppInfo(BaseModel):
    version: str | None


@router.get("/app", response_model=AppInfo)
def get_app_info() -> AppInfo:
    try:
        return AppInfo(version=version("agent-relay"))
    except PackageNotFoundError:
        return AppInfo(version=None)
