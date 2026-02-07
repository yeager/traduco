"""Main application window — full-featured translation editor."""

from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib, Pango, Gdk

import json
import re
from difflib import SequenceMatcher, unified_diff
from pathlib import Path
from typing import Optional

from traduco import APP_ID, __version__
from traduco.parsers.po_parser import parse_po, save_po, POFileData, TranslationEntry
from traduco.parsers.ts_parser import parse_ts, save_ts, TSFileData
from traduco.parsers.json_parser import parse_json, save_json, JSONFileData
from traduco.services.linter import lint_entries, LintResult, LintIssue
from traduco.services.spellcheck import check_text, available_languages
from traduco.services.translator import translate, ENGINES, TranslationError
from traduco.services.tm import lookup_tm, add_to_tm, feed_file_to_tm
from traduco.ui.platform_dialog import PlatformSettingsDialog
from traduco.ui.sync_dialog import SyncDialog

# ── Recent files helper ──────────────────────────────────────────────

_RECENT_FILE = Path.home() / ".config" / "traduco" / "recent.json"


def _load_recent() -> list[str]:
    try:
        return json.loads(_RECENT_FILE.read_text("utf-8"))
    except Exception:
        return []


def _save_recent(paths: list[str]) -> None:
    _RECENT_FILE.parent.mkdir(parents=True, exist_ok=True)
    _RECENT_FILE.write_text(json.dumps(paths[:20], ensure_ascii=False), "utf-8")


def _add_recent(path: str) -> None:
    recent = _load_recent()
    if path in recent:
        recent.remove(path)
    recent.insert(0, path)
    _save_recent(recent[:20])


# ── Format specifier regex ───────────────────────────────────────────

_FMT_RE = re.compile(
    r'%[\d$]*[-+ #0]*\d*\.?\d*[hlLqjzt]*[sdiufxXoecpg%]'  # C printf
    r'|\{[^}]*\}'                                            # Python {0}, {name}
    r'|%\([^)]+\)[sdiufxXoecpg]'                            # Python %(name)s
)


# ── Inline linting for a single entry ────────────────────────────────

def _lint_single(msgid: str, msgstr: str, flags: list[str]) -> list[LintIssue]:
    """Run linter on a single entry and return issues."""
    result = lint_entries([{"index": 0, "msgid": msgid, "msgstr": msgstr, "flags": flags}])
    return result.issues


# ── Window ────────────────────────────────────────────────────────────

