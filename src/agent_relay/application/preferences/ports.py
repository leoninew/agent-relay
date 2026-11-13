from typing import Protocol

from agent_relay.application.dto.preferences import LanguagePreference


class PreferenceReadError(OSError):
    pass


class PreferenceWriteError(OSError):
    pass


class PreferencesStore(Protocol):
    def load(self) -> LanguagePreference | None: ...
    def save(self, language: LanguagePreference) -> None: ...
