"""Platform settings dialog for Transifex, Weblate, and Crowdin."""
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import threading

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QFormLayout, QLineEdit, QPushButton, QLabel, QGroupBox,
    QListWidget, QListWidgetItem, QDialogButtonBox,
)
from PySide6.QtCore import Qt, Signal, QObject

from linguaedit.services.platforms import (
    load_platform_config, save_platform_config,
    TransifexConfig, WeblateConfig, CrowdinConfig,
    transifex_test_connection, weblate_test_connection, crowdin_test_connection,
    transifex_list_organizations, transifex_list_projects,
    weblate_list_projects, weblate_list_components,
    crowdin_list_projects,
    PlatformError,
)
from linguaedit.services.keystore import backend_name, is_secure_backend


class _SignalHelper(QObject):
    """Helper to emit signals from worker threads."""
    status_update = Signal(QLabel, str)
    enable_button = Signal(QPushButton, bool)
    browse_result = Signal(str, list)  # key, items


class _BrowseDialog(QDialog):
    """Simple list selection dialog for browsing platform resources."""

    def __init__(self, title: str, items: list[tuple[str, str]], parent=None):
        """items: list of (display_text, value)"""
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(450, 350)
        self.selected_value: str = ""

        layout = QVBoxLayout(self)
        self._list = QListWidget()
        for display, value in items:
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, value)
            self._list.addItem(item)
        self._list.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self._list)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_ok(self):
        item = self._list.currentItem()
        if item:
            self.selected_value = item.data(Qt.UserRole)
            self.accept()

    def _on_double_click(self):
        self._on_ok()


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
        self._signals.browse_result.connect(self._on_browse_result)

        self._pending_browse: dict[str, tuple] = {}  # key -> (field_widget, title)

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

    # ── Browse helper ─────────────────────────────────────────────

    def _start_browse(self, key: str, field: QLineEdit, title: str,
                      fetch_fn, status_label: QLabel):
        """Start a background browse operation."""
        self._pending_browse[key] = (field, title)
        status_label.setText(self.tr("Loading…"))

        def do_fetch():
            try:
                items = fetch_fn()
                self._signals.browse_result.emit(key, items)
                self._signals.status_update.emit(status_label, "")
            except PlatformError as e:
                self._signals.status_update.emit(
                    status_label, self.tr("✗ %1").replace("%1", str(e)))
                self._signals.browse_result.emit(key, [])
            except Exception as e:
                self._signals.status_update.emit(
                    status_label, self.tr("✗ %1").replace("%1", str(e)))
                self._signals.browse_result.emit(key, [])

        threading.Thread(target=do_fetch, daemon=True).start()

    def _on_browse_result(self, key: str, items: list):
        if key not in self._pending_browse or not items:
            self._pending_browse.pop(key, None)
            return
        field, title = self._pending_browse.pop(key)

        # Build display items based on the key type
        display_items: list[tuple[str, str]] = []
        for item in items:
            if isinstance(item, dict):
                name = item.get("name", "")
                slug = item.get("slug", item.get("identifier", ""))
                item_id = item.get("id", "")
                if slug:
                    display_items.append((f"{name} ({slug})", slug))
                elif item_id is not None:
                    display_items.append((f"{name} ({item_id})", str(item_id)))
                else:
                    display_items.append((name, name))

        if not display_items:
            return

        dlg = _BrowseDialog(title, display_items, self)
        if dlg.exec() == QDialog.Accepted and dlg.selected_value:
            field.setText(dlg.selected_value)

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

        # Organization with Browse
        org_row = QHBoxLayout()
        org_edit = QLineEdit(cfg.get("organization", ""))
        fields["organization"] = org_edit
        org_row.addWidget(org_edit)
        org_browse = QPushButton(self.tr("Browse…"))
        org_browse.clicked.connect(lambda: self._browse_tx_orgs())
        org_row.addWidget(org_browse)
        form.addRow(self.tr("Organization:"), org_row)

        # Project with Browse
        proj_row = QHBoxLayout()
        project_edit = QLineEdit(cfg.get("project", ""))
        fields["project"] = project_edit
        proj_row.addWidget(project_edit)
        proj_browse = QPushButton(self.tr("Browse…"))
        proj_browse.clicked.connect(lambda: self._browse_tx_projects())
        proj_row.addWidget(proj_browse)
        form.addRow(self.tr("Project:"), proj_row)

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

    def _browse_tx_orgs(self):
        fields = self._entries["transifex"]
        config = TransifexConfig(
            api_token=fields["api_token"].text(),
            organization="",
            project="",
            base_url=fields["base_url"].text(),
        )
        self._start_browse(
            "tx_orgs", fields["organization"],
            self.tr("Select Organization"),
            lambda: transifex_list_organizations(config),
            self._tx_status,
        )

    def _browse_tx_projects(self):
        fields = self._entries["transifex"]
        config = TransifexConfig(
            api_token=fields["api_token"].text(),
            organization=fields["organization"].text(),
            project="",
            base_url=fields["base_url"].text(),
        )
        self._start_browse(
            "tx_projects", fields["project"],
            self.tr("Select Project"),
            lambda: transifex_list_projects(config),
            self._tx_status,
        )

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

        # Project with Browse
        proj_row = QHBoxLayout()
        project_edit = QLineEdit(cfg.get("project", ""))
        fields["project"] = project_edit
        proj_row.addWidget(project_edit)
        proj_browse = QPushButton(self.tr("Browse…"))
        proj_browse.clicked.connect(lambda: self._browse_wb_projects())
        proj_row.addWidget(proj_browse)
        form.addRow(self.tr("Project:"), proj_row)

        # Component with Browse
        comp_row = QHBoxLayout()
        comp_edit = QLineEdit(cfg.get("component", ""))
        fields["component"] = comp_edit
        comp_row.addWidget(comp_edit)
        comp_browse = QPushButton(self.tr("Browse…"))
        comp_browse.clicked.connect(lambda: self._browse_wb_components())
        comp_row.addWidget(comp_browse)
        form.addRow(self.tr("Component:"), comp_row)

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

    def _browse_wb_projects(self):
        fields = self._entries["weblate"]
        config = WeblateConfig(
            api_url=fields["api_url"].text(),
            api_key=fields["api_key"].text(),
            project="",
            component="",
        )
        self._start_browse(
            "wb_projects", fields["project"],
            self.tr("Select Project"),
            lambda: weblate_list_projects(config),
            self._wb_status,
        )

    def _browse_wb_components(self):
        fields = self._entries["weblate"]
        config = WeblateConfig(
            api_url=fields["api_url"].text(),
            api_key=fields["api_key"].text(),
            project=fields["project"].text(),
            component="",
        )

        def fetch():
            comps = weblate_list_components(config)
            return [{"name": c.get("name", ""), "slug": c.get("slug", "")} for c in comps]

        self._start_browse(
            "wb_components", fields["component"],
            self.tr("Select Component"),
            fetch,
            self._wb_status,
        )

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

        # Project ID with Browse
        pid_row = QHBoxLayout()
        pid_edit = QLineEdit(str(cfg.get("project_id", "")))
        fields["project_id"] = pid_edit
        pid_row.addWidget(pid_edit)
        pid_browse = QPushButton(self.tr("Browse…"))
        pid_browse.clicked.connect(lambda: self._browse_cr_projects())
        pid_row.addWidget(pid_browse)
        form.addRow(self.tr("Project ID:"), pid_row)

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

    def _browse_cr_projects(self):
        fields = self._entries["crowdin"]
        config = CrowdinConfig(
            api_token=fields["api_token"].text(),
            project_id=0,
            base_url=fields["base_url"].text(),
        )

        def fetch():
            projects = crowdin_list_projects(config)
            # Return with id as the value (Crowdin uses numeric IDs)
            return [{"name": p["name"], "slug": str(p["id"])} for p in projects]

        self._start_browse(
            "cr_projects", fields["project_id"],
            self.tr("Select Project"),
            fetch,
            self._cr_status,
        )

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
