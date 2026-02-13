"""Settings service — load/save ~/.config/linguaedit/settings.json."""

from __future__ import annotations

import json
import locale
from pathlib import Path
from typing import Any

_SETTINGS_FILE = Path.home() / ".config" / "linguaedit" / "settings.json"

# All 25 supported languages with their locale codes
SUPPORTED_LANGUAGES = [
    ("ar", "العربية (Arabic)"),
    ("ca", "Català (Catalan)"),
    ("cs", "Čeština (Czech)"),
    ("da", "Dansk (Danish)"),
    ("de", "Deutsch (German)"),
    ("el", "Ελληνικά (Greek)"),
    ("en", "English"),
    ("es", "Español (Spanish)"),
    ("fi", "Suomi (Finnish)"),
    ("fr", "Français (French)"),
    ("hu", "Magyar (Hungarian)"),
    ("it", "Italiano (Italian)"),
    ("ja", "日本語 (Japanese)"),
    ("ko", "한국어 (Korean)"),
    ("nb", "Norsk bokmål (Norwegian)"),
    ("nl", "Nederlands (Dutch)"),
    ("pl", "Polski (Polish)"),
    ("pt", "Português (Portuguese)"),
    ("pt_BR", "Português do Brasil (Brazilian Portuguese)"),
    ("ro", "Română (Romanian)"),
    ("ru", "Русский (Russian)"),
    ("sv", "Svenska (Swedish)"),
    ("tr", "Türkçe (Turkish)"),
    ("uk", "Українська (Ukrainian)"),
    ("zh_CN", "简体中文 (Simplified Chinese)"),
]

DEFAULTS: dict[str, Any] = {
    # Personal info
    "translator_name": "",
    "translator_email": "",
    "language": "en",
    "team": "",

    # Translation
    "default_engine": "lingva",
    "source_language": "en",
    "target_language": "sv",
    "formality": "default",  # default / formal / informal

    # Appearance
    "color_scheme": "default",  # default / light / dark
    "editor_font_size": 12,

    # Build
    "auto_compile_on_save": False,

    # Internal
    "first_run_complete": False,
}


def _detect_system_language() -> str:
    """Try to detect the system language and return a matching code."""
    try:
        loc = locale.getlocale()[0] or ""
    except Exception:
        loc = ""
    # Try exact match first, then prefix
    for code, _ in SUPPORTED_LANGUAGES:
        if loc.startswith(code):
            return code
    return "en"


class Settings:
    """Application settings backed by a JSON file."""

    _instance: Settings | None = None

    def __init__(self):
        self._data: dict[str, Any] = dict(DEFAULTS)
        self._load()

    @classmethod
    def get(cls) -> Settings:
        if cls._instance is None:
            cls._instance = Settings()
        return cls._instance

    @classmethod
    def reset_instance(cls):
        cls._instance = None

    # ── Public API ────────────────────────────────────────────────

    def __getitem__(self, key: str) -> Any:
        return self._data.get(key, DEFAULTS.get(key))

    def __setitem__(self, key: str, value: Any):
        self._data[key] = value

    def get_value(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default if default is not None else DEFAULTS.get(key))

    def set_value(self, key: str, value: Any):
        self._data[key] = value

    @property
    def exists(self) -> bool:
        return _SETTINGS_FILE.exists()

    @property
    def first_run_complete(self) -> bool:
        return self._data.get("first_run_complete", False)

    def save(self):
        _SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        _SETTINGS_FILE.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2), "utf-8"
        )

    # ── Convenience properties ────────────────────────────────────

    @property
    def last_translator(self) -> str:
        name = self._data.get("translator_name", "")
        email = self._data.get("translator_email", "")
        if name and email:
            return f"{name} <{email}>"
        return name or email or ""

    @property
    def language_team(self) -> str:
        team = self._data.get("team", "")
        lang = self._data.get("language", "")
        if team:
            return team
        # Find language name
        for code, label in SUPPORTED_LANGUAGES:
            if code == lang:
                # Extract short name before parentheses
                short = label.split("(")[0].strip() if "(" in label else label
                return short
        return ""

    # ── Private ───────────────────────────────────────────────────

    def _load(self):
        if _SETTINGS_FILE.exists():
            try:
                stored = json.loads(_SETTINGS_FILE.read_text("utf-8"))
                self._data.update(stored)
            except Exception:
                pass
        else:
            # Set system language as default
            sys_lang = _detect_system_language()
            self._data["language"] = sys_lang
            self._data["target_language"] = sys_lang
