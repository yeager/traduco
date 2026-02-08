"""Platform settings dialog for Transifex, Weblate, and Crowdin."""
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import threading

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QFormLayout, QLineEdit, QPushButton, QLabel, QGroupBox,
)
from PySide6.QtCore import Qt, Signal, QObject, QCoreApplication

from linguaedit.services.platforms import (
    load_platform_config, save_platform_config,
    TransifexConfig, WeblateConfig, CrowdinConfig,
    transifex_test_connection, weblate_test_connection, crowdin_test_connection,
    PlatformError,
)
from linguaedit.services.keystore import backend_name, is_secure_backend


class _SignalHelper(QObject):
    """Helper to emit signals from worker threads."""
    status_update = Signal(QLabel, str)
    enable_button = Signal(QPushButton, bool)


class PlatformSettingsDialog(QDialog):
    """Settings dialog for translation platform integrations."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Platform Settings"))
        self.setModal(True)
        self.resize(600, 500)

        self._config = load_platform_config()
        self._entries: dict[str, dict[str, QLineEdit]] = {}
        self._signals = _SignalHelper()
        self._signals.status_update.connect(lambda lbl, txt: lbl.setText(txt))
        self._signals.enable_button.connect(lambda btn, val: btn.setEnabled(val))

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Security banner
        name = backend_name()
        secure = is_secure_backend()
        if secure:
            banner = QLabel(self.tr("🔒 Tokens stored in %1").replace("%1", name))
        else:
            banner = QLabel(
                self.tr("⚠️ No system keychain — tokens stored with basic obfuscation. "
                         "Install 'secretstorage' for proper security.")
            )
        banner.setWordWrap(True)
        layout.addWidget(banner)

        tabs = QTabWidget()
        tabs.addTab(self._build_transifex_tab(), self.tr("Transifex"))
        tabs.addTab(self._build_weblate_tab(), self.tr("Weblate"))
        tabs.addTab(self._build_crowdin_tab(), self.tr("Crowdin"))
        layout.addWidget(tabs)

    # ── Transifex ─────────────────────────────────────────────────

    def _build_transifex_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        group = QGroupBox(self.tr("Transifex API"))
        form = QFormLayout(group)

        cfg = self._config.get("transifex", {})
        fields = {}

        token_edit = QLineEdit(cfg.get("api_token", ""))
        token_edit.setEchoMode(QLineEdit.Password)
        fields["api_token"] = token_edit
        form.addRow(self.tr("API Token:"), token_edit)

        org_edit = QLineEdit(cfg.get("organization", ""))
        fields["organization"] = org_edit
        form.addRow(self.tr("Organization:"), org_edit)

        project_edit = QLineEdit(cfg.get("project", ""))
        fields["project"] = project_edit
        form.addRow(self.tr("Project:"), project_edit)

        url_edit = QLineEdit(cfg.get("base_url", "https://rest.api.transifex.com"))
        fields["base_url"] = url_edit
        form.addRow(self.tr("Base URL:"), url_edit)

        self._entries["transifex"] = fields
        layout.addWidget(group)

        # Buttons
        btn_row = QHBoxLayout()
        self._tx_status = QLabel("")
        btn_row.addWidget(self._tx_status, 1)

        test_btn = QPushButton(self.tr("Test Connection"))
        test_btn.clicked.connect(lambda: self._on_test_transifex(test_btn))
        btn_row.addWidget(test_btn)

        save_btn = QPushButton(self.tr("Save"))
        save_btn.clicked.connect(self._on_save_transifex)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)
        layout.addStretch()
        return page

    def _on_test_transifex(self, btn):
        fields = self._entries["transifex"]
        config = TransifexConfig(
            api_token=fields["api_token"].text(),
            organization=fields["organization"].text(),
            project=fields["project"].text(),
            base_url=fields["base_url"].text(),
        )
        self._tx_status.setText(self.tr("Testing…"))
        btn.setEnabled(False)

        def do_test():
            try:
                name = transifex_test_connection(config)
                self._signals.status_update.emit(
                    self._tx_status, self.tr("✓ Connected: %1").replace("%1", name))
            except PlatformError as e:
                self._signals.status_update.emit(
                    self._tx_status, self.tr("✗ %1").replace("%1", str(e)))
            finally:
                self._signals.enable_button.emit(btn, True)

        threading.Thread(target=do_test, daemon=True).start()

    def _on_save_transifex(self):
        fields = self._entries["transifex"]
        self._config["transifex"] = {
            "api_token": fields["api_token"].text(),
            "organization": fields["organization"].text(),
            "project": fields["project"].text(),
            "base_url": fields["base_url"].text(),
        }
        save_platform_config(self._config)
        self._tx_status.setText(self.tr("✓ Saved"))

    # ── Weblate ───────────────────────────────────────────────────

    def _build_weblate_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        group = QGroupBox(self.tr("Weblate API"))
        form = QFormLayout(group)

        cfg = self._config.get("weblate", {})
        fields = {}

        url_edit = QLineEdit(cfg.get("api_url", "https://hosted.weblate.org/api/"))
        fields["api_url"] = url_edit
        form.addRow(self.tr("API URL:"), url_edit)

        key_edit = QLineEdit(cfg.get("api_key", ""))
        key_edit.setEchoMode(QLineEdit.Password)
        fields["api_key"] = key_edit
        form.addRow(self.tr("API Key:"), key_edit)

        project_edit = QLineEdit(cfg.get("project", ""))
        fields["project"] = project_edit
        form.addRow(self.tr("Project:"), project_edit)

        comp_edit = QLineEdit(cfg.get("component", ""))
        fields["component"] = comp_edit
        form.addRow(self.tr("Component:"), comp_edit)

        self._entries["weblate"] = fields
        layout.addWidget(group)

        btn_row = QHBoxLayout()
        self._wb_status = QLabel("")
        btn_row.addWidget(self._wb_status, 1)

        test_btn = QPushButton(self.tr("Test Connection"))
        test_btn.clicked.connect(lambda: self._on_test_weblate(test_btn))
        btn_row.addWidget(test_btn)

        save_btn = QPushButton(self.tr("Save"))
        save_btn.clicked.connect(self._on_save_weblate)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)
        layout.addStretch()
        return page

    def _on_test_weblate(self, btn):
        fields = self._entries["weblate"]
        config = WeblateConfig(
            api_url=fields["api_url"].text(),
            api_key=fields["api_key"].text(),
            project=fields["project"].text(),
            component=fields["component"].text(),
        )
        self._wb_status.setText(self.tr("Testing…"))
        btn.setEnabled(False)

        def do_test():
            try:
                name = weblate_test_connection(config)
                self._signals.status_update.emit(
                    self._wb_status, self.tr("✓ Connected: %1").replace("%1", name))
            except PlatformError as e:
                self._signals.status_update.emit(
                    self._wb_status, self.tr("✗ %1").replace("%1", str(e)))
            finally:
                self._signals.enable_button.emit(btn, True)

        threading.Thread(target=do_test, daemon=True).start()

    def _on_save_weblate(self):
        fields = self._entries["weblate"]
        self._config["weblate"] = {
            "api_url": fields["api_url"].text(),
            "api_key": fields["api_key"].text(),
            "project": fields["project"].text(),
            "component": fields["component"].text(),
        }
        save_platform_config(self._config)
        self._wb_status.setText(self.tr("✓ Saved"))

    # ── Crowdin ───────────────────────────────────────────────────

    def _build_crowdin_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        group = QGroupBox(self.tr("Crowdin API"))
        form = QFormLayout(group)

        cfg = self._config.get("crowdin", {})
        fields = {}

        token_edit = QLineEdit(cfg.get("api_token", ""))
        token_edit.setEchoMode(QLineEdit.Password)
        fields["api_token"] = token_edit
        form.addRow(self.tr("API Token:"), token_edit)

        pid_edit = QLineEdit(str(cfg.get("project_id", "")))
        fields["project_id"] = pid_edit
        form.addRow(self.tr("Project ID:"), pid_edit)

        url_edit = QLineEdit(cfg.get("base_url", "https://api.crowdin.com/api/v2"))
        fields["base_url"] = url_edit
        form.addRow(self.tr("Base URL:"), url_edit)

        self._entries["crowdin"] = fields
        layout.addWidget(group)

        btn_row = QHBoxLayout()
        self._cr_status = QLabel("")
        btn_row.addWidget(self._cr_status, 1)

        test_btn = QPushButton(self.tr("Test Connection"))
        test_btn.clicked.connect(lambda: self._on_test_crowdin(test_btn))
        btn_row.addWidget(test_btn)

        save_btn = QPushButton(self.tr("Save"))
        save_btn.clicked.connect(self._on_save_crowdin)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)
        layout.addStretch()
        return page

    def _on_test_crowdin(self, btn):
        fields = self._entries["crowdin"]
        try:
            pid = int(fields["project_id"].text())
        except ValueError:
            self._cr_status.setText(self.tr("✗ Project ID must be a number"))
            return
        config = CrowdinConfig(
            api_token=fields["api_token"].text(),
            project_id=pid,
            base_url=fields["base_url"].text(),
        )
        self._cr_status.setText(self.tr("Testing…"))
        btn.setEnabled(False)

        def do_test():
            try:
                name = crowdin_test_connection(config)
                self._signals.status_update.emit(
                    self._cr_status, self.tr("✓ Connected: %1").replace("%1", name))
            except PlatformError as e:
                self._signals.status_update.emit(
                    self._cr_status, self.tr("✗ %1").replace("%1", str(e)))
            finally:
                self._signals.enable_button.emit(btn, True)

        threading.Thread(target=do_test, daemon=True).start()

    def _on_save_crowdin(self):
        fields = self._entries["crowdin"]
        try:
            pid = int(fields["project_id"].text())
        except ValueError:
            pid = 0
        self._config["crowdin"] = {
            "api_token": fields["api_token"].text(),
            "project_id": pid,
            "base_url": fields["base_url"].text(),
        }
        save_platform_config(self._config)
        self._cr_status.setText(self.tr("✓ Saved"))
