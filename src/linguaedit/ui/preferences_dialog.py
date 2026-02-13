"""Preferences dialog — QDialog with tabbed settings."""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QWidget, QFormLayout,
    QLineEdit, QComboBox, QSpinBox, QGroupBox, QDialogButtonBox,
    QCheckBox, QLabel,
)
from PySide6.QtCore import Qt, QLocale
from PySide6.QtGui import QIcon, QPixmap, QPainter, QFont

from linguaedit.services.settings import Settings, SUPPORTED_LANGUAGES
from linguaedit.services.translator import ENGINES
from linguaedit.services import keystore
from linguaedit.app import _find_translations_dir


# Country-flag emoji → QIcon via QPainter text rendering
_FLAG_MAP: dict[str, str] = {
    "ar": "🇸🇦", "ca": "🇪🇸", "cs": "🇨🇿", "da": "🇩🇰", "de": "🇩🇪",
    "el": "🇬🇷", "en": "🇬🇧", "es": "🇪🇸", "fi": "🇫🇮", "fr": "🇫🇷",
    "hu": "🇭🇺", "it": "🇮🇹", "ja": "🇯🇵", "ko": "🇰🇷", "nb": "🇳🇴",
    "nl": "🇳🇱", "pl": "🇵🇱", "pt": "🇵🇹", "pt_BR": "🇧🇷", "ro": "🇷🇴",
    "ru": "🇷🇺", "sv": "🇸🇪", "tr": "🇹🇷", "uk": "🇺🇦",
    "zh_CN": "🇨🇳",
}

def _flag_icon(code: str) -> QIcon:
    """Render a flag emoji to a QIcon."""
    flag = _FLAG_MAP.get(code, "🏳️")
    pix = QPixmap(24, 24)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setFont(QFont("Apple Color Emoji", 16))
    p.drawText(pix.rect(), Qt.AlignCenter, flag)
    p.end()
    return QIcon(pix)


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
        tabs.addTab(self._build_security_tab(), self.tr("Security"))
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
        self._lang_combo.setIconSize(self._lang_combo.sizeHint())  # decent flag size
        from PySide6.QtCore import QSize
        self._lang_combo.setIconSize(QSize(20, 20))

        # Build available languages from .qm files + English (always available)
        translations_dir = _find_translations_dir()
        available_codes = {"en"}  # English always present
        for qm in translations_dir.glob("linguaedit_*.qm"):
            code = qm.stem.replace("linguaedit_", "")
            available_codes.add(code)

        # Build lookup from SUPPORTED_LANGUAGES
        lang_lookup = {code: label for code, label in SUPPORTED_LANGUAGES}

        # Sort: English first, then alphabetically by label
        lang_items = []
        for code in available_codes:
            label = lang_lookup.get(code, code)
            lang_items.append((code, label))
        lang_items.sort(key=lambda x: (x[0] != "en", x[1]))

        current_lang = self._settings["language"]
        for i, (code, label) in enumerate(lang_items):
            self._lang_combo.addItem(_flag_icon(code), label, code)
            if code == current_lang:
                self._lang_combo.setCurrentIndex(i)
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
        
        # Feature 6: Inline editing
        self._inline_editing_check = QCheckBox(self.tr("Enable inline editing"))
        self._inline_editing_check.setChecked(self._settings.get_value("inline_editing_enabled", False))
        self._inline_editing_check.setToolTip(self.tr("Double-click to edit translations directly in the list"))
        form.addRow("", self._inline_editing_check)
        
        # Feature 7: Character counter
        self._char_counter_check = QCheckBox(self.tr("Show character counter"))
        self._char_counter_check.setChecked(self._settings.get_value("show_character_counter", True))
        form.addRow("", self._char_counter_check)
        
        self._char_limit_spin = QSpinBox()
        self._char_limit_spin.setMinimum(0)
        self._char_limit_spin.setMaximum(10000)
        self._char_limit_spin.setValue(self._settings.get_value("character_limit", 280))
        self._char_limit_spin.setSuffix(self.tr(" characters"))
        form.addRow(self.tr("Character limit:"), self._char_limit_spin)

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

    def _build_security_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        # Keyring backend status
        backend = keystore.backend_name()
        secure = keystore.is_secure_backend()
        status_icon = "🔒" if secure else "⚠️"
        status_text = f"{status_icon} {backend}"
        backend_label = QLabel(status_text)
        backend_label.setWordWrap(True)
        form.addRow(self.tr("Credential storage:"), backend_label)

        if not secure:
            hint = QLabel(self.tr(
                "No system keychain detected. Credentials are stored in an "
                "encrypted file with a master password.\n\n"
                "For better security, install:\n"
                "• macOS: Built-in (Keychain)\n"
                "• Windows: pip install keyring\n"
                "• Linux: pip install secretstorage"
            ))
            hint.setWordWrap(True)
            hint.setStyleSheet("color: #b36b00; font-size: 11px;")
            form.addRow("", hint)
        else:
            hint = QLabel(self.tr(
                "Your credentials are securely stored in the system keychain."
            ))
            hint.setWordWrap(True)
            hint.setStyleSheet("color: #2a7e3b; font-size: 11px;")
            form.addRow("", hint)

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
        
        # New settings
        s["inline_editing_enabled"] = self._inline_editing_check.isChecked()
        s["show_character_counter"] = self._char_counter_check.isChecked()
        s["character_limit"] = self._char_limit_spin.value()

        s.save()

        # Apply theme immediately
        if hasattr(self._parent_win, '_apply_settings'):
            self._parent_win._apply_settings()
