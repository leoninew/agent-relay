import ctypes
import logging
import os
import sys
from collections.abc import Mapping

from agent_relay.application.dto.preferences import ResolvedLanguage

logger = logging.getLogger(__name__)


def language_from_locale(value: str) -> ResolvedLanguage:
    normalized = value.strip().split(".", 1)[0].split("@", 1)[0].replace("_", "-")
    return "zh-CN" if normalized.split("-", 1)[0].lower() == "zh" else "en"


def detect_system_language(
    *, platform: str | None = None, environ: Mapping[str, str] | None = None
) -> ResolvedLanguage:
    try:
        if (platform or sys.platform) == "win32":
            windll = getattr(ctypes, "windll", None)
            if windll is None:
                return "en"
            language_id = int(windll.kernel32.GetUserDefaultUILanguage())
            return "zh-CN" if language_id & 0x3FF == 0x04 else "en"
        source = os.environ if environ is None else environ
        for name in ("LC_ALL", "LC_MESSAGES", "LANG"):
            value = source.get(name, "").strip()
            if value:
                return language_from_locale(value)
    except Exception:
        logger.warning("Unable to detect system display language", exc_info=True)
    return "en"
