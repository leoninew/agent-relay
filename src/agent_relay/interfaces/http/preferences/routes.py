from fastapi import APIRouter

from agent_relay.application.dto.preferences import Preferences, UpdatePreferences
from agent_relay.interfaces.http.preferences.dependencies import PreferencesDependency

router = APIRouter(prefix="/preferences", tags=["preferences"])


@router.get("")
def get_preferences(service: PreferencesDependency) -> Preferences:
    return service.get()


@router.patch("")
def update_preferences(request: UpdatePreferences, service: PreferencesDependency) -> Preferences:
    return service.update(language=request.language, theme=request.theme)
