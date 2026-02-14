"""LinguaEdit PySide6 application entry point."""

from __future__ import annotations

import locale
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTranslator, QLocale, QLibraryInfo

from linguaedit import APP_ID
from linguaedit.services.settings import Settings


def _find_translations_dir() -> Path:
    """Find the translations directory, checking multiple locations."""
    candidates = [
        Path(__file__).parent / "translations",                 # installed (inside package) & dev
    ]
    # PyInstaller frozen bundle: files are in sys._MEIPASS
    if getattr(sys, 'frozen', False):
        meipass = Path(sys._MEIPASS)  # type: ignore[attr-defined]
        candidates.insert(0, meipass / "linguaedit" / "translations")
    # Also check relative to the package install location via importlib
    try:
        import importlib.resources as _res
        pkg_dir = Path(_res.files("linguaedit").__fspath__())  # type: ignore[union-attr]
        candidates.append(pkg_dir / "translations")
    except Exception:
        pass
    candidates += [
        Path(sys.prefix) / "share" / "linguaedit" / "translations",
        Path(sys.prefix) / "Lib" / "site-packages" / "linguaedit" / "translations",  # Windows pip
    ]
    for d in candidates:
        if d.is_dir():
            return d
    return candidates[0]


class LinguaEditApp:
    """Main application wrapper."""

    def __init__(self, argv: list[str]):
        self._argv = argv

        # Fix macOS menu bar app name (must be before QApplication)
        if sys.platform == 'darwin':
            try:
                from Foundation import NSBundle
                bundle = NSBundle.mainBundle()
                info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
                info['CFBundleName'] = 'LinguaEdit'
            except ImportError:
                pass
            # Also patch argv[0] – Qt uses this for the menu title on macOS
            if argv:
                argv[0] = 'LinguaEdit'

        # Work around SIGSEGV in libqcocoa.dylib accessibility bridge (Qt 6 bug):
        # macOS accessibility daemon queries widgets during creation/destruction,
        # hitting dangling pointers in the Cocoa platform plugin.
        # Users who need accessibility can set QT_ACCESSIBILITY=1 to re-enable.
        if sys.platform == 'darwin':
            import os
            os.environ.setdefault("QT_ACCESSIBILITY", "0")

        self._qt_app = QApplication(argv)
        self._qt_app.setApplicationName("LinguaEdit")
        self._qt_app.setApplicationDisplayName("LinguaEdit")
        self._qt_app.setOrganizationName("danielnylander")
        self._qt_app.setOrganizationDomain("danielnylander.se")
        self._qt_app.setDesktopFileName(APP_ID)

        # Load translations
        self._translator = QTranslator()
        self._qt_translator = QTranslator()
        self._load_translations()

    def _load_translations(self):
        """Load Qt and app translations for current locale."""
        import logging
        log = logging.getLogger("linguaedit.i18n")

        settings = Settings.get()
        lang = settings["language"]
        log.info("Settings language: %s", lang)

        # If language is "en", try to detect system language
        if lang == "en":
            sys_lang = QLocale.system().name()[:2]
            log.info("System locale: %s", sys_lang)
            if sys_lang in ("C", "en", ""):
                if sys.platform == "darwin":
                    try:
                        import subprocess
                        result = subprocess.run(
                            ["defaults", "read", "-g", "AppleLanguages"],
                            capture_output=True, text=True, timeout=2
                        )
                        for line in result.stdout.splitlines():
                            line = line.strip().strip('",')
                            if line and len(line) >= 2 and not line.startswith("(") and not line.startswith(")"):
                                sys_lang = line[:2]
                                break
                    except Exception:
                        pass
                elif sys.platform == "win32":
                    # Windows: try ctypes GetUserDefaultUILanguage
                    try:
                        import ctypes
                        lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
                        # lang_id is a LANGID; primary language is low 10 bits
                        # Map common primary language IDs
                        _WIN_LANG_MAP = {
                            0x1D: "sv", 0x06: "da", 0x14: "no", 0x0B: "fi",
                            0x07: "de", 0x0C: "fr", 0x0A: "es", 0x10: "it",
                            0x13: "nl", 0x15: "pl", 0x05: "cs", 0x19: "ru",
                            0x22: "uk", 0x11: "ja", 0x12: "ko", 0x04: "zh",
                            0x16: "pt", 0x01: "ar",
                        }
                        primary = lang_id & 0x3FF
                        if primary in _WIN_LANG_MAP:
                            sys_lang = _WIN_LANG_MAP[primary]
                            log.info("Windows UI language: 0x%04x -> %s", lang_id, sys_lang)
                    except Exception:
                        pass
                # Also try locale module as fallback (works on all platforms)
                if sys_lang in ("C", "en", ""):
                    try:
                        loc = locale.getdefaultlocale()[0] or ""
                        if len(loc) >= 2:
                            loc_lang = loc[:2]
                            if loc_lang not in ("C", "en", ""):
                                sys_lang = loc_lang
                                log.info("Fallback locale: %s", sys_lang)
                    except Exception:
                        pass
            translations_dir = _find_translations_dir()
            sys_qm = translations_dir / f"linguaedit_{sys_lang}.qm"
            if sys_qm.exists():
                lang = sys_lang
                log.info("Auto-detected language: %s", lang)

        qt_locale = QLocale(lang)

        # Load Qt's own translations (buttons, dialogs, etc.)
        qt_translations_path = QLibraryInfo.path(QLibraryInfo.TranslationsPath)
        if self._qt_translator.load(qt_locale, "qtbase", "_", qt_translations_path):
            self._qt_app.installTranslator(self._qt_translator)
            log.info("Loaded Qt base translations for %s", lang)

        # Load LinguaEdit translations
        translations_dir = _find_translations_dir()
        log.info("Translations dir: %s (exists: %s)", translations_dir, translations_dir.is_dir())
        if translations_dir.is_dir():
            qm_files = list(translations_dir.glob("*.qm"))
            log.info("Available .qm files: %s", [f.name for f in qm_files])

        qm_file = translations_dir / f"linguaedit_{lang}.qm"
        log.info("Looking for: %s (exists: %s)", qm_file, qm_file.exists())
        # Use forward slashes for QTranslator.load() — Qt expects them on all platforms
        qm_path_str = str(qm_file).replace("\\", "/")
        if qm_file.exists() and self._translator.load(qm_path_str):
            self._qt_app.installTranslator(self._translator)
            log.info("✓ Loaded translations: %s", qm_file.name)
        elif qm_file.exists():
            log.warning("✗ .qm file exists but QTranslator.load() failed: %s", qm_file)
        else:
            log.warning("✗ Translation file not found: %s", qm_file)

    def run(self) -> int:
        settings = Settings.get()

        # Determine file to open from argv
        file_path = None
        if len(self._argv) > 1:
            file_path = self._argv[1]

        if not settings.first_run_complete:
            from linguaedit.ui.welcome_dialog import WelcomeDialog
            wizard = WelcomeDialog(on_finish=lambda: self._show_main_window(file_path))
            wizard.show()
        else:
            self._show_main_window(file_path)

        return self._qt_app.exec()

    def _show_main_window(self, file_path: str | None = None):
        from linguaedit.ui.window import LinguaEditWindow
        self._win = LinguaEditWindow()
        if file_path:
            self._win._load_file(file_path)
        self._win.show()


def main():
    import logging
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    app = LinguaEditApp(sys.argv)
    sys.exit(app.run())


if __name__ == "__main__":
    main()
