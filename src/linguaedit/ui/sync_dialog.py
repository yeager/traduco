"""Sync dialog for pulling/pushing translations from/to platforms."""
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

import threading
import tempfile
from datetime import datetime
from pathlib import Path
from gettext import gettext as _

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


class SyncDialog(Adw.Window):
    """Dialog for syncing translations with remote platforms."""

    def __init__(self, parent: Gtk.Window, platform: str, mode: str = "pull",
                 file_content: bytes | None = None, file_name: str = ""):
        """
        Args:
            parent: Parent window
            platform: "transifex", "weblate", or "crowdin"
            mode: "pull" or "push"
            file_content: File bytes for push mode
            file_name: Filename for push mode
        """
        super().__init__(
            title=_("{mode} — {platform}").format(
                mode=_("Pull") if mode == "pull" else _("Push"),
                platform=platform.capitalize(),
            ),
            transient_for=parent,
            modal=True,
            default_width=550,
            default_height=500,
        )

        self._parent = parent
        self._platform = platform
        self._mode = mode
        self._file_content = file_content
        self._file_name = file_name
        self._config_data = load_platform_config()
        self._resources: list[dict] = []
        self._languages: list[dict] = []
        self._on_file_downloaded = None  # callback(path: str)

        self._build_ui()
        self._load_resources()

    def set_on_file_downloaded(self, callback):
        """Set callback for when a file is downloaded: callback(path: str)."""
        self._on_file_downloaded = callback

    # ── UI ────────────────────────────────────────────────────────

    def _build_ui(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Header
        header = Adw.HeaderBar()
        box.append(header)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                          margin_start=16, margin_end=16, margin_top=16, margin_bottom=16)

        # Status bar
        self._status_label = Gtk.Label(label=_("Loading resources…"), xalign=0.0, wrap=True)
        content.append(self._status_label)

        # Resource / component list
        resource_frame = Gtk.Frame(label=_("Resources"))
        resource_sw = Gtk.ScrolledWindow(vexpand=True)
        resource_sw.set_size_request(-1, 150)
        self._resource_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        resource_sw.set_child(self._resource_list)
        resource_frame.set_child(resource_sw)
        content.append(resource_frame)

        # Language selector
        lang_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lang_box.append(Gtk.Label(label=_("Language:"), xalign=0.0))
        self._lang_entry = Gtk.Entry(placeholder_text=_("e.g. sv, de, fr"), hexpand=True)
        self._lang_entry.set_text("sv")
        lang_box.append(self._lang_entry)
        content.append(lang_box)

        # Action button
        if self._mode == "pull":
            self._action_btn = Gtk.Button(label=_("Pull Translation"))
            self._action_btn.add_css_class("suggested-action")
            self._action_btn.connect("clicked", self._on_pull)
        else:
            self._action_btn = Gtk.Button(label=_("Push Translation"))
            self._action_btn.add_css_class("destructive-action")
            self._action_btn.connect("clicked", self._on_push)
        self._action_btn.set_sensitive(False)
        content.append(self._action_btn)

        # Progress
        self._progress = Gtk.ProgressBar()
        self._progress.set_visible(False)
        content.append(self._progress)

        # Sync status
        self._sync_status = Gtk.Label(label="", xalign=0.0, wrap=True, selectable=True)
        self._sync_status.add_css_class("dim-label")
        content.append(self._sync_status)

        box.append(content)
        self.set_content(box)

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
                GLib.idle_add(self._populate_resources, resources)
            except PlatformError as e:
                GLib.idle_add(self._status_label.set_label,
                              _("✗ Error: {error}").format(error=str(e)))
            except Exception as e:
                GLib.idle_add(self._status_label.set_label,
                              _("✗ Error: {error}").format(error=str(e)))

        threading.Thread(target=do_load, daemon=True).start()

    def _load_transifex_resources(self) -> list[dict]:
        cfg = self._config_data.get("transifex", {})
        if not cfg.get("api_token"):
            raise PlatformError(_("Transifex not configured. Open Platform Settings first."))
        config = TransifexConfig(**{k: v for k, v in cfg.items() if k in TransifexConfig.__dataclass_fields__})
        resources = transifex_list_resources(config)
        return [{"id": r["id"], "name": r.get("attributes", {}).get("name", r["id"]),
                 "type": "transifex"} for r in resources]

    def _load_weblate_resources(self) -> list[dict]:
        cfg = self._config_data.get("weblate", {})
        if not cfg.get("api_key"):
            raise PlatformError(_("Weblate not configured. Open Platform Settings first."))
        config = WeblateConfig(**{k: v for k, v in cfg.items() if k in WeblateConfig.__dataclass_fields__})
        translations = weblate_list_translations(config)
        return [{"id": t.get("language", {}).get("code", "?"),
                 "name": _("{lang} — {translated}/{total}").format(
                     lang=t.get("language", {}).get("code", "?"),
                     translated=t.get("translated", 0),
                     total=t.get("total", 0)),
                 "type": "weblate"} for t in translations]

    def _load_crowdin_resources(self) -> list[dict]:
        cfg = self._config_data.get("crowdin", {})
        if not cfg.get("api_token"):
            raise PlatformError(_("Crowdin not configured. Open Platform Settings first."))
        config = CrowdinConfig(**{k: v for k, v in cfg.items() if k in CrowdinConfig.__dataclass_fields__})
        files = crowdin_list_files(config)
        return [{"id": f.get("data", f).get("id", 0),
                 "name": f.get("data", f).get("name", _("Unknown")),
                 "type": "crowdin"} for f in files]

    def _populate_resources(self, resources: list[dict]):
        self._resources = resources
        while row := self._resource_list.get_first_child():
            self._resource_list.remove(row)

        if not resources:
            self._status_label.set_label(_("No resources found"))
            return

        for res in resources:
            row = Gtk.ListBoxRow()
            label = Gtk.Label(label=res["name"], xalign=0.0,
                              margin_start=8, margin_end=8, margin_top=4, margin_bottom=4)
            row.set_child(label)
            row._resource_data = res
            self._resource_list.append(row)

        count = len(resources)
        self._status_label.set_label(
            _("{count} resources found").format(count=count))
        self._action_btn.set_sensitive(True)

    # ── Pull ──────────────────────────────────────────────────────

    def _on_pull(self, btn):
        row = self._resource_list.get_selected_row()
        if not row:
            self._sync_status.set_label(_("Select a resource first"))
            return
        res = row._resource_data
        lang = self._lang_entry.get_text().strip()
        if not lang:
            self._sync_status.set_label(_("Enter a language code"))
            return

        self._action_btn.set_sensitive(False)
        self._progress.set_visible(True)
        self._progress.pulse()
        self._sync_status.set_label(_("Downloading…"))

        def do_pull():
            try:
                content = self._pull_from_platform(res, lang)
                # Save to temp file
                suffix = ".po"
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix,
                                                   prefix=f"linguaedit_{self._platform}_")
                tmp.write(content)
                tmp.close()
                path = tmp.name
                now = datetime.now().strftime("%H:%M:%S")
                GLib.idle_add(self._on_pull_done, path, now)
            except PlatformError as e:
                GLib.idle_add(self._on_pull_error, str(e))
            except Exception as e:
                GLib.idle_add(self._on_pull_error, str(e))

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
        raise PlatformError(_("Unknown platform"))

    def _on_pull_done(self, path: str, timestamp: str):
        self._progress.set_visible(False)
        self._action_btn.set_sensitive(True)
        self._sync_status.set_label(
            _("✓ Downloaded at {time}\nSaved to: {path}").format(time=timestamp, path=path))
        if self._on_file_downloaded:
            self._on_file_downloaded(path)

    def _on_pull_error(self, error: str):
        self._progress.set_visible(False)
        self._action_btn.set_sensitive(True)
        self._sync_status.set_label(_("✗ Pull failed: {error}").format(error=error))

    # ── Push ──────────────────────────────────────────────────────

    def _on_push(self, btn):
        if not self._file_content:
            self._sync_status.set_label(_("No file loaded to push"))
            return
        row = self._resource_list.get_selected_row()
        if not row:
            self._sync_status.set_label(_("Select a resource first"))
            return
        res = row._resource_data
        lang = self._lang_entry.get_text().strip()
        if not lang:
            self._sync_status.set_label(_("Enter a language code"))
            return

        self._action_btn.set_sensitive(False)
        self._progress.set_visible(True)
        self._progress.pulse()
        self._sync_status.set_label(_("Uploading…"))

        def do_push():
            try:
                self._push_to_platform(res, lang)
                now = datetime.now().strftime("%H:%M:%S")
                GLib.idle_add(self._on_push_done, now)
            except PlatformError as e:
                GLib.idle_add(self._on_push_error, str(e))
            except Exception as e:
                GLib.idle_add(self._on_push_error, str(e))

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
            raise PlatformError(_("Unknown platform"))

    def _on_push_done(self, timestamp: str):
        self._progress.set_visible(False)
        self._action_btn.set_sensitive(True)
        self._sync_status.set_label(_("✓ Uploaded at {time}").format(time=timestamp))

    def _on_push_error(self, error: str):
        self._progress.set_visible(False)
        self._action_btn.set_sensitive(True)
        self._sync_status.set_label(_("✗ Push failed: {error}").format(error=error))
