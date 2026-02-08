"""First-run welcome wizard — QDialog with stacked pages."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QStackedWidget, QComboBox, QLineEdit, QSpinBox, QWidget,
    QFormLayout, QGroupBox,
)
from PySide6.QtCore import Qt

from linguaedit import __version__
from linguaedit.services.settings import Settings, SUPPORTED_LANGUAGES, DEFAULTS
from linguaedit.services.translator import ENGINES


class WelcomeDialog(QDialog):
    """Five-page first-run wizard."""

    def __init__(self, on_finish=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Welcome to LinguaEdit"))
        self.resize(620, 520)
        self.setModal(True)
        self._settings = Settings.get()
        self._on_finish = on_finish
        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Stacked widget (carousel replacement)
        self._stack = QStackedWidget()
        layout.addWidget(self._stack, 1)

        # Navigation buttons
        nav = QHBoxLayout()
        nav.addStretch()
        self._back_btn = QPushButton(self.tr("Back"))
        self._back_btn.clicked.connect(self._on_back)
        self._back_btn.setEnabled(False)
        nav.addWidget(self._back_btn)

        self._next_btn = QPushButton(self.tr("Next"))
        self._next_btn.setDefault(True)
        self._next_btn.clicked.connect(self._on_next)
        nav.addWidget(self._next_btn)
        nav.addStretch()
        layout.addLayout(nav)

        # Build pages
        self._stack.addWidget(self._build_page_welcome())
        self._stack.addWidget(self._build_page_personal())
        self._stack.addWidget(self._build_page_translation())
        self._stack.addWidget(self._build_page_appearance())
        self._stack.addWidget(self._build_page_done())

        self._stack.currentChanged.connect(self._on_page_changed)

    # ── Page 1: Welcome ───────────────────────────────────────────

    def _build_page_welcome(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignCenter)

        title = QLabel(self.tr("Welcome to LinguaEdit"))
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        version = QLabel(f"Version {__version__}")
        version.setStyleSheet("color: gray;")
        version.setAlignment(Qt.AlignCenter)
        layout.addWidget(version)

        desc = QLabel(self.tr(
            "LinguaEdit is a modern translation editor for PO, TS, JSON, XLIFF,\n"
            "Android XML, ARB, PHP, and YAML files.\n\n"
            "Features include AI-powered pre-translation, translation memory,\n"
            "quality assurance, spell checking, and platform integration."
        ))
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)
        layout.addWidget(desc)

        return page

    # ── Page 2: Personal info ─────────────────────────────────────

    def _build_page_personal(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        group = QGroupBox(self.tr("Personal Information"))
        form = QFormLayout(group)
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        self._name_edit = QLineEdit(self._settings["translator_name"])
        form.addRow(self.tr("Name:"), self._name_edit)

        self._email_edit = QLineEdit(self._settings["translator_email"])
        form.addRow(self.tr("Email:"), self._email_edit)

        self._lang_combo = QComboBox()
        for code, label in SUPPORTED_LANGUAGES:
            self._lang_combo.addItem(label, code)
        current_lang = self._settings["language"]
        for i, (code, _) in enumerate(SUPPORTED_LANGUAGES):
            if code == current_lang:
                self._lang_combo.setCurrentIndex(i)
                break
        form.addRow(self.tr("Language / Locale:"), self._lang_combo)

        self._team_edit = QLineEdit(self._settings["team"])
        form.addRow(self.tr("Team (optional):"), self._team_edit)

        layout.addWidget(group)
        layout.addStretch()
        return page

    # ── Page 3: Translation settings ──────────────────────────────

    def _build_page_translation(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        group = QGroupBox(self.tr("Translation Settings"))
        form = QFormLayout(group)
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        self._engine_combo = QComboBox()
        engine_keys = list(ENGINES.keys())
        for k in engine_keys:
            self._engine_combo.addItem(ENGINES[k]["name"], k)
        current_engine = self._settings["default_engine"]
        for i, k in enumerate(engine_keys):
            if k == current_engine:
                self._engine_combo.setCurrentIndex(i)
                break
        form.addRow(self.tr("Default engine:"), self._engine_combo)

        self._source_lang_edit = QLineEdit(self._settings["source_language"])
        form.addRow(self.tr("Source language:"), self._source_lang_edit)

        self._target_lang_edit = QLineEdit(self._settings["target_language"])
        form.addRow(self.tr("Target language:"), self._target_lang_edit)

        self._formality_combo = QComboBox()
        self._formality_combo.addItems([self.tr("Default"), self.tr("Formal"), self.tr("Informal")])
        formality_map = {"default": 0, "formal": 1, "informal": 2}
        self._formality_combo.setCurrentIndex(formality_map.get(self._settings["formality"], 0))
        form.addRow(self.tr("Formality level:"), self._formality_combo)

        layout.addWidget(group)
        layout.addStretch()
        return page

    # ── Page 4: Appearance ────────────────────────────────────────

    def _build_page_appearance(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        group = QGroupBox(self.tr("Appearance"))
        form = QFormLayout(group)

        self._theme_combo = QComboBox()
        self._theme_combo.addItems([self.tr("System default"), self.tr("Light"), self.tr("Dark")])
        scheme_map = {"default": 0, "light": 1, "dark": 2}
        self._theme_combo.setCurrentIndex(scheme_map.get(self._settings["color_scheme"], 0))
        form.addRow(self.tr("Theme:"), self._theme_combo)

        self._font_spin = QSpinBox()
        self._font_spin.setRange(8, 32)
        self._font_spin.setValue(self._settings["editor_font_size"])
        form.addRow(self.tr("Editor font size:"), self._font_spin)

        layout.addWidget(group)
        layout.addStretch()
        return page

    # ── Page 5: Done ──────────────────────────────────────────────

    def _build_page_done(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignCenter)

        title = QLabel(self.tr("You're all set!"))
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        self._summary_label = QLabel()
        self._summary_label.setWordWrap(True)
        layout.addWidget(self._summary_label)

        return page

    # ── Navigation ────────────────────────────────────────────────

    def _on_page_changed(self, index):
        self._back_btn.setEnabled(index > 0)
        if index == 4:
            self._next_btn.setText(self.tr("Start translating!"))
            self._update_summary()
        else:
            self._next_btn.setText(self.tr("Next"))

    def _on_back(self):
        idx = self._stack.currentIndex()
        if idx > 0:
            self._stack.setCurrentIndex(idx - 1)

    def _on_next(self):
        idx = self._stack.currentIndex()
        if idx < 4:
            self._stack.setCurrentIndex(idx + 1)
        else:
            self._save_and_finish()

    def _update_summary(self):
        self._collect_values()

        engine_key = self._engine_combo.currentData()
        engine_name = ENGINES.get(engine_key, {}).get("name", "Lingva")

        lang_idx = self._lang_combo.currentIndex()
        lang_name = SUPPORTED_LANGUAGES[lang_idx][1] if lang_idx < len(SUPPORTED_LANGUAGES) else "English"

        themes = [self.tr("System default"), self.tr("Light"), self.tr("Dark")]
        theme = themes[self._theme_combo.currentIndex()]

        lines = [
            f"👤  {self._name_edit.text() or '(not set)'} <{self._email_edit.text() or '...'}>",
            f"🌍  Language: {lang_name}",
            f"🤖  Engine: {engine_name}",
            f"📝  {self._source_lang_edit.text()} → {self._target_lang_edit.text()}",
            f"🎨  Theme: {theme}, Font: {self._font_spin.value()}pt",
        ]
        if self._team_edit.text():
            lines.insert(2, f"👥  Team: {self._team_edit.text()}")

        self._summary_label.setText("\n".join(lines))

    def _collect_values(self):
        s = self._settings
        s["translator_name"] = self._name_edit.text().strip()
        s["translator_email"] = self._email_edit.text().strip()

        lang_idx = self._lang_combo.currentIndex()
        if lang_idx < len(SUPPORTED_LANGUAGES):
            s["language"] = SUPPORTED_LANGUAGES[lang_idx][0]

        s["team"] = self._team_edit.text().strip()

        engine_key = self._engine_combo.currentData()
        if engine_key:
            s["default_engine"] = engine_key

        s["source_language"] = self._source_lang_edit.text().strip() or "en"
        s["target_language"] = self._target_lang_edit.text().strip() or "sv"

        formality_vals = ["default", "formal", "informal"]
        s["formality"] = formality_vals[self._formality_combo.currentIndex()]

        scheme_vals = ["default", "light", "dark"]
        s["color_scheme"] = scheme_vals[self._theme_combo.currentIndex()]

        s["editor_font_size"] = self._font_spin.value()

    def _save_and_finish(self):
        self._collect_values()
        self._settings["first_run_complete"] = True
        self._settings.save()
        self.close()
        if self._on_finish:
            self._on_finish()
