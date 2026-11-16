from pathlib import Path

from conflua.application.preferences.service import PreferencesService
from conflua.bootstrap.paths import user_data_root
from conflua.bootstrap.settings import Settings
from conflua.infrastructure.preferences.store import FilePreferencesStore
from conflua.infrastructure.preferences.system_language import detect_system_language


def create_preferences_service(
    settings: Settings, *, user_root: Path | None = None
) -> PreferencesService:
    return PreferencesService(
        settings.preferences.language,
        settings.preferences.theme,
        FilePreferencesStore((user_root or user_data_root()) / "preferences.json"),
        detect_system_language(),
    )
