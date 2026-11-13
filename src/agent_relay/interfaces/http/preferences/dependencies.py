from typing import Annotated, cast

from fastapi import Depends
from starlette.requests import HTTPConnection

from agent_relay.application.preferences.service import PreferencesService


def get_preferences(connection: HTTPConnection) -> PreferencesService:
    return cast(PreferencesService, connection.app.state.preferences)


PreferencesDependency = Annotated[PreferencesService, Depends(get_preferences)]
