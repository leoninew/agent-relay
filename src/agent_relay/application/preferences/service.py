from agent_relay.application.dto.preferences import (
    LanguagePreference,
    Preferences,
    ResolvedLanguage,
    StoredPreferences,
    ThemePreference,
)
from agent_relay.application.preferences.ports import PreferencesStore


class PreferencesService:
    def __init__(
        self,
        default_language: LanguagePreference,
        default_theme: ThemePreference,
        store: PreferencesStore,
        system_language: ResolvedLanguage,
    ) -> None:
        self.default_language = default_language
        self.default_theme = default_theme
        self.store = store
        self.system_language = system_language

    def get(self) -> Preferences:
        stored = self.store.load()
        return self._resolve(stored)

    def update(
        self,
        *,
        language: LanguagePreference | None = None,
        theme: ThemePreference | None = None,
    ) -> Preferences:
        return self._resolve(self.store.update(language=language, theme=theme))

    def _resolve(self, stored: StoredPreferences) -> Preferences:
        language = stored.language or self.default_language
        resolved = self.system_language if language == "system" else language
        return Preferences(
            language=language,
            resolvedLanguage=resolved,
            theme=stored.theme or self.default_theme,
        )
