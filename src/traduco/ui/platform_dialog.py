"""Platform settings dialog for Transifex, Weblate, and Crowdin."""
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

import threading
from gettext import gettext as _

from traduco.services.platforms import (
    load_platform_config, save_platform_config,
    TransifexConfig, WeblateConfig, CrowdinConfig,
    transifex_test_connection, weblate_test_connection, crowdin_test_connection,
    PlatformError,
)
from traduco.services.keystore import backend_name, is_secure_backend


class PlatformSettingsDialog(Adw.PreferencesWindow):
    """Settings dialog for translation platform integrations."""

    def __init__(self, parent: Gtk.Window):
        super().__init__(
            title=_("Platform Settings"),
            transient_for=parent,
            modal=True,
            default_width=600,
            default_height=500,
        )

        self._config = load_platform_config()
        self._entries: dict[str, dict[str, Adw.EntryRow]] = {}

        self._build_security_banner()
        self._build_transifex_page()
        self._build_weblate_page()
        self._build_crowdin_page()

    def _build_security_banner(self):
        """Show which keychain backend is active."""
        name = backend_name()
        secure = is_secure_backend()
        if secure:
            banner = Adw.Banner(title=_("🔒 Tokens stored in {backend}").format(backend=name))
        else:
            banner = Adw.Banner(
                title=_("⚠️ No system keychain — tokens stored with basic obfuscation. Install 'secretstorage' for proper security."),
                button_label="",
            )
            banner.set_revealed(True)
        # Banners need to be shown via set_revealed
        banner.set_revealed(True)

    # ── Transifex ─────────────────────────────────────────────────

    def _build_transifex_page(self):
        page = Adw.PreferencesPage(title=_("Transifex"), icon_name="network-server-symbolic")

        group = Adw.PreferencesGroup(title=_("Transifex API"), description=_("Configure your Transifex connection"))

        cfg = self._config.get("transifex", {})
        fields = {}

        token_row = Adw.PasswordEntryRow(title=_("API Token"))
        token_row.set_text(cfg.get("api_token", ""))
        fields["api_token"] = token_row
        group.add(token_row)

        org_row = Adw.EntryRow(title=_("Organization"))
        org_row.set_text(cfg.get("organization", ""))
        fields["organization"] = org_row
        group.add(org_row)

        project_row = Adw.EntryRow(title=_("Project"))
        project_row.set_text(cfg.get("project", ""))
        fields["project"] = project_row
        group.add(project_row)

        url_row = Adw.EntryRow(title=_("Base URL"))
        url_row.set_text(cfg.get("base_url", "https://rest.api.transifex.com"))
        fields["base_url"] = url_row
        group.add(url_row)

        self._entries["transifex"] = fields

        # Test + Save buttons
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8,
                          margin_top=12, halign=Gtk.Align.END)
        self._tx_status = Gtk.Label(label="", hexpand=True, xalign=0.0)
        btn_box.append(self._tx_status)

        test_btn = Gtk.Button(label=_("Test Connection"))
        test_btn.connect("clicked", self._on_test_transifex)
        btn_box.append(test_btn)

        save_btn = Gtk.Button(label=_("Save"))
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", self._on_save_transifex)
        btn_box.append(save_btn)

        row = Adw.ActionRow()
        row.set_child(btn_box)
        group.add(row)

        page.add(group)
        self.add(page)

    def _on_test_transifex(self, btn):
        fields = self._entries["transifex"]
        config = TransifexConfig(
            api_token=fields["api_token"].get_text(),
            organization=fields["organization"].get_text(),
            project=fields["project"].get_text(),
            base_url=fields["base_url"].get_text(),
        )
        self._tx_status.set_label(_("Testing…"))
        btn.set_sensitive(False)

        def do_test():
            try:
                name = transifex_test_connection(config)
                GLib.idle_add(self._tx_status.set_label, _("✓ Connected: {name}").format(name=name))
            except PlatformError as e:
                GLib.idle_add(self._tx_status.set_label, _("✗ {error}").format(error=str(e)))
            finally:
                GLib.idle_add(btn.set_sensitive, True)

        threading.Thread(target=do_test, daemon=True).start()

    def _on_save_transifex(self, btn):
        fields = self._entries["transifex"]
        self._config["transifex"] = {
            "api_token": fields["api_token"].get_text(),
            "organization": fields["organization"].get_text(),
            "project": fields["project"].get_text(),
            "base_url": fields["base_url"].get_text(),
        }
        save_platform_config(self._config)
        self._tx_status.set_label(_("✓ Saved"))

    # ── Weblate ───────────────────────────────────────────────────

    def _build_weblate_page(self):
        page = Adw.PreferencesPage(title=_("Weblate"), icon_name="network-server-symbolic")

        group = Adw.PreferencesGroup(title=_("Weblate API"), description=_("Configure your Weblate connection"))

        cfg = self._config.get("weblate", {})
        fields = {}

        url_row = Adw.EntryRow(title=_("API URL"))
        url_row.set_text(cfg.get("api_url", "https://hosted.weblate.org/api/"))
        fields["api_url"] = url_row
        group.add(url_row)

        key_row = Adw.PasswordEntryRow(title=_("API Key"))
        key_row.set_text(cfg.get("api_key", ""))
        fields["api_key"] = key_row
        group.add(key_row)

        project_row = Adw.EntryRow(title=_("Project"))
        project_row.set_text(cfg.get("project", ""))
        fields["project"] = project_row
        group.add(project_row)

        comp_row = Adw.EntryRow(title=_("Component"))
        comp_row.set_text(cfg.get("component", ""))
        fields["component"] = comp_row
        group.add(comp_row)

        self._entries["weblate"] = fields

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8,
                          margin_top=12, halign=Gtk.Align.END)
        self._wb_status = Gtk.Label(label="", hexpand=True, xalign=0.0)
        btn_box.append(self._wb_status)

        test_btn = Gtk.Button(label=_("Test Connection"))
        test_btn.connect("clicked", self._on_test_weblate)
        btn_box.append(test_btn)

        save_btn = Gtk.Button(label=_("Save"))
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", self._on_save_weblate)
        btn_box.append(save_btn)

        row = Adw.ActionRow()
        row.set_child(btn_box)
        group.add(row)

        page.add(group)
        self.add(page)

    def _on_test_weblate(self, btn):
        fields = self._entries["weblate"]
        config = WeblateConfig(
            api_url=fields["api_url"].get_text(),
            api_key=fields["api_key"].get_text(),
            project=fields["project"].get_text(),
            component=fields["component"].get_text(),
        )
        self._wb_status.set_label(_("Testing…"))
        btn.set_sensitive(False)

        def do_test():
            try:
                name = weblate_test_connection(config)
                GLib.idle_add(self._wb_status.set_label, _("✓ Connected: {name}").format(name=name))
            except PlatformError as e:
                GLib.idle_add(self._wb_status.set_label, _("✗ {error}").format(error=str(e)))
            finally:
                GLib.idle_add(btn.set_sensitive, True)

        threading.Thread(target=do_test, daemon=True).start()

    def _on_save_weblate(self, btn):
        fields = self._entries["weblate"]
        self._config["weblate"] = {
            "api_url": fields["api_url"].get_text(),
            "api_key": fields["api_key"].get_text(),
            "project": fields["project"].get_text(),
            "component": fields["component"].get_text(),
        }
        save_platform_config(self._config)
        self._wb_status.set_label(_("✓ Saved"))

    # ── Crowdin ───────────────────────────────────────────────────

    def _build_crowdin_page(self):
        page = Adw.PreferencesPage(title=_("Crowdin"), icon_name="network-server-symbolic")

        group = Adw.PreferencesGroup(title=_("Crowdin API"), description=_("Configure your Crowdin connection"))

        cfg = self._config.get("crowdin", {})
        fields = {}

        token_row = Adw.PasswordEntryRow(title=_("API Token"))
        token_row.set_text(cfg.get("api_token", ""))
        fields["api_token"] = token_row
        group.add(token_row)

        pid_row = Adw.EntryRow(title=_("Project ID"))
        pid_row.set_text(str(cfg.get("project_id", "")))
        fields["project_id"] = pid_row
        group.add(pid_row)

        url_row = Adw.EntryRow(title=_("Base URL"))
        url_row.set_text(cfg.get("base_url", "https://api.crowdin.com/api/v2"))
        fields["base_url"] = url_row
        group.add(url_row)

        self._entries["crowdin"] = fields

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8,
                          margin_top=12, halign=Gtk.Align.END)
        self._cr_status = Gtk.Label(label="", hexpand=True, xalign=0.0)
        btn_box.append(self._cr_status)

        test_btn = Gtk.Button(label=_("Test Connection"))
        test_btn.connect("clicked", self._on_test_crowdin)
        btn_box.append(test_btn)

        save_btn = Gtk.Button(label=_("Save"))
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", self._on_save_crowdin)
        btn_box.append(save_btn)

        row = Adw.ActionRow()
        row.set_child(btn_box)
        group.add(row)

        page.add(group)
        self.add(page)

    def _on_test_crowdin(self, btn):
        fields = self._entries["crowdin"]
        try:
            pid = int(fields["project_id"].get_text())
        except ValueError:
            self._cr_status.set_label(_("✗ Project ID must be a number"))
            return
        config = CrowdinConfig(
            api_token=fields["api_token"].get_text(),
            project_id=pid,
            base_url=fields["base_url"].get_text(),
        )
        self._cr_status.set_label(_("Testing…"))
        btn.set_sensitive(False)

        def do_test():
            try:
                name = crowdin_test_connection(config)
                GLib.idle_add(self._cr_status.set_label, _("✓ Connected: {name}").format(name=name))
            except PlatformError as e:
                GLib.idle_add(self._cr_status.set_label, _("✗ {error}").format(error=str(e)))
            finally:
                GLib.idle_add(btn.set_sensitive, True)

        threading.Thread(target=do_test, daemon=True).start()

    def _on_save_crowdin(self, btn):
        fields = self._entries["crowdin"]
        try:
            pid = int(fields["project_id"].get_text())
        except ValueError:
            pid = 0
        self._config["crowdin"] = {
            "api_token": fields["api_token"].get_text(),
            "project_id": pid,
            "base_url": fields["base_url"].get_text(),
        }
        save_platform_config(self._config)
        self._cr_status.set_label(_("✓ Saved"))
