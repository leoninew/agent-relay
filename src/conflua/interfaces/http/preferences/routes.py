from fastapi import APIRouter

from conflua.application.dto.preferences import Preferences, UpdatePreferences
from conflua.interfaces.http.preferences.dependencies import PreferencesDependency

router = APIRouter(prefix="/preferences", tags=["preferences"])


@router.get("")
def get_preferences(service: PreferencesDependency) -> Preferences:
    return service.get()


@router.patch("")
def update_preferences(request: UpdatePreferences, service: PreferencesDependency) -> Preferences:
    return service.update(language=request.language, theme=request.theme)
