"""Preferences dialog — QDialog with tabbed settings."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QWidget, QFormLayout,
    QLineEdit, QComboBox, QSpinBox, QGroupBox, QDialogButtonBox,
    QCheckBox,
)
from PySide6.QtCore import Qt

from linguaedit.services.settings import Settings, SUPPORTED_LANGUAGES
from linguaedit.services.translator import ENGINES


class PreferencesDialog(QDialog):
    """Full preferences dialog mirroring the welcome wizard settings."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Preferences"))
        self.setModal(True)
        self.resize(500, 450)
        self._parent_win = parent
        self._settings = Settings.get()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        tabs = QTabWidget()
        tabs.addTab(self._build_personal_tab(), self.tr("Personal"))
        tabs.addTab(self._build_translation_tab(), self.tr("Translation"))
        tabs.addTab(self._build_appearance_tab(), self.tr("Appearance"))
        layout.addWidget(tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _build_personal_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
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
        form.addRow(self.tr("Team:"), self._team_edit)

        return page

    def _build_translation_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
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

        self._source_edit = QLineEdit(self._settings["source_language"])
        form.addRow(self.tr("Source language:"), self._source_edit)

        self._target_edit = QLineEdit(self._settings["target_language"])
        form.addRow(self.tr("Target language:"), self._target_edit)

        self._auto_compile_check = QCheckBox(self.tr("Auto-compile on save"))
        self._auto_compile_check.setChecked(self._settings.get_value("auto_compile_on_save", False))
        self._auto_compile_check.setToolTip(self.tr("Automatically compile .mo/.qm after saving"))
        form.addRow("", self._auto_compile_check)

        self._formality_combo = QComboBox()
        self._formality_combo.addItems([self.tr("Default"), self.tr("Formal"), self.tr("Informal")])
        formality_map = {"default": 0, "formal": 1, "informal": 2}
        self._formality_combo.setCurrentIndex(formality_map.get(self._settings["formality"], 0))
        form.addRow(self.tr("Formality level:"), self._formality_combo)

        return page

    def _build_appearance_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)

        self._theme_combo = QComboBox()
        self._theme_combo.addItems([self.tr("System default"), self.tr("Light"), self.tr("Dark")])
        scheme_map = {"default": 0, "light": 1, "dark": 2}
        self._theme_combo.setCurrentIndex(scheme_map.get(self._settings["color_scheme"], 0))
        form.addRow(self.tr("Theme:"), self._theme_combo)

        self._font_spin = QSpinBox()
        self._font_spin.setRange(8, 32)
        self._font_spin.setValue(self._settings["editor_font_size"])
        form.addRow(self.tr("Editor font size:"), self._font_spin)

        return page

    def _on_accept(self):
        self._save()
        self.accept()

    def _save(self):
        s = self._settings
        s["translator_name"] = self._name_edit.text().strip()
        s["translator_email"] = self._email_edit.text().strip()

        lang_data = self._lang_combo.currentData()
        if lang_data:
            s["language"] = lang_data

        s["team"] = self._team_edit.text().strip()

        engine_key = self._engine_combo.currentData()
        if engine_key:
            s["default_engine"] = engine_key

        s["source_language"] = self._source_edit.text().strip() or "en"
        s["target_language"] = self._target_edit.text().strip() or "sv"

        s["auto_compile_on_save"] = self._auto_compile_check.isChecked()

        formality_vals = ["default", "formal", "informal"]
        s["formality"] = formality_vals[self._formality_combo.currentIndex()]

        scheme_vals = ["default", "light", "dark"]
        s["color_scheme"] = scheme_vals[self._theme_combo.currentIndex()]
        s["editor_font_size"] = self._font_spin.value()

        s.save()

        # Apply theme immediately
        if hasattr(self._parent_win, '_apply_settings'):
            self._parent_win._apply_settings()
