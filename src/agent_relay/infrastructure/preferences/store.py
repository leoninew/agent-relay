import json
import logging
import os
import tempfile
from pathlib import Path
from threading import Lock

from pydantic import ValidationError

from agent_relay.application.dto.preferences import (
    LanguagePreference,
    StoredPreferences,
    ThemePreference,
)
from agent_relay.application.preferences.ports import PreferenceReadError, PreferenceWriteError

logger = logging.getLogger(__name__)


class FilePreferencesStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = Lock()

    def load(self) -> StoredPreferences:
        return self._load()

    def update(
        self,
        *,
        language: LanguagePreference | None = None,
        theme: ThemePreference | None = None,
    ) -> StoredPreferences:
        with self._lock:
            stored = self._load()
            merged = StoredPreferences(
                language=language if language is not None else stored.language,
                theme=theme if theme is not None else stored.theme,
            )
            self._save(merged)
            return merged

    def _load(self) -> StoredPreferences:
        try:
            raw = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return StoredPreferences()
        except (OSError, UnicodeError) as exc:
            if isinstance(exc, UnicodeError):
                logger.warning("Invalid preferences file encoding", exc_info=True)
                return StoredPreferences()
            raise PreferenceReadError("Unable to read preferences") from exc
        try:
            return StoredPreferences.model_validate(json.loads(raw))
        except (ValueError, ValidationError):
            logger.warning("Invalid preferences file", exc_info=True)
            return StoredPreferences()

    def _save(self, preferences: StoredPreferences) -> None:
        temporary: Path | None = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.path.parent, delete=False
            ) as handle:
                temporary = Path(handle.name)
                json.dump(
                    preferences.model_dump(exclude_none=True),
                    handle,
                    ensure_ascii=False,
                )
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        except OSError as exc:
            raise PreferenceWriteError("Unable to save preferences") from exc
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    logger.warning("Unable to remove temporary preferences file", exc_info=True)
