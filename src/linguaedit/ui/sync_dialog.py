"""Sync dialog for pulling/pushing translations from/to platforms."""
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import threading
import tempfile
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QLineEdit, QProgressBar,
    QGroupBox,
)
from PySide6.QtCore import Qt, Signal, QObject, QCoreApplication

from linguaedit.services.platforms import (
    load_platform_config,
    TransifexConfig, WeblateConfig, CrowdinConfig,
    transifex_list_resources, transifex_list_languages, transifex_download,
    transifex_upload_translation,
    weblate_list_translations, weblate_list_components, weblate_download, weblate_upload,
    crowdin_list_files, crowdin_list_languages, crowdin_download_file,
    crowdin_build_translations, crowdin_poll_build,
    crowdin_upload_translation,
    PlatformError,
)


class _SignalHelper(QObject):
    """Helper to emit signals from worker threads."""
    set_text = Signal(QLabel, str)
    set_enabled = Signal(QPushButton, bool)
    populate = Signal(list)
    progress_visible = Signal(bool)


class SyncDialog(QDialog):
    """Dialog for syncing translations with remote platforms."""

    def __init__(self, parent, platform: str, mode: str = "pull",
                 file_content: bytes | None = None, file_name: str = ""):
        super().__init__(parent)

        mode_text = self.tr("Pull") if mode == "pull" else self.tr("Push")
        self.setWindowTitle(f"{mode_text} — {platform.capitalize()}")
        self.setModal(True)
        self.resize(550, 500)

        self._parent = parent
        self._platform = platform
        self._mode = mode
        self._file_content = file_content
        self._file_name = file_name
        self._config_data = load_platform_config()
        self._resources: list[dict] = []
        self._on_file_downloaded = None

        self._signals = _SignalHelper()
        self._signals.set_text.connect(lambda lbl, txt: lbl.setText(txt))
        self._signals.set_enabled.connect(lambda btn, val: btn.setEnabled(val))
        self._signals.populate.connect(self._populate_resources)
        self._signals.progress_visible.connect(lambda v: self._progress.setVisible(v))

        self._build_ui()
        self._load_resources()

    def set_on_file_downloaded(self, callback):
        self._on_file_downloaded = callback

    # ── UI ────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self._status_label = QLabel(self.tr("Loading resources…"))
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        group = QGroupBox(self.tr("Resources"))
        group_layout = QVBoxLayout(group)
        self._resource_list = QListWidget()
        self._resource_list.setMinimumHeight(150)
        group_layout.addWidget(self._resource_list)
        layout.addWidget(group)

        lang_row = QHBoxLayout()
        lang_row.addWidget(QLabel(self.tr("Language:")))
        self._lang_entry = QLineEdit("sv")
        self._lang_entry.setPlaceholderText(self.tr("e.g. sv, de, fr"))
        lang_row.addWidget(self._lang_entry)
        layout.addLayout(lang_row)

        if self._mode == "pull":
            self._action_btn = QPushButton(self.tr("Pull Translation"))
            self._action_btn.clicked.connect(self._on_pull)
        else:
            self._action_btn = QPushButton(self.tr("Push Translation"))
            self._action_btn.clicked.connect(self._on_push)
        self._action_btn.setEnabled(False)
        layout.addWidget(self._action_btn)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._sync_status = QLabel("")
        self._sync_status.setWordWrap(True)
        layout.addWidget(self._sync_status)

    # ── Load resources ────────────────────────────────────────────

    def _load_resources(self):
        def do_load():
            try:
                if self._platform == "transifex":
                    resources = self._load_transifex_resources()
                elif self._platform == "weblate":
                    resources = self._load_weblate_resources()
                elif self._platform == "crowdin":
                    resources = self._load_crowdin_resources()
                else:
                    resources = []
                self._signals.populate.emit(resources)
            except PlatformError as e:
                self._signals.set_text.emit(
                    self._status_label,
                    self.tr("✗ Error: %1").replace("%1", str(e)))
            except Exception as e:
                self._signals.set_text.emit(
                    self._status_label,
                    self.tr("✗ Error: %1").replace("%1", str(e)))

        threading.Thread(target=do_load, daemon=True).start()

    def _load_transifex_resources(self) -> list[dict]:
        cfg = self._config_data.get("transifex", {})
        if not cfg.get("api_token"):
            raise PlatformError(self.tr("Transifex not configured. Open Platform Settings first."))
        config = TransifexConfig(**{k: v for k, v in cfg.items() if k in TransifexConfig.__dataclass_fields__})
        resources = transifex_list_resources(config)
        return [{"id": r["id"], "name": r.get("attributes", {}).get("name", r["id"]),
                 "type": "transifex"} for r in resources]

    def _load_weblate_resources(self) -> list[dict]:
        cfg = self._config_data.get("weblate", {})
        if not cfg.get("api_key"):
            raise PlatformError(self.tr("Weblate not configured. Open Platform Settings first."))
        config = WeblateConfig(**{k: v for k, v in cfg.items() if k in WeblateConfig.__dataclass_fields__})
        translations = weblate_list_translations(config)
        return [{"id": t.get("language", {}).get("code", "?"),
                 "name": "{} — {}/{}".format(
                     t.get("language", {}).get("code", "?"),
                     t.get("translated", 0),
                     t.get("total", 0)),
                 "type": "weblate"} for t in translations]

    def _load_crowdin_resources(self) -> list[dict]:
        cfg = self._config_data.get("crowdin", {})
        if not cfg.get("api_token"):
            raise PlatformError(self.tr("Crowdin not configured. Open Platform Settings first."))
        config = CrowdinConfig(**{k: v for k, v in cfg.items() if k in CrowdinConfig.__dataclass_fields__})
        files = crowdin_list_files(config)
        return [{"id": f.get("data", f).get("id", 0),
                 "name": f.get("data", f).get("name", self.tr("Unknown")),
                 "type": "crowdin"} for f in files]

    def _populate_resources(self, resources: list[dict]):
        self._resources = resources
        self._resource_list.clear()

        if not resources:
            self._status_label.setText(self.tr("No resources found"))
            return

        for res in resources:
            item = QListWidgetItem(res["name"])
            item.setData(Qt.UserRole, res)
            self._resource_list.addItem(item)

        self._status_label.setText(
            self.tr("%1 resources found").replace("%1", str(len(resources))))
        self._action_btn.setEnabled(True)

    # ── Pull ──────────────────────────────────────────────────────

    def _on_pull(self):
        item = self._resource_list.currentItem()
        if not item:
            self._sync_status.setText(self.tr("Select a resource first"))
            return
        res = item.data(Qt.UserRole)
        lang = self._lang_entry.text().strip()
        if not lang:
            self._sync_status.setText(self.tr("Enter a language code"))
            return

        self._action_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._sync_status.setText(self.tr("Downloading…"))

        def do_pull():
            try:
                content = self._pull_from_platform(res, lang)
                suffix = ".po"
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix,
                                                   prefix=f"linguaedit_{self._platform}_")
                tmp.write(content)
                tmp.close()
                path = tmp.name
                now = datetime.now().strftime("%H:%M:%S")
                msg = self.tr("✓ Downloaded at %1\nSaved to: %2").replace("%1", now).replace("%2", path)
                self._signals.set_text.emit(self._sync_status, msg)
                self._signals.progress_visible.emit(False)
                self._signals.set_enabled.emit(self._action_btn, True)
                if self._on_file_downloaded:
                    self._downloaded_path = path
            except (PlatformError, Exception) as e:
                self._signals.set_text.emit(
                    self._sync_status,
                    self.tr("✗ Pull failed: %1").replace("%1", str(e)))
                self._signals.progress_visible.emit(False)
                self._signals.set_enabled.emit(self._action_btn, True)

        threading.Thread(target=do_pull, daemon=True).start()

    def _pull_from_platform(self, resource: dict, language: str) -> bytes:
        if self._platform == "transifex":
            cfg = self._config_data["transifex"]
            config = TransifexConfig(**{k: v for k, v in cfg.items() if k in TransifexConfig.__dataclass_fields__})
            return transifex_download(config, resource["id"], language)
        elif self._platform == "weblate":
            cfg = self._config_data["weblate"]
            config = WeblateConfig(**{k: v for k, v in cfg.items() if k in WeblateConfig.__dataclass_fields__})
            return weblate_download(config, language)
        elif self._platform == "crowdin":
            cfg = self._config_data["crowdin"]
            config = CrowdinConfig(**{k: v for k, v in cfg.items() if k in CrowdinConfig.__dataclass_fields__})
            build_id = crowdin_build_translations(config)
            url = crowdin_poll_build(config, build_id)
            return crowdin_download_file(url)
        raise PlatformError(self.tr("Unknown platform"))

    # ── Push ──────────────────────────────────────────────────────

    def _on_push(self):
        if not self._file_content:
            self._sync_status.setText(self.tr("No file loaded to push"))
            return
        item = self._resource_list.currentItem()
        if not item:
            self._sync_status.setText(self.tr("Select a resource first"))
            return
        res = item.data(Qt.UserRole)
        lang = self._lang_entry.text().strip()
        if not lang:
            self._sync_status.setText(self.tr("Enter a language code"))
            return

        self._action_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._sync_status.setText(self.tr("Uploading…"))

        def do_push():
            try:
                self._push_to_platform(res, lang)
                now = datetime.now().strftime("%H:%M:%S")
                self._signals.set_text.emit(
                    self._sync_status,
                    self.tr("✓ Uploaded at %1").replace("%1", now))
            except (PlatformError, Exception) as e:
                self._signals.set_text.emit(
                    self._sync_status,
                    self.tr("✗ Push failed: %1").replace("%1", str(e)))
            finally:
                self._signals.progress_visible.emit(False)
                self._signals.set_enabled.emit(self._action_btn, True)

        threading.Thread(target=do_push, daemon=True).start()

    def _push_to_platform(self, resource: dict, language: str):
        if self._platform == "transifex":
            cfg = self._config_data["transifex"]
            config = TransifexConfig(**{k: v for k, v in cfg.items() if k in TransifexConfig.__dataclass_fields__})
            transifex_upload_translation(config, resource["id"], language, self._file_content)
        elif self._platform == "weblate":
            cfg = self._config_data["weblate"]
            config = WeblateConfig(**{k: v for k, v in cfg.items() if k in WeblateConfig.__dataclass_fields__})
            weblate_upload(config, language, self._file_content, self._file_name or "translation.po")
        elif self._platform == "crowdin":
            cfg = self._config_data["crowdin"]
            config = CrowdinConfig(**{k: v for k, v in cfg.items() if k in CrowdinConfig.__dataclass_fields__})
            crowdin_upload_translation(config, resource["id"], language,
                                       self._file_content, self._file_name or "translation.po")
        else:
            raise PlatformError(self.tr("Unknown platform"))
