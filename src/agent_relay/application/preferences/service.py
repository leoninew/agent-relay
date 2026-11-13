from agent_relay.application.dto.preferences import (
    LanguagePreference,
    Preferences,
    ResolvedLanguage,
)
from agent_relay.application.preferences.ports import PreferencesStore


class PreferencesService:
    def __init__(
        self,
        default_language: LanguagePreference,
        store: PreferencesStore,
        system_language: ResolvedLanguage,
    ) -> None:
        self.default_language = default_language
        self.store = store
        self.system_language = system_language

    def get(self) -> Preferences:
        language = self.store.load() or self.default_language
        return self._resolve(language)

    def update(self, language: LanguagePreference) -> Preferences:
        self.store.save(language)
        return self._resolve(language)

    def _resolve(self, language: LanguagePreference) -> Preferences:
        resolved = self.system_language if language == "system" else language
        return Preferences(language=language, resolvedLanguage=resolved)
