import json
import logging
import os
import tempfile
from pathlib import Path
from threading import Lock

from pydantic import ValidationError

from agent_relay.application.dto.preferences import LanguagePreference, UpdatePreferences
from agent_relay.application.preferences.ports import PreferenceReadError, PreferenceWriteError

logger = logging.getLogger(__name__)


class FilePreferencesStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = Lock()

    def load(self) -> LanguagePreference | None:
        try:
            raw = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except (OSError, UnicodeError) as exc:
            if isinstance(exc, UnicodeError):
                logger.warning("Invalid preferences file encoding", exc_info=True)
                return None
            raise PreferenceReadError("Unable to read preferences") from exc
        try:
            return UpdatePreferences.model_validate(json.loads(raw)).language
        except (ValueError, ValidationError):
            logger.warning("Invalid preferences file", exc_info=True)
            return None

    def save(self, language: LanguagePreference) -> None:
        request = UpdatePreferences(language=language)
        temporary: Path | None = None
        with self._lock:
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", dir=self.path.parent, delete=False
                ) as handle:
                    temporary = Path(handle.name)
                    json.dump(request.model_dump(), handle, ensure_ascii=False)
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
