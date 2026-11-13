from pathlib import Path

from agent_relay.application.preferences.service import PreferencesService
from agent_relay.bootstrap.paths import user_data_root
from agent_relay.bootstrap.settings import Settings
from agent_relay.infrastructure.preferences.store import FilePreferencesStore
from agent_relay.infrastructure.preferences.system_language import detect_system_language


def create_preferences_service(
    settings: Settings, *, user_root: Path | None = None
) -> PreferencesService:
    return PreferencesService(
        settings.preferences.language,
        FilePreferencesStore((user_root or user_data_root()) / "preferences.json"),
        detect_system_language(),
    )
