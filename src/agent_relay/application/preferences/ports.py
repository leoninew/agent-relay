from typing import Protocol

from agent_relay.application.dto.preferences import (
    LanguagePreference,
    StoredPreferences,
    ThemePreference,
)


class PreferenceReadError(OSError):
    pass


class PreferenceWriteError(OSError):
    pass


class PreferencesStore(Protocol):
    def load(self) -> StoredPreferences: ...
    def update(
        self,
        *,
        language: LanguagePreference | None = None,
        theme: ThemePreference | None = None,
    ) -> StoredPreferences: ...