class TraducoWindow(Adw.ApplicationWindow):
    """Main editor window."""

    def __init__(self, app: Adw.Application):
        super().__init__(application=app, title="Traduco", default_width=1100, default_height=700)

        self._file_data = None  # POFileData | TSFileData | JSONFileData
        self._file_type = None  # "po", "ts", "json"
        self._current_index = -1
        self._modified = False
        self._spell_lang = "en_US"
        self._trans_engine = "lingva"
        self._trans_source = "en"
        self._trans_target = "sv"

        # Undo/redo stacks per entry index
        self._undo_stacks: dict[int, list[str]] = {}
        self._redo_stacks: dict[int, list[str]] = {}
        self._undo_snapshot: str | None = None  # last known text for dirty detection

        # Lint cache per entry index
        self._lint_cache: dict[int, list[LintIssue]] = {}

        # File monitor
        self._file_monitor: Gio.FileMonitor | None = None
        self._reload_debounce_id: int = 0

        # Filter mode: "all", "fuzzy", "untranslated"
        self._filter_mode = "all"

        # Sort mode and index mapping
        self._sort_mode = "file"  # file|src_az|src_za|trans_az|trans_za|status|length|reference
        self._sort_order: list[int] = []  # maps display position → original index

        # 10. Dark theme — follow system preference via Adw.StyleManager
        style = Adw.StyleManager.get_default()
        style.set_color_scheme(Adw.ColorScheme.PREFER_DARK)

        self._build_ui()
        self._setup_actions()
        self._setup_keys()
        self._setup_dnd()

    # ── UI construction ───────────────────────────────────────────

    def _build_ui(self):
        # Toast overlay (wraps everything so toasts actually show)
        self._toast_overlay = Adw.ToastOverlay()

        # Header bar
        self._header = Adw.HeaderBar()

        # Open button
        open_btn = Gtk.Button(icon_name="document-open-symbolic", tooltip_text="Open file")
        open_btn.connect("clicked", self._on_open)
        self._header.pack_start(open_btn)

        # Save button
        save_btn = Gtk.Button(icon_name="document-save-symbolic", tooltip_text="Save")
        save_btn.connect("clicked", self._on_save)
        self._header.pack_start(save_btn)

        # Separator
        self._header.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))

        # Undo / Redo
        hdr_undo_btn = Gtk.Button(icon_name="edit-undo-symbolic", tooltip_text="Undo (Ctrl+Z)")
        hdr_undo_btn.connect("clicked", lambda b: self._do_undo())
        self._header.pack_start(hdr_undo_btn)

        hdr_redo_btn = Gtk.Button(icon_name="edit-redo-symbolic", tooltip_text="Redo (Ctrl+Shift+Z)")
        hdr_redo_btn.connect("clicked", lambda b: self._do_redo())
        self._header.pack_start(hdr_redo_btn)

        # Separator
        self._header.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))

        # Lint / Validate
        lint_btn = Gtk.Button(icon_name="dialog-warning-symbolic", tooltip_text="Lint / Validate file")
        lint_btn.connect("clicked", lambda b: self.activate_action("win.lint"))
        self._header.pack_start(lint_btn)

        # Pre-translate
        pretrans_btn = Gtk.Button(icon_name="system-run-symbolic", tooltip_text="Pre-translate all untranslated")
        pretrans_btn.connect("clicked", lambda b: self.activate_action("win.pretranslate"))
        self._header.pack_start(pretrans_btn)

        # Spell check
        spell_hdr_btn = Gtk.Button(icon_name="tools-check-spelling-symbolic", tooltip_text="Spell check current entry")
        spell_hdr_btn.connect("clicked", lambda b: self.activate_action("win.spellcheck"))
        self._header.pack_start(spell_hdr_btn)

        # ── Right side of header (pack_end, reverse visual order) ──

        # Platform sync button
        platform_btn = Gtk.Button(icon_name="network-server-symbolic", tooltip_text="Platform sync")
        platform_btn.connect("clicked", lambda b: self.activate_action("win.platform_settings"))
        self._header.pack_end(platform_btn)

        # Menu button (rightmost — packed first in pack_end)
        menu_btn = Gtk.MenuButton(icon_name="open-menu-symbolic", tooltip_text="Menu")
        menu = Gio.Menu()
        menu.append("Lint file", "win.lint")
        menu.append("Pre-translate all", "win.pretranslate")
        menu.append("Spell check current", "win.spellcheck")
        menu.append("File metadata…", "win.metadata")
        menu.append("Feed file to TM", "win.feed_tm")

        # Recent files submenu
        recent_section = Gio.Menu()
        for i, rp in enumerate(_load_recent()[:8]):
            name = Path(rp).name
            recent_section.append(name, f"win.open_recent_{i}")
        if recent_section.get_n_items() > 0:
            menu.append_section("Recent Files", recent_section)

        # Platform integration section
        platform_section = Gio.Menu()
        platform_section.append("Platforms…", "win.platform_settings")

        pull_submenu = Gio.Menu()
        pull_submenu.append("Transifex", "win.pull_transifex")
        pull_submenu.append("Weblate", "win.pull_weblate")
        pull_submenu.append("Crowdin", "win.pull_crowdin")
        platform_section.append_submenu("Pull from…", pull_submenu)

        push_submenu = Gio.Menu()
        push_submenu.append("Transifex", "win.push_transifex")
        push_submenu.append("Weblate", "win.push_weblate")
        push_submenu.append("Crowdin", "win.push_crowdin")
        platform_section.append_submenu("Push to…", push_submenu)

        menu.append_section("Platforms", platform_section)

        section2 = Gio.Menu()
        section2.append("GitHub PR…", "win.github_pr")
        menu.append_section("Integration", section2)

        section3 = Gio.Menu()
        section3.append("Check for updates", "win.check_updates")
        section3.append("Donate ♥", "win.donate")
        section3.append("About Traduco", "win.about")
        menu.append_section(None, section3)

        menu_btn.set_menu_model(menu)
        self._header.pack_end(menu_btn)

        # Separator (right side)
        self._header.pack_end(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))

        # Search toggle — focus the search entry
        search_toggle_btn = Gtk.Button(icon_name="edit-find-symbolic", tooltip_text="Focus search (Ctrl+F)")
        search_toggle_btn.connect("clicked", self._on_focus_search)
        self._header.pack_end(search_toggle_btn)

        # Filter untranslated toggle
        self._filter_untrans_hdr = Gtk.ToggleButton(icon_name="edit-find-replace-symbolic",
                                                      tooltip_text="Show untranslated only")
        self._filter_untrans_hdr.connect("toggled", self._on_hdr_filter_untranslated)
        self._header.pack_end(self._filter_untrans_hdr)

        # Separator
        self._header.pack_end(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))

        # Next untranslated
        next_untrans_btn = Gtk.Button(icon_name="go-next-symbolic", tooltip_text="Next untranslated")
        next_untrans_btn.connect("clicked", lambda b: self._navigate_untranslated(1))
        self._header.pack_end(next_untrans_btn)

        # Previous untranslated
        prev_untrans_btn = Gtk.Button(icon_name="go-previous-symbolic", tooltip_text="Previous untranslated")
        prev_untrans_btn.connect("clicked", lambda b: self._navigate_untranslated(-1))
        self._header.pack_end(prev_untrans_btn)

        # Main layout: paned
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_position(380)

        # ── Left side: filter + entry list + progress ──
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Search + sort row
        search_sort_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self._search_entry = Gtk.SearchEntry(placeholder_text="Filter…", hexpand=True)
        self._search_entry.connect("search-changed", self._on_search_changed)
        search_sort_box.append(self._search_entry)

        # Sort dropdown
        _SORT_LABELS = [
            "Filordning",
            "Källa (A-Ö)",
            "Källa (Ö-A)",
            "Översättning (A-Ö)",
            "Översättning (Ö-A)",
            "Status",
            "Stränglängd",
            "Referens",
        ]
        sort_model = Gtk.StringList.new(_SORT_LABELS)
        self._sort_dropdown = Gtk.DropDown(model=sort_model, tooltip_text="Sortering")
        self._sort_dropdown.set_selected(0)
        self._sort_dropdown.connect("notify::selected", self._on_sort_changed)
        search_sort_box.append(self._sort_dropdown)
        left_box.append(search_sort_box)

        # 5. Fuzzy/untranslated filter buttons
        filter_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4,
                             margin_start=4, margin_end=4, margin_top=4)
        self._filter_all_btn = Gtk.ToggleButton(label="All", active=True)
        self._filter_fuzzy_btn = Gtk.ToggleButton(label="Fuzzy")
        self._filter_untrans_btn = Gtk.ToggleButton(label="Untranslated")
        self._filter_all_btn.set_group(self._filter_fuzzy_btn)
        self._filter_untrans_btn.set_group(self._filter_fuzzy_btn)
        for btn, mode in [(self._filter_all_btn, "all"),
                          (self._filter_fuzzy_btn, "fuzzy"),
                          (self._filter_untrans_btn, "untranslated")]:
            btn.connect("toggled", self._on_filter_toggled, mode)
            filter_box.append(btn)
        left_box.append(filter_box)

        # List
        sw = Gtk.ScrolledWindow(vexpand=True)
        self._listbox = Gtk.ListBox()
        self._listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._listbox.connect("row-selected", self._on_row_selected)
        sw.set_child(self._listbox)
        left_box.append(sw)

        # 4. Progress bar + stats
        self._progress_bar = Gtk.ProgressBar()
        self._progress_bar.set_show_text(False)
        left_box.append(self._progress_bar)

        self._stats_label = Gtk.Label(label="No file loaded", xalign=0.0,
                                       margin_start=8, margin_end=8, margin_top=4, margin_bottom=4)
        self._stats_label.add_css_class("dim-label")
        left_box.append(self._stats_label)

        paned.set_start_child(left_box)

        # ── Right side: editor ──
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                            margin_start=12, margin_end=12, margin_top=8, margin_bottom=8)

        # Source label
        right_box.append(Gtk.Label(label="Source (msgid)", xalign=0.0, css_classes=["heading"]))
        self._source_view = Gtk.TextView(editable=False, wrap_mode=Gtk.WrapMode.WORD_CHAR, vexpand=False)
        self._source_view.set_size_request(-1, 80)
        src_sw = Gtk.ScrolledWindow(child=self._source_view, vexpand=False)
        src_sw.set_size_request(-1, 80)
        right_box.append(src_sw)

        # 8. Diff view for fuzzy (previous vs current msgid)
        self._diff_frame = Gtk.Frame(label="Fuzzy diff (previous → current)")
        self._diff_frame.set_margin_top(2)
        self._diff_label = Gtk.Label(label="", xalign=0.0, wrap=True, selectable=True,
                                      use_markup=True)
        diff_sw = Gtk.ScrolledWindow(child=self._diff_label, vexpand=False)
        diff_sw.set_size_request(-1, 60)
        diff_sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._diff_frame.set_child(diff_sw)
        self._diff_frame.set_visible(False)
        right_box.append(self._diff_frame)

        # String information frame
        info_frame = Gtk.Frame(label="String Information")
        info_frame.set_margin_top(4)
        info_frame.set_margin_bottom(4)
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2,
                           margin_start=8, margin_end=8, margin_top=6, margin_bottom=6)

        self._translator_note_label = Gtk.Label(label="", xalign=0.0, wrap=True, selectable=True)
        self._translator_note_row = self._make_info_row("Translator notes", self._translator_note_label)
        info_box.append(self._translator_note_row)

        self._extracted_comment_label = Gtk.Label(label="", xalign=0.0, wrap=True, selectable=True)
        self._extracted_comment_row = self._make_info_row("Developer notes", self._extracted_comment_label)
        info_box.append(self._extracted_comment_row)

        self._msgctxt_label = Gtk.Label(label="", xalign=0.0, wrap=True, selectable=True)
        self._msgctxt_row = self._make_info_row("Context", self._msgctxt_label)
        info_box.append(self._msgctxt_row)

        self._references_label = Gtk.Label(label="", xalign=0.0, wrap=True, selectable=True)
        self._references_row = self._make_info_row("References", self._references_label)
        info_box.append(self._references_row)

        self._flags_label = Gtk.Label(label="", xalign=0.0, wrap=True, selectable=True)
        self._flags_row = self._make_info_row("Flags", self._flags_label)
        info_box.append(self._flags_row)

        self._previous_label = Gtk.Label(label="", xalign=0.0, wrap=True, selectable=True)
        self._previous_row = self._make_info_row("Previous source", self._previous_label)
        info_box.append(self._previous_row)

        info_frame.set_child(info_box)
        info_sw = Gtk.ScrolledWindow(child=info_frame, vexpand=False)
        info_sw.set_size_request(-1, 120)
        info_sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        right_box.append(info_sw)

        # 7. TM suggestions frame
        self._tm_frame = Gtk.Frame(label="Translation Memory")
        self._tm_frame.set_margin_top(2)
        self._tm_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2,
                                margin_start=6, margin_end=6, margin_top=4, margin_bottom=4)
        self._tm_frame.set_child(self._tm_box)
        self._tm_frame.set_visible(False)
        right_box.append(self._tm_frame)

        # 2. Plural tabs (notebook) — only visible for plural entries
        self._plural_notebook = Gtk.Notebook()
        self._plural_notebook.set_visible(False)
        right_box.append(self._plural_notebook)

        # Translation (singular / non-plural)
        right_box.append(Gtk.Label(label="Translation (msgstr)", xalign=0.0, css_classes=["heading"]))
        self._trans_view = Gtk.TextView(editable=True, wrap_mode=Gtk.WrapMode.WORD_CHAR, vexpand=True)
        self._trans_view.get_buffer().connect("changed", self._on_trans_buffer_changed)
        trans_sw = Gtk.ScrolledWindow(child=self._trans_view, vexpand=True)
        self._trans_sw = trans_sw
        right_box.append(trans_sw)

        # 6. Inline lint label (below translation)
        self._lint_inline_label = Gtk.Label(label="", xalign=0.0, wrap=True, selectable=True,
                                             use_markup=True)
        right_box.append(self._lint_inline_label)

        # Buttons row
        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        translate_btn = Gtk.Button(label="Pre-translate")
        translate_btn.connect("clicked", self._on_translate_current)
        btn_row.append(translate_btn)

        spell_btn = Gtk.Button(label="Spell check")
        spell_btn.connect("clicked", self._on_spellcheck_current)
        btn_row.append(spell_btn)

        # Undo / Redo
        undo_btn = Gtk.Button(icon_name="edit-undo-symbolic", tooltip_text="Undo (Ctrl+Z)")
        undo_btn.connect("clicked", lambda b: self._do_undo())
        btn_row.append(undo_btn)

        redo_btn = Gtk.Button(icon_name="edit-redo-symbolic", tooltip_text="Redo (Ctrl+Shift+Z)")
        redo_btn.connect("clicked", lambda b: self._do_redo())
        btn_row.append(redo_btn)

        self._fuzzy_check = Gtk.CheckButton(label="Fuzzy")
        self._fuzzy_check.connect("toggled", self._on_fuzzy_toggled)
        btn_row.append(self._fuzzy_check)

        right_box.append(btn_row)

        # Info label
        self._info_label = Gtk.Label(label="", xalign=0.0, wrap=True, selectable=True)
        right_box.append(self._info_label)

        paned.set_end_child(right_box)

        # Assemble
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_box.append(self._header)
        main_box.append(paned)
        self._toast_overlay.set_child(main_box)
        self.set_content(self._toast_overlay)

        # CSS for syntax highlighting tags and lint
        css = Gtk.CssProvider()
        css.load_from_string("""
            .format-spec { color: @accent_color; font-weight: bold; }
            .lint-error { background: alpha(@error_color, 0.15); }
        """)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    # ── Keyboard shortcuts ────────────────────────────────────────

    def _setup_keys(self):
        """1. Ctrl+↑/↓ navigate, Ctrl+Enter save+next, Ctrl+Z/Ctrl+Shift+Z undo/redo."""
        ctrl = Gtk.EventControllerKey()
        ctrl.connect("key-pressed", self._on_key_pressed)
        self.add_controller(ctrl)

    def _on_key_pressed(self, controller, keyval, keycode, state):
        ctrl = state & Gdk.ModifierType.CONTROL_MASK
        shift = state & Gdk.ModifierType.SHIFT_MASK
        if ctrl:
            if keyval == Gdk.KEY_Up:
                self._navigate(-1)
                return True
            elif keyval == Gdk.KEY_Down:
                self._navigate(1)
                return True
            elif keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
                self._save_current_entry()
                self._navigate(1)
                return True
            elif keyval == Gdk.KEY_z and not shift:
                self._do_undo()
                return True
            elif keyval == Gdk.KEY_z and shift:
                self._do_redo()
                return True
            elif keyval == Gdk.KEY_f:
                self._search_entry.grab_focus()
                return True
        return False

    def _navigate(self, delta: int):
        """Move selection by delta rows (skips hidden rows)."""
        if not self._file_data:
            return
        row = self._listbox.get_selected_row()
        if row is None:
            target_idx = 0
        else:
            target_idx = row.get_index() + delta
        # Find next visible row
        child = self._listbox.get_row_at_index(target_idx)
        while child and not child.get_visible():
            target_idx += delta
            child = self._listbox.get_row_at_index(target_idx)
        if child and child.get_visible():
            self._listbox.select_row(child)

    def _navigate_untranslated(self, direction: int):
        """Jump to the next/previous untranslated (or fuzzy) entry."""
        if not self._file_data:
            return
        entries = self._get_entries()
        current_row = self._listbox.get_selected_row()
        start = getattr(current_row, '_orig_index', -1) if current_row else -1

        # Build ordered list of orig indices as displayed
        displayed = []
        row = self._listbox.get_first_child()
        while row:
            if row.get_visible():
                displayed.append(getattr(row, '_orig_index', 0))
            row = row.get_next_sibling()

        if not displayed:
            return

        # Find current position in displayed list
        try:
            cur_pos = displayed.index(start)
        except ValueError:
            cur_pos = -1 if direction > 0 else len(displayed)

        # Search in direction
        pos = cur_pos + direction
        while 0 <= pos < len(displayed):
            oi = displayed[pos]
            msgid, msgstr, is_fuzzy = entries[oi]
            if not msgstr or is_fuzzy:
                # Select this row in listbox
                r = self._listbox.get_first_child()
                while r:
                    if getattr(r, '_orig_index', -1) == oi and r.get_visible():
                        self._listbox.select_row(r)
                        return
                    r = r.get_next_sibling()
            pos += direction

        self._show_toast("No more untranslated entries" if direction > 0 else "No previous untranslated entry")

    def _on_focus_search(self, btn):
        """Focus the search entry."""
        self._search_entry.grab_focus()

    def _on_hdr_filter_untranslated(self, btn):
        """Toggle untranslated-only filter from header button."""
        if btn.get_active():
            self._filter_untrans_btn.set_active(True)
        else:
            self._filter_all_btn.set_active(True)

    # ── Drag & drop (14) ─────────────────────────────────────────

    def _setup_dnd(self):
        drop = Gtk.DropTarget.new(Gio.File, Gdk.DragAction.COPY)
        drop.connect("drop", self._on_drop)
        self.add_controller(drop)

    def _on_drop(self, target, value, x, y):
        if isinstance(value, Gio.File):
            path = value.get_path()
            if path and Path(path).suffix in (".po", ".pot", ".ts", ".json"):
                self._load_file(path)
                return True
        return False

    # ── Undo / Redo (3) ──────────────────────────────────────────

    def _push_undo_snapshot(self):
        """Capture current translation text as undo snapshot."""
        if self._current_index < 0:
            return
        buf = self._trans_view.get_buffer()
        text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
        idx = self._current_index
        if idx not in self._undo_stacks:
            self._undo_stacks[idx] = []
        stack = self._undo_stacks[idx]
        if not stack or stack[-1] != text:
            stack.append(text)
            # Cap
            if len(stack) > 100:
                del stack[0]
        # Clear redo on new edit
        self._redo_stacks.pop(idx, None)

    def _do_undo(self):
        idx = self._current_index
        if idx < 0:
            return
        stack = self._undo_stacks.get(idx, [])
        if len(stack) < 2:
            return
        current = stack.pop()
        self._redo_stacks.setdefault(idx, []).append(current)
        prev = stack[-1]
        buf = self._trans_view.get_buffer()
        buf.handler_block_by_func(self._on_trans_buffer_changed)
        buf.set_text(prev)
        buf.handler_unblock_by_func(self._on_trans_buffer_changed)

    def _do_redo(self):
        idx = self._current_index
        if idx < 0:
            return
        stack = self._redo_stacks.get(idx, [])
        if not stack:
            return
        text = stack.pop()
        self._undo_stacks.setdefault(idx, []).append(text)
        buf = self._trans_view.get_buffer()
        buf.handler_block_by_func(self._on_trans_buffer_changed)
        buf.set_text(text)
        buf.handler_unblock_by_func(self._on_trans_buffer_changed)

    # ── Translation buffer change handler ─────────────────────────

    def _on_trans_buffer_changed(self, buf):
        """Push undo snapshot + run inline lint + apply syntax highlighting."""
        self._push_undo_snapshot()
        # Debounced lint
        if hasattr(self, '_lint_timeout_id') and self._lint_timeout_id:
            GLib.source_remove(self._lint_timeout_id)
        self._lint_timeout_id = GLib.timeout_add(400, self._run_inline_lint)
        # Apply format highlighting to translation view
        self._apply_format_tags(self._trans_view)

    # ── Inline linting (6) ────────────────────────────────────────

    def _run_inline_lint(self):
        self._lint_timeout_id = 0
        if self._current_index < 0 or not self._file_data:
            self._lint_inline_label.set_label("")
            return False
        entries = self._get_entries()
        if self._current_index >= len(entries):
            return False
        msgid, _, is_fuzzy = entries[self._current_index]
        buf = self._trans_view.get_buffer()
        msgstr = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
        flags = ["fuzzy"] if is_fuzzy else []
        issues = _lint_single(msgid, msgstr, flags)
        self._lint_cache[self._current_index] = issues
        if issues:
            lines = []
            for issue in issues[:5]:
                icon = "🔴" if issue.severity == "error" else ("🟡" if issue.severity == "warning" else "ℹ️")
                lines.append(f"{icon} {issue.message}")
            self._lint_inline_label.set_markup(
                "<span foreground='red'>" + GLib.markup_escape_text("\n".join(lines)) + "</span>"
            )
        else:
            self._lint_inline_label.set_label("")
        return False  # don't repeat

    # ── Syntax highlighting for format specifiers (9) ─────────────

    def _apply_format_tags(self, textview: Gtk.TextView):
        """Highlight format specifiers in a TextView."""
        buf = textview.get_buffer()
        # Create or get tag
        tag_table = buf.get_tag_table()
        tag = tag_table.lookup("fmt")
        if not tag:
            tag = buf.create_tag("fmt", foreground="#1c71d8", weight=Pango.Weight.BOLD)

        # Remove old tags
        buf.remove_tag(tag, buf.get_start_iter(), buf.get_end_iter())

        text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
        for m in _FMT_RE.finditer(text):
            start = buf.get_iter_at_offset(m.start())
            end = buf.get_iter_at_offset(m.end())
            buf.apply_tag(tag, start, end)

    def _apply_source_highlighting(self):
        """Apply format highlighting to source view."""
        self._apply_format_tags(self._source_view)

    # ── Info panel helpers ────────────────────────────────────────

    def _clear_info_panel(self):
        for row, label in [
            (self._translator_note_row, self._translator_note_label),
            (self._extracted_comment_row, self._extracted_comment_label),
            (self._msgctxt_row, self._msgctxt_label),
            (self._references_row, self._references_label),
            (self._flags_row, self._flags_label),
            (self._previous_row, self._previous_label),
        ]:
            row.set_visible(False)
            label.set_label("")

    @staticmethod
    def _make_info_row(title: str, value_label: Gtk.Label) -> Gtk.Box:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title_label = Gtk.Label(label=f"<b>{title}:</b>", xalign=0.0, use_markup=True)
        title_label.set_size_request(120, -1)
        title_label.set_valign(Gtk.Align.START)
        value_label.add_css_class("dim-label")
        row.append(title_label)
        row.append(value_label)
        return row

    # ── Actions ───────────────────────────────────────────────────

    def _setup_actions(self):
        for name, cb in [
            ("lint", self._on_lint),
            ("pretranslate", self._on_pretranslate_all),
            ("spellcheck", self._on_spellcheck_current_action),
            ("metadata", self._on_show_metadata),
            ("feed_tm", self._on_feed_tm),
            ("github_pr", self._on_github_pr),
            ("check_updates", self._on_check_updates),
            ("donate", self._on_donate),
            ("about", self._on_about),
            ("platform_settings", self._on_platform_settings),
            ("pull_transifex", lambda a, p: self._on_sync("transifex", "pull")),
            ("pull_weblate", lambda a, p: self._on_sync("weblate", "pull")),
            ("pull_crowdin", lambda a, p: self._on_sync("crowdin", "pull")),
            ("push_transifex", lambda a, p: self._on_sync("transifex", "push")),
            ("push_weblate", lambda a, p: self._on_sync("weblate", "push")),
            ("push_crowdin", lambda a, p: self._on_sync("crowdin", "push")),
        ]:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", cb)
            self.add_action(action)

        # Recent file actions
        recent = _load_recent()
        for i, rp in enumerate(recent[:8]):
            act = Gio.SimpleAction.new(f"open_recent_{i}", None)
            act.connect("activate", self._make_open_recent_cb(rp))
            self.add_action(act)

    def _make_open_recent_cb(self, path: str):
        def cb(action, param):
            self._load_file(path)
        return cb

    # ── File loading ──────────────────────────────────────────────

    def _on_open(self, btn):
        dialog = Gtk.FileDialog()
        ff = Gtk.FileFilter()
        ff.set_name("Translation files (PO, TS, JSON)")
        ff.add_pattern("*.po")
        ff.add_pattern("*.pot")
        ff.add_pattern("*.ts")
        ff.add_pattern("*.json")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(ff)
        dialog.set_filters(filters)
        dialog.open(self, None, self._on_open_response)

    def _on_open_response(self, dialog, result):
        try:
            f = dialog.open_finish(result)
            path = f.get_path()
            self._load_file(path)
        except GLib.Error:
            pass

    def _load_file(self, path: str):
        p = Path(path)
        if not p.exists():
            self._show_toast(f"File not found: {p}")
            return
        try:
            if p.suffix in (".po", ".pot"):
                self._file_data = parse_po(p)
                self._file_type = "po"
            elif p.suffix == ".ts":
                self._file_data = parse_ts(p)
                self._file_type = "ts"
            elif p.suffix == ".json":
                self._file_data = parse_json(p)
                self._file_type = "json"
            else:
                self._show_toast(f"Unsupported file type: {p.suffix}")
                return
        except Exception as e:
            self._show_toast(f"Error loading file: {e}")
            return

        self.set_title(f"Traduco — {p.name}")
        _add_recent(str(p))
        self._populate_list()
        self._update_stats()
        self._modified = False
        self._undo_stacks.clear()
        self._redo_stacks.clear()
        self._lint_cache.clear()

        # 12. File monitoring
        self._setup_file_monitor(p)

    # ── File monitoring (12) ──────────────────────────────────────

    def _setup_file_monitor(self, path: Path):
        if self._file_monitor:
            self._file_monitor.cancel()
        gfile = Gio.File.new_for_path(str(path))
        self._file_monitor = gfile.monitor_file(Gio.FileMonitorFlags.NONE, None)
        self._file_monitor.connect("changed", self._on_file_changed)

    def _on_file_changed(self, monitor, file, other_file, event_type):
        if event_type == Gio.FileMonitorEvent.CHANGES_DONE_HINT:
            # Debounce
            if self._reload_debounce_id:
                GLib.source_remove(self._reload_debounce_id)
            self._reload_debounce_id = GLib.timeout_add(500, self._reload_file)

    def _reload_file(self):
        self._reload_debounce_id = 0
        if not self._file_data:
            return False
        path = str(self._file_data.path)
        saved_idx = self._current_index
        self._load_file(path)
        # Restore selection
        row = self._listbox.get_row_at_index(saved_idx)
        if row:
            self._listbox.select_row(row)
        self._show_toast("File reloaded (changed externally)")
        return False

    # ── List population (11. Status icons) ────────────────────────

    def _populate_list(self):
        while row := self._listbox.get_first_child():
            self._listbox.remove(row)

        entries = self._get_entries()
        self._compute_sort_order()

        for display_pos, orig_idx in enumerate(self._sort_order):
            msgid, msgstr, is_fuzzy = entries[orig_idx]
            label_text = msgid[:80].replace("\n", " ") if msgid else "(empty)"
            row = Gtk.ListBoxRow()
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6,
                          margin_start=6, margin_end=6, margin_top=3, margin_bottom=3)

            # Status icon
            lint_issues = self._lint_cache.get(orig_idx, [])
            has_lint_error = any(iss.severity == "error" for iss in lint_issues)
            if has_lint_error:
                icon = "⚠️"
            elif is_fuzzy:
                icon = "🟡"
            elif msgstr:
                icon = "🟢"
            else:
                icon = "🔴"
            icon_label = Gtk.Label(label=icon)
            box.append(icon_label)

            text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            src_label = Gtk.Label(label=label_text, xalign=0.0, ellipsize=Pango.EllipsizeMode.END)
            text_box.append(src_label)
            trans_preview = msgstr[:50].replace("\n", " ") if msgstr else "—"
            status_label = Gtk.Label(label=trans_preview, xalign=0.0,
                                      ellipsize=Pango.EllipsizeMode.END, css_classes=["dim-label"])
            text_box.append(status_label)
            box.append(text_box)

            row.set_child(box)

            # Store entry data on row for filtering + original index
            row._entry_fuzzy = is_fuzzy
            row._entry_translated = bool(msgstr)
            row._orig_index = orig_idx

            self._listbox.append(row)

        self._apply_filter()

    def _get_entries(self) -> list[tuple[str, str, bool]]:
        if self._file_type == "po":
            return [(e.msgid, e.msgstr, e.fuzzy) for e in self._file_data.entries]
        elif self._file_type == "ts":
            return [(e.source, e.translation, e.is_fuzzy) for e in self._file_data.entries]
        elif self._file_type == "json":
            return [(e.key, e.value, False) for e in self._file_data.entries]
        return []

    # ── Sort ──────────────────────────────────────────────────────

    _SORT_MODES = ["file", "src_az", "src_za", "trans_az", "trans_za",
                   "status", "length", "reference"]

    def _on_sort_changed(self, dropdown, param):
        selected = dropdown.get_selected()
        if selected < len(self._SORT_MODES):
            self._sort_mode = self._SORT_MODES[selected]
            if self._file_data:
                self._save_current_entry()
                self._populate_list()

    def _get_reference(self, idx: int) -> str:
        """Return a sortable reference string for entry at original index."""
        if self._file_type == "po":
            e = self._file_data.entries[idx]
            if e.occurrences:
                return f"{e.occurrences[0][0]}:{e.occurrences[0][1]}"
        elif self._file_type == "ts":
            e = self._file_data.entries[idx]
            if e.location_file:
                return f"{e.location_file}:{e.location_line}"
        return ""

    def _compute_sort_order(self):
        """Compute self._sort_order based on current sort mode."""
        entries = self._get_entries()
        n = len(entries)
        indices = list(range(n))

        mode = self._sort_mode
        if mode == "file":
            self._sort_order = indices
        elif mode == "src_az":
            indices.sort(key=lambda i: entries[i][0].lower())
            self._sort_order = indices
        elif mode == "src_za":
            indices.sort(key=lambda i: entries[i][0].lower(), reverse=True)
            self._sort_order = indices
        elif mode == "trans_az":
            indices.sort(key=lambda i: entries[i][1].lower())
            self._sort_order = indices
        elif mode == "trans_za":
            indices.sort(key=lambda i: entries[i][1].lower(), reverse=True)
            self._sort_order = indices
        elif mode == "status":
            def status_key(i):
                _, msgstr, fuzzy = entries[i]
                if not msgstr:
                    return 0  # untranslated first
                if fuzzy:
                    return 1
                return 2  # translated last
            indices.sort(key=status_key)
            self._sort_order = indices
        elif mode == "length":
            indices.sort(key=lambda i: len(entries[i][0]))
            self._sort_order = indices
        elif mode == "reference":
            indices.sort(key=lambda i: self._get_reference(i))
            self._sort_order = indices
        else:
            self._sort_order = indices

    # ── Filter (5) ────────────────────────────────────────────────

    def _on_filter_toggled(self, btn, mode):
        if btn.get_active():
            self._filter_mode = mode
            self._apply_filter()

    def _apply_filter(self):
        query = self._search_entry.get_text().lower()
        entries = self._get_entries()
        row = self._listbox.get_first_child()
        while row:
            visible = True
            orig_idx = getattr(row, '_orig_index', 0)
            # Text filter
            if query and orig_idx < len(entries):
                msgid, msgstr, _ = entries[orig_idx]
                if query not in msgid.lower() and query not in msgstr.lower():
                    visible = False
            # Status filter
            if visible and self._filter_mode == "fuzzy":
                visible = getattr(row, '_entry_fuzzy', False)
            elif visible and self._filter_mode == "untranslated":
                visible = not getattr(row, '_entry_translated', True)
            row.set_visible(visible)
            row = row.get_next_sibling()

    # ── Stats (4) ─────────────────────────────────────────────────

    def _update_stats(self):
        if not self._file_data:
            self._stats_label.set_label("No file loaded")
            self._progress_bar.set_fraction(0)
            return
        d = self._file_data
        remaining = d.untranslated_count + getattr(d, 'fuzzy_count', 0)
        self._stats_label.set_label(
            f"{remaining} av {d.total_count} kvar | "
            f"{d.translated_count} translated | {getattr(d, 'fuzzy_count', 0)} fuzzy"
        )
        frac = d.translated_count / d.total_count if d.total_count else 1.0
        self._progress_bar.set_fraction(frac)

    # ── Row selection / editing ───────────────────────────────────

    def _on_row_selected(self, listbox, row):
        self._save_current_entry()
        if row is None:
            self._current_index = -1
            return
        # Use the original data index stored on the row
        self._current_index = getattr(row, '_orig_index', row.get_index())
        self._display_entry(self._current_index)

    def _display_entry(self, idx: int):
        entries = self._get_entries()
        if idx < 0 or idx >= len(entries):
            return
        msgid, msgstr, is_fuzzy = entries[idx]

        # Source
        self._source_view.get_buffer().set_text(msgid)
        self._apply_source_highlighting()

        # Translation
        buf = self._trans_view.get_buffer()
        buf.handler_block_by_func(self._on_trans_buffer_changed)
        buf.set_text(msgstr)
        buf.handler_unblock_by_func(self._on_trans_buffer_changed)
        self._apply_format_tags(self._trans_view)

        # Init undo stack for this entry
        if idx not in self._undo_stacks:
            self._undo_stacks[idx] = [msgstr]

        self._fuzzy_check.set_active(is_fuzzy)

        # 2. Plural support
        self._setup_plural_tabs(idx)

        # Info panel
        self._clear_info_panel()
        self._diff_frame.set_visible(False)

        if self._file_type == "po":
            e = self._file_data.entries[idx]
            if e.tcomment:
                self._translator_note_label.set_label(e.tcomment)
                self._translator_note_row.set_visible(True)
            if e.comment:
                self._extracted_comment_label.set_label(e.comment)
                self._extracted_comment_row.set_visible(True)
            if e.msgctxt:
                self._msgctxt_label.set_label(e.msgctxt)
                self._msgctxt_row.set_visible(True)
            if e.occurrences:
                refs = ", ".join(f"{f}:{l}" for f, l in e.occurrences[:8])
                if len(e.occurrences) > 8:
                    refs += f" (+{len(e.occurrences) - 8} more)"
                self._references_label.set_label(refs)
                self._references_row.set_visible(True)
            flags = [f for f in getattr(e, 'flags', []) if f != 'fuzzy']
            if flags:
                self._flags_label.set_label(", ".join(flags))
                self._flags_row.set_visible(True)
            prev = getattr(e, 'previous_msgid', None)
            if prev:
                self._previous_label.set_label(prev)
                self._previous_row.set_visible(True)
                # 8. Diff view
                self._show_fuzzy_diff(prev, e.msgid)

        elif self._file_type == "ts":
            e = self._file_data.entries[idx]
            if e.context_name:
                self._msgctxt_label.set_label(e.context_name)
                self._msgctxt_row.set_visible(True)
            if e.comment:
                self._extracted_comment_label.set_label(e.comment)
                self._extracted_comment_row.set_visible(True)
            if e.location_file:
                self._references_label.set_label(f"{e.location_file}:{e.location_line}")
                self._references_row.set_visible(True)

        elif self._file_type == "json":
            e = self._file_data.entries[idx]
            self._msgctxt_label.set_label(e.key)
            self._msgctxt_row.set_visible(True)

        self._info_label.set_label("")
        self._lint_inline_label.set_label("")

        # 7. TM suggestions
        self._show_tm_suggestions(msgid)

        # Run lint immediately
        self._run_inline_lint()

    # ── Plural tabs (2) ──────────────────────────────────────────

    def _setup_plural_tabs(self, idx: int):
        """Show plural form tabs if the entry has msgid_plural."""
        # Clear old tabs
        while self._plural_notebook.get_n_pages() > 0:
            self._plural_notebook.remove_page(0)

        if self._file_type != "po":
            self._plural_notebook.set_visible(False)
            self._trans_sw.set_visible(True)
            return

        entry = self._file_data.entries[idx]
        if not entry.msgid_plural:
            self._plural_notebook.set_visible(False)
            self._trans_sw.set_visible(True)
            return

        # Hide the normal translation view, show notebook
        self._trans_sw.set_visible(False)
        self._plural_notebook.set_visible(True)

        # Plural source info
        src_label = Gtk.Label(label=f"Plural: {entry.msgid_plural}", xalign=0.0, wrap=True,
                               margin_start=4, margin_top=4, css_classes=["dim-label"])
        self._plural_notebook.append_page(src_label, Gtk.Label(label="msgid_plural"))

        # Determine number of plural forms (default 2)
        n_forms = max(2, max(entry.msgstr_plural.keys(), default=1) + 1)
        self._plural_views: list[Gtk.TextView] = []
        for i in range(n_forms):
            tv = Gtk.TextView(editable=True, wrap_mode=Gtk.WrapMode.WORD_CHAR)
            tv.get_buffer().set_text(entry.msgstr_plural.get(i, ""))
            sw = Gtk.ScrolledWindow(child=tv, vexpand=True)
            sw.set_size_request(-1, 80)
            self._plural_notebook.append_page(sw, Gtk.Label(label=f"msgstr[{i}]"))
            self._plural_views.append(tv)

        # Show the first msgstr tab
        self._plural_notebook.set_current_page(1)

    def _save_plural_entries(self, idx: int):
        """Save plural form texts back to data model."""
        if self._file_type != "po":
            return
        entry = self._file_data.entries[idx]
        if not entry.msgid_plural:
            return
        if not hasattr(self, '_plural_views'):
            return
        changed = False
        for i, tv in enumerate(self._plural_views):
            buf = tv.get_buffer()
            text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
            if entry.msgstr_plural.get(i) != text:
                entry.msgstr_plural[i] = text
                changed = True
        if changed:
            self._modified = True

    # ── Fuzzy diff (8) ────────────────────────────────────────────

    def _show_fuzzy_diff(self, previous: str, current: str):
        """Show a simple diff between previous and current msgid."""
        if not previous or previous == current:
            self._diff_frame.set_visible(False)
            return
        # Simple word-level diff
        prev_words = previous.split()
        curr_words = current.split()
        sm = SequenceMatcher(None, prev_words, curr_words)
        parts = []
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == 'equal':
                parts.append(GLib.markup_escape_text(" ".join(prev_words[i1:i2])))
            elif tag == 'delete':
                parts.append(f"<span strikethrough='true' foreground='red'>{GLib.markup_escape_text(' '.join(prev_words[i1:i2]))}</span>")
            elif tag == 'insert':
                parts.append(f"<span foreground='green'>{GLib.markup_escape_text(' '.join(curr_words[j1:j2]))}</span>")
            elif tag == 'replace':
                parts.append(f"<span strikethrough='true' foreground='red'>{GLib.markup_escape_text(' '.join(prev_words[i1:i2]))}</span>")
                parts.append(f"<span foreground='green'>{GLib.markup_escape_text(' '.join(curr_words[j1:j2]))}</span>")
        self._diff_label.set_markup(" ".join(parts))
        self._diff_frame.set_visible(True)

    # ── TM suggestions (7) ────────────────────────────────────────

    def _show_tm_suggestions(self, msgid: str):
        """Show Translation Memory matches."""
        # Clear
        while child := self._tm_box.get_first_child():
            self._tm_box.remove(child)

        matches = lookup_tm(msgid, threshold=0.6, max_results=3)
        if not matches:
            self._tm_frame.set_visible(False)
            return

        self._tm_frame.set_visible(True)
        for m in matches:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            pct = Gtk.Label(label=f"{m.similarity:.0%}", css_classes=["dim-label"])
            row.append(pct)
            btn = Gtk.Button(label=m.target[:60])
            btn.set_tooltip_text(f"Source: {m.source}\nTarget: {m.target}")
            btn.connect("clicked", self._apply_tm_match, m.target)
            row.append(btn)
            self._tm_box.append(row)

    def _apply_tm_match(self, btn, text):
        self._trans_view.get_buffer().set_text(text)

    # ── Save current entry ────────────────────────────────────────

    def _save_current_entry(self):
        if self._current_index < 0 or not self._file_data:
            return

        # Save plural forms if applicable
        self._save_plural_entries(self._current_index)

        buf = self._trans_view.get_buffer()
        text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)

        if self._file_type == "po":
            entry = self._file_data.entries[self._current_index]
            if entry.msgstr != text:
                entry.msgstr = text
                self._modified = True
                # Add to TM
                if text.strip() and entry.msgid.strip():
                    add_to_tm(entry.msgid, text)
        elif self._file_type == "ts":
            entry = self._file_data.entries[self._current_index]
            if entry.translation != text:
                entry.translation = text
                if text and entry.translation_type == "unfinished":
                    entry.translation_type = ""
                self._modified = True
        elif self._file_type == "json":
            entry = self._file_data.entries[self._current_index]
            if entry.value != text:
                entry.value = text
                self._modified = True

    def _on_fuzzy_toggled(self, check):
        if self._current_index < 0 or not self._file_data:
            return
        if self._file_type == "po":
            entry = self._file_data.entries[self._current_index]
            if check.get_active():
                if "fuzzy" not in entry.flags:
                    entry.flags.append("fuzzy")
                entry.fuzzy = True
            else:
                entry.flags = [f for f in entry.flags if f != "fuzzy"]
                entry.fuzzy = False
            self._modified = True

    # ── Save file ─────────────────────────────────────────────────

    def _on_save(self, btn):
        self._save_current_entry()
        if not self._file_data:
            return
        # Temporarily disable file monitor to avoid reload loop
        if self._file_monitor:
            self._file_monitor.cancel()
        try:
            if self._file_type == "po":
                save_po(self._file_data)
            elif self._file_type == "ts":
                save_ts(self._file_data)
            elif self._file_type == "json":
                save_json(self._file_data)
            self._modified = False
            self._show_toast("Saved!")
            self._update_stats()
            self._populate_list()
        except Exception as e:
            self._show_toast(f"Save error: {e}")
        finally:
            # Re-enable monitor
            if self._file_data:
                self._setup_file_monitor(self._file_data.path)

    # ── Search ────────────────────────────────────────────────────

    def _on_search_changed(self, entry):
        self._apply_filter()

    # ── Lint ──────────────────────────────────────────────────────

    def _on_lint(self, action, param):
        if not self._file_data:
            self._show_toast("No file loaded")
            return
        self._save_current_entry()
        entries = self._get_entries()
        lint_input = []
        for i, (msgid, msgstr, is_fuzzy) in enumerate(entries):
            flags = ["fuzzy"] if is_fuzzy else []
            lint_input.append({"index": i, "msgid": msgid, "msgstr": msgstr, "flags": flags})
        result = lint_entries(lint_input)

        # Cache per-entry results
        self._lint_cache.clear()
        for issue in result.issues:
            self._lint_cache.setdefault(issue.entry_index, []).append(issue)

        # Refresh list to show ⚠️ icons
        self._populate_list()

        msg = (f"Quality score: {result.score}%\n"
               f"Errors: {result.error_count} | Warnings: {result.warning_count}\n\n")
        for issue in result.issues[:20]:
            src = issue.msgid[:40].replace("\n", " ")
            msg += f"[{issue.severity}] #{issue.entry_index}: {issue.message} — \"{src}\"\n"
        if len(result.issues) > 20:
            msg += f"\n… and {len(result.issues) - 20} more issues"
        self._show_dialog("Lint Results", msg)

    # ── Pre-translate ─────────────────────────────────────────────

    def _on_translate_current(self, btn):
        if self._current_index < 0 or not self._file_data:
            return
        entries = self._get_entries()
        msgid = entries[self._current_index][0]
        if not msgid:
            return
        try:
            result = translate(msgid, engine=self._trans_engine,
                               source=self._trans_source, target=self._trans_target)
            self._trans_view.get_buffer().set_text(result)
            self._info_label.set_label(f"Translated via {self._trans_engine}")
        except TranslationError as e:
            self._info_label.set_label(str(e))

    def _on_pretranslate_all(self, action, param):
        if not self._file_data:
            self._show_toast("No file loaded")
            return
        self._save_current_entry()
        count = 0
        entries = self._get_entries()
        for i, (msgid, msgstr, _) in enumerate(entries):
            if msgstr or not msgid:
                continue
            try:
                result = translate(msgid, engine=self._trans_engine,
                                   source=self._trans_source, target=self._trans_target)
                if result:
                    if self._file_type == "po":
                        self._file_data.entries[i].msgstr = result
                    elif self._file_type == "ts":
                        self._file_data.entries[i].translation = result
                    elif self._file_type == "json":
                        self._file_data.entries[i].value = result
                    count += 1
            except TranslationError:
                continue
        self._modified = True
        self._populate_list()
        self._update_stats()
        self._show_toast(f"Pre-translated {count} entries via {self._trans_engine}")

    # ── Feed TM ───────────────────────────────────────────────────

    def _on_feed_tm(self, action, param):
        if not self._file_data:
            self._show_toast("No file loaded")
            return
        entries = self._get_entries()
        pairs = [(msgid, msgstr) for msgid, msgstr, _ in entries if msgid and msgstr]
        count = feed_file_to_tm(pairs)
        self._show_toast(f"Added {count} entries to Translation Memory")

    # ── Spellcheck ────────────────────────────────────────────────

    def _on_spellcheck_current(self, btn):
        self._run_spellcheck()

    def _on_spellcheck_current_action(self, action, param):
        self._run_spellcheck()

    def _run_spellcheck(self):
        buf = self._trans_view.get_buffer()
        text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
        if not text:
            self._info_label.set_label("No text to check")
            return
        issues = check_text(text, language=self._spell_lang)
        if not issues:
            self._info_label.set_label("✓ No spelling issues found")
        else:
            msg = "\n".join(
                f"'{i.word}' → {', '.join(i.suggestions[:3]) or '(no suggestions)'}"
                for i in issues[:10]
            )
            self._info_label.set_label(f"Spelling issues:\n{msg}")

    # ── Metadata ──────────────────────────────────────────────────

    def _on_show_metadata(self, action, param):
        if not self._file_data:
            self._show_toast("No file loaded")
            return
        if self._file_type == "po":
            meta = self._file_data.metadata
            lines = [f"{k}: {v}" for k, v in meta.items()]
            text = "\n".join(lines) or "No metadata"
        elif self._file_type == "ts":
            text = f"Language: {self._file_data.language}\nSource language: {self._file_data.source_language}"
        elif self._file_type == "json":
            text = f"File: {self._file_data.path.name}\nEntries: {self._file_data.total_count}"
        else:
            text = "No metadata"
        self._show_dialog("File Metadata", text)

    # ── GitHub PR ─────────────────────────────────────────────────

    def _on_github_pr(self, action, param):
        self._show_dialog("GitHub PR", "To push a PR, configure your GitHub token in\nPreferences → GitHub.\n\nThis feature will:\n1. Ask for auth token\n2. Fetch POT from the repo\n3. Create a branch\n4. Push your translation\n5. Open a PR\n\n(Full implementation in services/github.py)")

    # ── Updates ───────────────────────────────────────────────────

    def _on_check_updates(self, action, param):
        from traduco.services.updater import check_for_updates
        update = check_for_updates()
        if update:
            self._show_dialog("Update Available",
                              f"Version {update['version']} is available!\n\n{update['url']}")
        else:
            self._show_dialog("Up to date", f"You are running the latest version ({__version__}).")

    # ── Donate ────────────────────────────────────────────────────

    def _on_donate(self, action, param):
        self._show_dialog(
            "Donate ♥",
            "Traduco is free software.\n\n"
            "If you find it useful, consider supporting development:\n\n"
            "• GitHub Sponsors: github.com/sponsors/danielnylander\n"
            "• Ko-fi: ko-fi.com/danielnylander\n"
            "• PayPal: paypal.me/danielnylander"
        )

    # ── About ─────────────────────────────────────────────────────

    def _on_about(self, action, param):
        about = Adw.AboutWindow(
            application_name="Traduco",
            application_icon="accessories-text-editor",
            version=__version__,
            developer_name="Daniel Nylander",
            license_type=Gtk.License.GPL_3_0,
            website="https://github.com/yeager/traduco",
            issue_url="https://github.com/yeager/traduco/issues",
            developers=["Daniel Nylander <po@danielnylander.se>"],
            copyright="© 2025 Daniel Nylander",
            comments="A translation file editor for PO, TS, and JSON files.",
            transient_for=self,
        )
        about.present()

    # ── Platform integration ─────────────────────────────────────

    def _on_platform_settings(self, action, param):
        dialog = PlatformSettingsDialog(self)
        dialog.present()

    def _on_sync(self, platform: str, mode: str):
        file_content = None
        file_name = ""
        if mode == "push" and self._file_data:
            self._save_current_entry()
            path = self._file_data.path
            try:
                file_content = Path(path).read_bytes()
                file_name = Path(path).name
            except Exception:
                pass
        dialog = SyncDialog(self, platform, mode, file_content, file_name)
        dialog.set_on_file_downloaded(self._load_file)
        dialog.present()

    # ── Helpers ───────────────────────────────────────────────────

    def _show_toast(self, message: str):
        toast = Adw.Toast(title=message, timeout=3)
        self._toast_overlay.add_toast(toast)

    def _show_dialog(self, title: str, body: str):
        dialog = Adw.MessageDialog(
            heading=title,
            body=body,
            transient_for=self,
        )
        dialog.add_response("ok", "OK")
        dialog.present()
