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
        Path(__file__).parent / "translations",                 # installed (inside package)
        Path(__file__).parent.parent.parent / "translations",  # dev: repo root
        Path(sys.prefix) / "share" / "linguaedit" / "translations",
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
        settings = Settings.get()
        lang = settings["language"]

        # If language is "en", also check system locale for a better match
        if lang == "en":
            # Try QLocale first, then macOS defaults, then Python locale
            sys_lang = QLocale.system().name()[:2]
            if sys_lang in ("C", "en", ""):
                try:
                    import subprocess
                    result = subprocess.run(
                        ["defaults", "read", "-g", "AppleLanguages"],
                        capture_output=True, text=True, timeout=2
                    )
                    # Parse first language from plist output like '(\n    "sv-SE",\n    "en-SE"\n)'
                    for line in result.stdout.splitlines():
                        line = line.strip().strip('",')
                        if line and len(line) >= 2 and not line.startswith("(") and not line.startswith(")"):
                            sys_lang = line[:2]
                            break
                except Exception:
                    pass
            translations_dir = _find_translations_dir()
            sys_qm = translations_dir / f"linguaedit_{sys_lang}.qm"
            if sys_qm.exists():
                lang = sys_lang

        qt_locale = QLocale(lang)

        # Load Qt's own translations (buttons, dialogs, etc.)
        qt_translations_path = QLibraryInfo.path(QLibraryInfo.TranslationsPath)
        if self._qt_translator.load(qt_locale, "qtbase", "_", qt_translations_path):
            self._qt_app.installTranslator(self._qt_translator)

        # Load LinguaEdit translations
        translations_dir = _find_translations_dir()
        qm_file = translations_dir / f"linguaedit_{lang}.qm"
        if qm_file.exists() and self._translator.load(str(qm_file)):
            self._qt_app.installTranslator(self._translator)

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
    app = LinguaEditApp(sys.argv)
    sys.exit(app.run())


if __name__ == "__main__":
    main()
