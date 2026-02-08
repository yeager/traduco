"""Main application window — full-featured translation editor.

UI layout inspired by POedit and Qt Linguist:
  ┌─────────────────────────────────────────────────────────────┐
  │ Menu bar                                                     │
  │ Toolbar                                                      │
  ├─────────────────────────────────────────────────┬───────────┤
  │ Entry table (source | translation | status)     │ TM / Side │
  │                                                 │ panel     │
  ├─────────────────────────────────────────────────┤           │
  │ Source (read-only)                              │           │
  │ ─────────────────                               │           │
  │ Translation (editable)                          │           │
  │ [Fuzzy] [Needs work] info                       │           │
  ├─────────────────────────────────────────────────┴───────────┤
  │ Status bar: file | format | T: n | F: n | U: n | progress   │
  └─────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional
from html import escape as html_escape

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTreeWidget, QTreeWidgetItem, QHeaderView,
    QTextEdit, QPlainTextEdit,
    QLabel, QPushButton, QCheckBox, QComboBox, QLineEdit,
    QProgressBar, QMenu, QStatusBar, QTabWidget,
    QToolBar, QFrame, QScrollArea, QGroupBox, QTableWidget, QTableWidgetItem,
    QDialog, QDialogButtonBox, QFormLayout, QFileDialog,
    QMessageBox, QInputDialog, QApplication, QToolButton,
    QAbstractItemView,
)
from PySide6.QtCore import Qt, QTimer, QFileSystemWatcher, Signal, Slot
from PySide6.QtGui import (
    QAction, QKeySequence, QFont, QColor, QIcon, QBrush,
    QDragEnterEvent, QDropEvent, QPalette, QShortcut, QDesktopServices,
)
from PySide6.QtCore import QUrl

from linguaedit import APP_ID, __version__
from linguaedit.parsers.po_parser import parse_po, save_po, POFileData, TranslationEntry
from linguaedit.parsers.ts_parser import parse_ts, save_ts, TSFileData
from linguaedit.parsers.json_parser import parse_json, save_json, JSONFileData
from linguaedit.parsers.xliff_parser import parse_xliff, save_xliff, XLIFFFileData
from linguaedit.parsers.android_parser import parse_android, save_android, AndroidFileData
from linguaedit.parsers.arb_parser import parse_arb, save_arb, ARBFileData
from linguaedit.parsers.php_parser import parse_php, save_php, PHPFileData
from linguaedit.parsers.yaml_parser import parse_yaml, save_yaml, YAMLFileData
from linguaedit.services.linter import lint_entries, LintResult, LintIssue
from linguaedit.services.spellcheck import check_text, available_languages
from linguaedit.services.translator import translate, ENGINES, TranslationError
from linguaedit.services.tm import lookup_tm, add_to_tm, feed_file_to_tm
from linguaedit.services.glossary import get_terms, add_term, remove_term, check_glossary
from linguaedit.services.qa_profiles import get_profiles, check_profile
from linguaedit.services.report import generate_report
from linguaedit.services.git_integration import (
    get_status, get_diff, stage_file, commit, get_branches, switch_branch, create_branch
)
from linguaedit.ui.platform_dialog import PlatformSettingsDialog
from linguaedit.ui.sync_dialog import SyncDialog
from linguaedit.services.settings import Settings

# ── Recent files helper ──────────────────────────────────────────────

_RECENT_FILE = Path.home() / ".config" / "linguaedit" / "recent.json"


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


# ── Comment threads storage ──────────────────────────────────────────

_COMMENTS_FILE = Path.home() / ".config" / "linguaedit" / "comments.json"


def _load_comments() -> dict:
    try:
        return json.loads(_COMMENTS_FILE.read_text("utf-8"))
    except Exception:
        return {}


def _save_comments(data: dict) -> None:
    _COMMENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _COMMENTS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")


# ── Format specifier regex ───────────────────────────────────────────

_FMT_RE = re.compile(
    r'%[\d$]*[-+ #0]*\d*\.?\d*[hlLqjzt]*[sdiufxXoecpg%]'
    r'|\{[^}]*\}'
    r'|%\([^)]+\)[sdiufxXoecpg]'
)


# ── Supported file extensions ────────────────────────────────────────

_ALL_EXTENSIONS = {
    ".po", ".pot", ".ts", ".json", ".xliff", ".xlf",
    ".xml", ".arb", ".php", ".yml", ".yaml",
}

_FILE_FILTER = "Translation files (*.po *.pot *.ts *.json *.xliff *.xlf *.xml *.arb *.php *.yml *.yaml)"


# ── Inline linting for a single entry ────────────────────────────────

def _lint_single(msgid: str, msgstr: str, flags: list[str]) -> list[LintIssue]:
    result = lint_entries([{"index": 0, "msgid": msgid, "msgstr": msgstr, "flags": flags}])
    return result.issues


# ── Color constants (POedit-inspired) ────────────────────────────────

# Light theme colors
_LIGHT_COLORS = {
    'translated': QColor(230, 248, 230),
    'untranslated': QColor(248, 240, 240),
    'fuzzy': QColor(252, 248, 230),
    'warning': QColor(252, 242, 225),
    'translated_fg': QColor(30, 130, 50),
    'untranslated_fg': QColor(160, 50, 50),
    'fuzzy_fg': QColor(160, 120, 20),
}

# Dark theme colors
_DARK_COLORS = {
    'translated': QColor(25, 50, 30),
    'untranslated': QColor(55, 25, 25),
    'fuzzy': QColor(55, 48, 20),
    'warning': QColor(55, 40, 15),
    'translated_fg': QColor(80, 200, 100),
    'untranslated_fg': QColor(230, 100, 100),
    'fuzzy_fg': QColor(230, 190, 60),
}

def _is_dark_theme():
    """Detect if the system/app is using a dark theme."""
    palette = QApplication.instance().palette()
    bg = palette.color(QPalette.Window)
    return bg.lightness() < 128

def _get_colors():
    """Return the appropriate color set for the current theme."""
    return _DARK_COLORS if _is_dark_theme() else _LIGHT_COLORS

# Defaults (updated at runtime)
_CLR_TRANSLATED = _LIGHT_COLORS['translated']
_CLR_UNTRANSLATED = _LIGHT_COLORS['untranslated']
_CLR_FUZZY = _LIGHT_COLORS['fuzzy']
_CLR_WARNING = _LIGHT_COLORS['warning']
_CLR_TRANSLATED_FG = _LIGHT_COLORS['translated_fg']
_CLR_UNTRANSLATED_FG = _LIGHT_COLORS['untranslated_fg']
_CLR_FUZZY_FG = _LIGHT_COLORS['fuzzy_fg']


# ── Tab data holder ──────────────────────────────────────────────────

class TabData:
    """Data associated with a single editor tab."""
    def __init__(self):
        self.file_data = None
        self.file_type = None
        self.file_path = None
        self.current_index = -1
        self.modified = False
        self.undo_stacks: dict[int, list[str]] = {}
        self.redo_stacks: dict[int, list[str]] = {}
        self.lint_cache: dict[int, list[LintIssue]] = {}
        self.filter_mode = "all"
        self.sort_mode = "file"
        self.sort_order: list[int] = []
        self.search_text = ""


# ── Custom tree item with numeric sort on column 0 ───────────────────

class _SortableItem(QTreeWidgetItem):
    """QTreeWidgetItem that sorts column 0 numerically."""
    def __lt__(self, other):
        col = self.treeWidget().sortColumn() if self.treeWidget() else 0
        if col == 0:
            try:
                return int(self.text(0)) < int(other.text(0))
            except ValueError:
                pass
        return self.text(col).lower() < other.text(col).lower()


# ── Window ────────────────────────────────────────────────────────────

class LinguaEditWindow(QMainWindow):
    """Main editor window — POedit / Qt Linguist inspired layout."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("LinguaEdit")
        self.resize(1200, 800)
        self.setAcceptDrops(True)

        # Window icon
        _icon_path = Path(__file__).parent.parent.parent.parent / "resources" / "icon.png"
        if _icon_path.exists():
            self.setWindowIcon(QIcon(str(_icon_path)))
            self._app_icon_path = str(_icon_path)
        else:
            self._app_icon_path = None

        # File state
        self._file_data = None
        self._file_type = None
        self._current_index = -1
        self._modified = False
        self._app_settings = Settings.get()
        self._spell_lang = "en_US"
        self._trans_engine = self._app_settings["default_engine"]
        self._trans_source = self._app_settings["source_language"]
        self._trans_target = self._app_settings["target_language"]

        # Undo/redo stacks per entry index
        self._undo_stacks: dict[int, list[str]] = {}
        self._redo_stacks: dict[int, list[str]] = {}

        # Lint cache per entry index
        self._lint_cache: dict[int, list[LintIssue]] = {}

        # File watcher
        self._file_watcher: QFileSystemWatcher | None = None
        self._reload_timer = QTimer()
        self._reload_timer.setSingleShot(True)
        self._reload_timer.setInterval(500)
        self._reload_timer.timeout.connect(self._reload_file)

        # Filter & sort
        self._filter_mode = "all"
        self._sort_mode = "file"
        self._sort_order: list[int] = []
        self._search_replace_visible = False
        self._search_match_count = 0
        self._selected_indices: set[int] = set()

        # Tabs
        self._tabs: dict[int, TabData] = {}

        # Split view
        self._split_file_data = None
        self._split_file_type = None

        # Lint timer
        self._lint_timer = QTimer()
        self._lint_timer.setSingleShot(True)
        self._lint_timer.setInterval(400)
        self._lint_timer.timeout.connect(self._run_inline_lint)

        # Block recursive text change signals
        self._trans_block = False

        self._build_ui()
        self._apply_settings()
        self._setup_shortcuts()

    # ── Settings ──────────────────────────────────────────────────

    def _apply_settings(self):
        s = self._app_settings
        scheme = s["color_scheme"]
        app = QApplication.instance()
        if scheme == "dark":
            palette = QPalette()
            palette.setColor(QPalette.Window, QColor(53, 53, 53))
            palette.setColor(QPalette.WindowText, Qt.white)
            palette.setColor(QPalette.Base, QColor(35, 35, 35))
            palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
            palette.setColor(QPalette.ToolTipBase, QColor(25, 25, 25))
            palette.setColor(QPalette.ToolTipText, Qt.white)
            palette.setColor(QPalette.Text, Qt.white)
            palette.setColor(QPalette.Button, QColor(53, 53, 53))
            palette.setColor(QPalette.ButtonText, Qt.white)
            palette.setColor(QPalette.Link, QColor(42, 130, 218))
            palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
            palette.setColor(QPalette.HighlightedText, Qt.black)
            app.setPalette(palette)
        else:
            app.setStyleSheet("")
            app.setPalette(app.style().standardPalette())

        font_size = s["editor_font_size"]
        font = QFont()
        font.setPointSize(font_size)
        if hasattr(self, '_trans_view'):
            self._trans_view.setFont(font)
        if hasattr(self, '_source_view'):
            self._source_view.setFont(font)

        self._trans_engine = s["default_engine"]
        self._trans_source = s["source_language"]
        self._trans_target = s["target_language"]

    def _on_preferences(self):
        from linguaedit.ui.preferences_dialog import PreferencesDialog
        dialog = PreferencesDialog(self)
        dialog.exec()

    # ══════════════════════════════════════════════════════════════
    #  UI CONSTRUCTION
    # ══════════════════════════════════════════════════════════════

    def _build_ui(self):
        self._build_menu_bar()
        self._build_toolbar()

        # ── Tab bar for multiple open files ──
        self._tab_widget = QTabWidget()
        self._tab_widget.setTabsClosable(True)
        self._tab_widget.setDocumentMode(True)
        self._tab_widget.currentChanged.connect(self._on_tab_changed)
        self._tab_widget.tabCloseRequested.connect(self._on_tab_close)

        # ── Main horizontal splitter: [editor area | side panel] ──
        outer_splitter = QSplitter(Qt.Horizontal)

        # ── Left: vertical splitter [entry table | editors] ──
        self._v_splitter = QSplitter(Qt.Vertical)

        # ── Top: entry table with filter bar ──
        table_container = QWidget()
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(2)

        # Filter / search bar above table
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(4)

        self._filter_combo = QComboBox()
        self._filter_combo.addItems([self.tr("All strings"), self.tr("Untranslated"), self.tr("Fuzzy / Needs work"),
                                      self.tr("Translated"), self.tr("With warnings")])
        self._filter_combo.setMinimumWidth(140)
        self._filter_combo.currentIndexChanged.connect(self._on_filter_combo_changed)
        filter_bar.addWidget(self._filter_combo)

        self._search_entry = QLineEdit()
        self._search_entry.setPlaceholderText(self.tr("Search source and translation text…"))
        self._search_entry.setClearButtonEnabled(True)
        self._search_entry.textChanged.connect(self._on_search_changed)
        filter_bar.addWidget(self._search_entry, 1)

        # Sort dropdown
        self._sort_combo = QComboBox()
        self._sort_combo.addItems([
            self.tr("File order"), self.tr("Source A → Z"), self.tr("Source Z → A"),
            self.tr("Translation A → Z"), self.tr("Translation Z → A"),
            self.tr("By status"), self.tr("By length"), self.tr("By reference"),
        ])
        self._sort_combo.setMinimumWidth(120)
        self._sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        filter_bar.addWidget(self._sort_combo)

        table_layout.addLayout(filter_bar)

        # Search & Replace panel (hidden by default)
        self._search_replace_box = QWidget()
        sr_layout = QHBoxLayout(self._search_replace_box)
        sr_layout.setContentsMargins(0, 0, 0, 0)
        sr_layout.setSpacing(4)

        self._sr_search_entry = QLineEdit()
        self._sr_search_entry.setPlaceholderText(self.tr("Find in translations…"))
        self._sr_search_entry.textChanged.connect(self._on_sr_search_changed)
        sr_layout.addWidget(self._sr_search_entry, 1)

        self._sr_replace_entry = QLineEdit()
        self._sr_replace_entry.setPlaceholderText(self.tr("Replace with…"))
        sr_layout.addWidget(self._sr_replace_entry, 1)

        self._sr_regex_check = QCheckBox(self.tr("Regex"))
        sr_layout.addWidget(self._sr_regex_check)

        sr_replace_btn = QPushButton(self.tr("Replace"))
        sr_replace_btn.clicked.connect(self._on_sr_replace)
        sr_layout.addWidget(sr_replace_btn)

        sr_replace_all_btn = QPushButton(self.tr("Replace All"))
        sr_replace_all_btn.clicked.connect(self._on_sr_replace_all)
        sr_layout.addWidget(sr_replace_all_btn)

        self._sr_match_label = QLabel("")
        sr_layout.addWidget(self._sr_match_label)

        self._search_replace_box.setVisible(False)
        table_layout.addWidget(self._search_replace_box)

        # The entry table (QTreeWidget — POedit-style columns)
        self._tree = QTreeWidget()
        self._tree.setRootIsDecorated(False)
        self._tree.setAlternatingRowColors(True)
        self._tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._tree.setUniformRowHeights(True)
        self._tree.setHeaderLabels(["#", self.tr("Source text"), self.tr("Translation"), ""])
        self._tree.setSortingEnabled(True)
        header = self._tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._tree.currentItemChanged.connect(self._on_tree_item_changed)
        table_layout.addWidget(self._tree, 1)

        # Progress bar under table
        progress_row = QHBoxLayout()
        progress_row.setSpacing(8)
        self._progress_bar = QProgressBar()
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFormat(self.tr("%p% translated"))
        self._progress_bar.setMaximumHeight(18)
        progress_row.addWidget(self._progress_bar, 1)
        self._stats_label = QLabel(self.tr("No file loaded"))
        progress_row.addWidget(self._stats_label)
        table_layout.addLayout(progress_row)

        self._v_splitter.addWidget(table_container)

        # ── Bottom: source + translation editors ──
        editor_container = QWidget()
        editor_layout = QVBoxLayout(editor_container)
        editor_layout.setContentsMargins(0, 4, 0, 0)
        editor_layout.setSpacing(4)

        # Fuzzy diff (hidden by default)
        self._diff_frame = QGroupBox(self.tr("Fuzzy diff (previous → current)"))
        diff_inner = QVBoxLayout(self._diff_frame)
        self._diff_label = QLabel()
        self._diff_label.setWordWrap(True)
        self._diff_label.setTextFormat(Qt.RichText)
        diff_inner.addWidget(self._diff_label)
        self._diff_frame.setVisible(False)
        editor_layout.addWidget(self._diff_frame)

        # Source label + view
        self._source_header = QLabel(self.tr("<b>Source text:</b>"))
        editor_layout.addWidget(self._source_header)
        self._source_view = QTextEdit()
        self._source_view.setReadOnly(True)
        self._source_view.setMaximumHeight(90)
        self._source_view.setFrameShape(QFrame.StyledPanel)
        self._source_view.setStyleSheet("QTextEdit { background: palette(alternate-base); }")
        editor_layout.addWidget(self._source_view)

        # Translation label + view
        self._trans_header = QLabel(self.tr("<b>Translation:</b>"))
        editor_layout.addWidget(self._trans_header)
        self._trans_view = QTextEdit()
        self._trans_view.setFrameShape(QFrame.StyledPanel)
        self._trans_view.textChanged.connect(self._on_trans_buffer_changed)
        editor_layout.addWidget(self._trans_view, 1)

        # Plural tabs (shown for plural entries only)
        self._plural_notebook = QTabWidget()
        self._plural_notebook.setVisible(False)
        editor_layout.addWidget(self._plural_notebook)

        # Inline lint warnings
        self._lint_inline_label = QLabel()
        self._lint_inline_label.setWordWrap(True)
        editor_layout.addWidget(self._lint_inline_label)

        # Action bar under translation editor (POedit-style)
        action_bar = QHBoxLayout()
        action_bar.setSpacing(4)

        self._fuzzy_check = QCheckBox(self.tr("Needs work"))
        self._fuzzy_check.setToolTip(self.tr("Mark this string as fuzzy / needs review (Ctrl+U)"))
        self._fuzzy_check.toggled.connect(self._on_fuzzy_toggled)
        action_bar.addWidget(self._fuzzy_check)

        action_bar.addStretch()

        copy_src_btn = QPushButton(self.tr("Copy source"))
        copy_src_btn.setToolTip(self.tr("Copy source text to translation (Ctrl+B)"))
        copy_src_btn.clicked.connect(self._copy_source_to_target)
        action_bar.addWidget(copy_src_btn)

        clear_btn = QPushButton(self.tr("Clear"))
        clear_btn.setToolTip(self.tr("Clear translation"))
        clear_btn.clicked.connect(lambda: self._trans_view.clear())
        action_bar.addWidget(clear_btn)

        comment_btn = QPushButton(self.tr("💬 Comment"))
        comment_btn.clicked.connect(self._on_add_comment)
        action_bar.addWidget(comment_btn)

        editor_layout.addLayout(action_bar)

        # Info label (spellcheck results, etc.)
        self._info_label = QLabel()
        self._info_label.setWordWrap(True)
        editor_layout.addWidget(self._info_label)

        self._v_splitter.addWidget(editor_container)
        self._v_splitter.setSizes([400, 350])

        outer_splitter.addWidget(self._v_splitter)

        # ── Right: side panel (TM, string info, concordance) ──
        self._side_panel = QTabWidget()
        self._side_panel.setMinimumWidth(250)
        self._side_panel.setMaximumWidth(400)

        # String Information tab
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(4, 4, 4, 4)

        self._translator_note_label = QLabel()
        self._translator_note_label.setWordWrap(True)
        self._translator_note_row = self._make_info_row("Notes", self._translator_note_label)
        info_layout.addWidget(self._translator_note_row)

        self._extracted_comment_label = QLabel()
        self._extracted_comment_label.setWordWrap(True)
        self._extracted_comment_row = self._make_info_row("Developer", self._extracted_comment_label)
        info_layout.addWidget(self._extracted_comment_row)

        self._msgctxt_label = QLabel()
        self._msgctxt_label.setWordWrap(True)
        self._msgctxt_row = self._make_info_row("Context", self._msgctxt_label)
        info_layout.addWidget(self._msgctxt_row)

        self._references_label = QLabel()
        self._references_label.setWordWrap(True)
        self._references_row = self._make_info_row("References", self._references_label)
        info_layout.addWidget(self._references_row)

        self._flags_label = QLabel()
        self._flags_label.setWordWrap(True)
        self._flags_row = self._make_info_row("Flags", self._flags_label)
        info_layout.addWidget(self._flags_row)

        self._previous_label = QLabel()
        self._previous_label.setWordWrap(True)
        self._previous_row = self._make_info_row("Previous", self._previous_label)
        info_layout.addWidget(self._previous_row)

        self._comments_label = QLabel()
        self._comments_label.setWordWrap(True)
        self._comments_label.setTextFormat(Qt.RichText)
        self._comments_row = self._make_info_row("Comments", self._comments_label)
        info_layout.addWidget(self._comments_row)

        info_layout.addStretch()

        info_scroll = QScrollArea()
        info_scroll.setWidget(info_widget)
        info_scroll.setWidgetResizable(True)
        self._side_panel.addTab(info_scroll, self.tr("String Info"))

        # Translation Memory tab
        tm_widget = QWidget()
        tm_layout_outer = QVBoxLayout(tm_widget)
        tm_layout_outer.setContentsMargins(4, 4, 4, 4)
        tm_label = QLabel(self.tr("<b>Suggestions</b>"))
        tm_layout_outer.addWidget(tm_label)
        self._tm_layout = QVBoxLayout()
        tm_layout_outer.addLayout(self._tm_layout)
        self._tm_no_match_label = QLabel(self.tr("<i>No suggestions</i>"))
        self._tm_no_match_label.setStyleSheet("color: gray;")
        tm_layout_outer.addWidget(self._tm_no_match_label)

        # Concordance search
        tm_layout_outer.addWidget(QLabel(self.tr("<b>Concordance search</b>")))
        self._concordance_entry = QLineEdit()
        self._concordance_entry.setPlaceholderText(self.tr("Search TM…"))
        self._concordance_entry.setClearButtonEnabled(True)
        self._concordance_entry.textChanged.connect(self._on_concordance_search)
        tm_layout_outer.addWidget(self._concordance_entry)
        self._concordance_results = QVBoxLayout()
        tm_layout_outer.addLayout(self._concordance_results)
        tm_layout_outer.addStretch()

        tm_scroll = QScrollArea()
        tm_scroll.setWidget(tm_widget)
        tm_scroll.setWidgetResizable(True)
        self._side_panel.addTab(tm_scroll, self.tr("TM / Suggestions"))

        # Split / reference view tab
        split_widget = QWidget()
        split_layout = QVBoxLayout(split_widget)
        split_layout.setContentsMargins(4, 4, 4, 4)
        self._split_source_label = QLabel()
        self._split_source_label.setWordWrap(True)
        split_layout.addWidget(QLabel(self.tr("<b>Reference source:</b>")))
        split_layout.addWidget(self._split_source_label)
        split_layout.addWidget(QLabel(self.tr("<b>Reference translation:</b>")))
        self._split_trans_label = QLabel()
        self._split_trans_label.setWordWrap(True)
        split_layout.addWidget(self._split_trans_label)
        split_layout.addStretch()
        self._side_panel.addTab(split_widget, self.tr("Reference"))

        outer_splitter.addWidget(self._side_panel)
        outer_splitter.setSizes([850, 300])

        # ── Central widget ──
        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(self._tab_widget)
        central_layout.addWidget(outer_splitter, 1)
        self.setCentralWidget(central)

        # ── Status Bar (POedit-style) ──
        sb = self.statusBar()
        self._sb_filename = QLabel(self.tr("No file"))
        sb.addWidget(self._sb_filename)
        sb.addWidget(self._make_separator())
        self._sb_format = QLabel("")
        sb.addWidget(self._sb_format)
        sb.addWidget(self._make_separator())
        self._sb_total = QLabel("")
        sb.addWidget(self._sb_total)
        sb.addWidget(self._make_separator())
        self._sb_translated = QLabel(self.tr("Translated: 0"))
        sb.addWidget(self._sb_translated)
        sb.addWidget(self._make_separator())
        self._sb_fuzzy = QLabel(self.tr("Fuzzy: 0"))
        sb.addWidget(self._sb_fuzzy)
        sb.addWidget(self._make_separator())
        self._sb_untranslated = QLabel(self.tr("Untranslated: 0"))
        sb.addWidget(self._sb_untranslated)
        sb.addPermanentWidget(QLabel(""))
        self._sb_cursor = QLabel(self.tr("Ln 1, Col 1"))
        sb.addPermanentWidget(self._sb_cursor)

        self._trans_view.cursorPositionChanged.connect(self._on_cursor_position_changed)

    @staticmethod
    def _make_separator() -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFrameShadow(QFrame.Sunken)
        return sep

    # ── Menu Bar ──────────────────────────────────────────────────

    def _build_menu_bar(self):
        mb = self.menuBar()

        # File
        file_menu = mb.addMenu(self.tr("&File"))
        open_act = file_menu.addAction(self.tr("&Open…"))
        open_act.setShortcut(QKeySequence.Open)
        open_act.triggered.connect(self._on_open)

        save_act = file_menu.addAction(self.tr("&Save"))
        save_act.setShortcut(QKeySequence.Save)
        save_act.triggered.connect(self._on_save)

        file_menu.addSeparator()
        self._recent_menu = file_menu.addMenu(self.tr("Recent Files"))
        self._rebuild_recent_menu()

        file_menu.addSeparator()
        close_act = file_menu.addAction(self.tr("Close Tab"))
        close_act.setShortcut(QKeySequence("Ctrl+W"))
        close_act.triggered.connect(lambda: self._on_tab_close(self._tab_widget.currentIndex()))

        file_menu.addSeparator()
        file_menu.addAction(self.tr("Quit"), QApplication.quit, QKeySequence.Quit)

        # Edit
        edit_menu = mb.addMenu(self.tr("&Edit"))
        edit_menu.addAction(self.tr("Undo"), self._do_undo, QKeySequence.Undo)
        edit_menu.addAction(self.tr("Redo"), self._do_redo, QKeySequence.Redo)
        edit_menu.addSeparator()
        edit_menu.addAction(self.tr("Find…"), self._on_focus_search, QKeySequence.Find)
        edit_menu.addAction(self.tr("Find && Replace…"), self._toggle_search_replace, QKeySequence("Ctrl+H"))
        edit_menu.addSeparator()
        edit_menu.addAction(self.tr("Copy source to translation"), self._copy_source_to_target, QKeySequence("Ctrl+B"))
        edit_menu.addSeparator()
        edit_menu.addAction(self.tr("Preferences…"), self._on_preferences, QKeySequence("Ctrl+,"))

        # Catalog (POedit calls it this)
        catalog_menu = mb.addMenu(self.tr("&Catalog"))
        catalog_menu.addAction(self.tr("Validate (Lint)"), self._on_lint, QKeySequence("Ctrl+Shift+V"))
        catalog_menu.addAction(self.tr("Pre-translate…"), self._on_pretranslate_all, QKeySequence("Ctrl+Shift+T"))
        catalog_menu.addAction(self.tr("Spell check current"), self._run_spellcheck, QKeySequence("F7"))
        catalog_menu.addAction(self.tr("File metadata…"), self._on_show_metadata)
        catalog_menu.addAction(self.tr("Feed file to TM"), self._on_feed_tm)
        catalog_menu.addSeparator()
        catalog_menu.addAction(self.tr("Statistics…"), self._on_statistics)
        catalog_menu.addSeparator()
        catalog_menu.addAction(self.tr("Compile translation"), self._on_compile, QKeySequence("Ctrl+Shift+B"))

        qa_menu = catalog_menu.addMenu(self.tr("Quality"))
        qa_menu.addAction(self.tr("Consistency check"), self._on_consistency_check)
        qa_menu.addAction(self.tr("Glossary…"), self._on_glossary)
        qa_menu.addAction(self.tr("QA profile: Formal"), lambda: self._on_qa_profile("formal"))
        qa_menu.addAction(self.tr("QA profile: Informal"), lambda: self._on_qa_profile("informal"))
        qa_menu.addAction(self.tr("Export report…"), self._on_export_report)

        # Go
        go_menu = mb.addMenu(self.tr("&Go"))
        go_menu.addAction(self.tr("Previous entry"), lambda: self._navigate(-1), QKeySequence("Ctrl+Up"))
        go_menu.addAction(self.tr("Next entry"), lambda: self._navigate(1), QKeySequence("Ctrl+Down"))
        go_menu.addSeparator()
        go_menu.addAction(self.tr("Previous untranslated"), lambda: self._navigate_untranslated(-1), QKeySequence("Ctrl+Shift+Up"))
        go_menu.addAction(self.tr("Next untranslated"), lambda: self._navigate_untranslated(1), QKeySequence("Ctrl+Shift+Down"))
        go_menu.addSeparator()
        go_menu.addAction(self.tr("Done and next (Ctrl+Enter)"), lambda: (self._save_current_entry(), self._navigate(1)))

        # View
        view_menu = mb.addMenu(self.tr("&View"))
        view_menu.addAction(self.tr("Compare language…"), self._on_compare_lang)
        view_menu.addAction(self.tr("Auto-propagate"), self._on_auto_propagate)
        view_menu.addSeparator()
        theme_menu = view_menu.addMenu(self.tr("Theme"))
        theme_menu.addAction(self.tr("System"), lambda: self._set_theme("system"))
        theme_menu.addAction(self.tr("Light"), lambda: self._set_theme("light"))
        theme_menu.addAction(self.tr("Dark"), lambda: self._set_theme("dark"))

        # Git
        git_menu = mb.addMenu(self.tr("&Git"))
        git_menu.addAction(self.tr("Status…"), self._on_git_status)
        git_menu.addAction(self.tr("Diff…"), self._on_git_diff)
        git_menu.addAction(self.tr("Commit…"), self._on_git_commit)
        git_menu.addAction(self.tr("Switch branch…"), self._on_git_branch)

        # Platforms
        platform_menu = mb.addMenu(self.tr("&Platforms"))
        platform_menu.addAction(self.tr("Platform settings…"), self._on_platform_settings)
        platform_menu.addSeparator()
        pull_menu = platform_menu.addMenu(self.tr("Pull from…"))
        pull_menu.addAction(self.tr("Transifex"), lambda: self._on_sync("transifex", "pull"))
        pull_menu.addAction(self.tr("Weblate"), lambda: self._on_sync("weblate", "pull"))
        pull_menu.addAction(self.tr("Crowdin"), lambda: self._on_sync("crowdin", "pull"))
        push_menu = platform_menu.addMenu(self.tr("Push to…"))
        push_menu.addAction(self.tr("Transifex"), lambda: self._on_sync("transifex", "push"))
        push_menu.addAction(self.tr("Weblate"), lambda: self._on_sync("weblate", "push"))
        push_menu.addAction(self.tr("Crowdin"), lambda: self._on_sync("crowdin", "push"))

        # Help
        help_menu = mb.addMenu(self.tr("&Help"))
        help_menu.addAction(self.tr("GitHub PR…"), self._on_github_pr)
        help_menu.addAction(self.tr("Check for updates"), self._on_check_updates)
        help_menu.addAction(self.tr("GitHub Repository"), lambda: QDesktopServices.openUrl(QUrl("https://github.com/yeager/linguaedit")))
        help_menu.addAction(self.tr("Report a Bug"), lambda: QDesktopServices.openUrl(QUrl("https://github.com/yeager/linguaedit/issues")))
        help_menu.addSeparator()
        help_menu.addAction(self.tr("Donate ♥"), self._on_donate)
        help_menu.addSeparator()
        help_menu.addAction(self.tr("About LinguaEdit"), self._on_about)
        help_menu.addAction(self.tr("About Qt"), lambda: QApplication.instance().aboutQt())

    # ── Toolbar ───────────────────────────────────────────────────

    def _build_toolbar(self):
        tb = QToolBar("Main")
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.addToolBar(tb)

        style = self.style()

        # File operations
        open_act = tb.addAction(style.standardIcon(style.StandardPixmap.SP_DirOpenIcon), self.tr("Open"), self._on_open)
        open_act.setShortcut(QKeySequence.Open)
        save_act = tb.addAction(style.standardIcon(style.StandardPixmap.SP_DialogSaveButton), self.tr("Save"), self._on_save)
        save_act.setShortcut(QKeySequence.Save)
        tb.addSeparator()

        # Undo / Redo
        tb.addAction(style.standardIcon(style.StandardPixmap.SP_ArrowBack), self.tr("Undo"), self._do_undo)
        tb.addAction(style.standardIcon(style.StandardPixmap.SP_ArrowForward), self.tr("Redo"), self._do_redo)
        tb.addSeparator()

        # Navigation
        tb.addAction(style.standardIcon(style.StandardPixmap.SP_ArrowUp), self.tr("Previous"), lambda: self._navigate(-1))
        self._nav_counter_label = QLabel(" 0 / 0 ")
        self._nav_counter_label.setStyleSheet("font-weight: bold; padding: 0 4px;")
        tb.addWidget(self._nav_counter_label)
        tb.addAction(style.standardIcon(style.StandardPixmap.SP_ArrowDown), self.tr("Next"), lambda: self._navigate(1))
        tb.addSeparator()

        # Copy Source
        tb.addAction(style.standardIcon(style.StandardPixmap.SP_FileIcon), self.tr("Copy Source"), self._copy_source_to_target)
        tb.addSeparator()

        # Pre-translate
        tb.addAction(style.standardIcon(style.StandardPixmap.SP_BrowserReload), self.tr("Pre-translate"), self._on_pretranslate_all)

        # Translation engine
        self._engine_dropdown = QComboBox()
        engine_keys = list(ENGINES.keys())
        for k in engine_keys:
            self._engine_dropdown.addItem(ENGINES[k]["name"], k)
        try:
            self._engine_dropdown.setCurrentIndex(engine_keys.index(self._trans_engine))
        except ValueError:
            pass
        self._engine_dropdown.setMinimumWidth(120)
        tb.addWidget(self._engine_dropdown)
        tb.addSeparator()

        # Validate
        tb.addAction(style.standardIcon(style.StandardPixmap.SP_DialogApplyButton), self.tr("Validate"), self._on_lint)
        tb.addSeparator()

        # Compile
        tb.addAction(style.standardIcon(style.StandardPixmap.SP_MediaPlay), self.tr("Compile"), self._on_compile)

    # ── Keyboard shortcuts ────────────────────────────────────────

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+Return"), self, lambda: (self._save_current_entry(), self._navigate(1)))
        QShortcut(QKeySequence("Ctrl+U"), self, lambda: self._fuzzy_check.toggle())

    # ══════════════════════════════════════════════════════════════
    #  ENTRY TABLE (QTreeWidget)
    # ══════════════════════════════════════════════════════════════

    def _populate_list(self):
        self._tree.blockSignals(True)
        self._tree.setSortingEnabled(False)
        self._tree.clear()

        entries = self._get_entries()
        self._compute_sort_order()

        for orig_idx in self._sort_order:
            msgid, msgstr, is_fuzzy = entries[orig_idx]
            lint_issues = self._lint_cache.get(orig_idx, [])
            has_warning = any(iss.severity in ("error", "warning") for iss in lint_issues)

            # Status icon
            if has_warning:
                status = "⚠"
            elif is_fuzzy:
                status = "🔶"
            elif msgstr:
                status = "✓"
            else:
                status = "●"

            src_preview = msgid[:200].replace("\n", "⏎ ") if msgid else "(empty)"
            trans_preview = msgstr[:200].replace("\n", "⏎ ") if msgstr else ""

            item = _SortableItem([str(orig_idx + 1), src_preview, trans_preview, status])
            item.setData(0, Qt.UserRole, orig_idx)

            # Row colors (theme-aware)
            colors = _get_colors()
            if has_warning:
                self._color_row(item, colors['warning'])
            elif is_fuzzy:
                self._color_row(item, colors['fuzzy'])
            elif not msgstr:
                self._color_row(item, colors['untranslated'])

            # Status column color
            if not msgstr:
                item.setForeground(3, QBrush(colors['untranslated_fg']))
            elif is_fuzzy:
                item.setForeground(3, QBrush(colors['fuzzy_fg']))
            elif msgstr:
                item.setForeground(3, QBrush(colors['translated_fg']))

            self._tree.addTopLevelItem(item)

        self._tree.setSortingEnabled(True)
        self._tree.blockSignals(False)
        self._apply_filter()
        self._update_nav_counter()

    @staticmethod
    def _color_row(item: QTreeWidgetItem, color: QColor):
        brush = QBrush(color)
        for col in range(4):
            item.setBackground(col, brush)

    def _on_tree_item_changed(self, current: QTreeWidgetItem | None, previous: QTreeWidgetItem | None):
        self._save_current_entry()
        if current is None:
            self._current_index = -1
            return
        idx = current.data(0, Qt.UserRole)
        if idx is not None:
            self._current_index = idx
            self._display_entry(idx)

    def _navigate(self, delta: int):
        if not self._file_data:
            return
        count = self._tree.topLevelItemCount()
        current = self._tree.currentItem()
        if current is None:
            if count > 0:
                self._tree.setCurrentItem(self._tree.topLevelItem(0))
            return

        cur_row = self._tree.indexOfTopLevelItem(current)
        target = cur_row + delta
        while 0 <= target < count:
            item = self._tree.topLevelItem(target)
            if not item.isHidden():
                self._tree.setCurrentItem(item)
                self._tree.scrollToItem(item)
                return
            target += delta

    def _navigate_untranslated(self, direction: int):
        if not self._file_data:
            return
        entries = self._get_entries()
        count = self._tree.topLevelItemCount()
        current = self._tree.currentItem()
        cur_row = self._tree.indexOfTopLevelItem(current) if current else -1

        row = cur_row + direction
        while 0 <= row < count:
            item = self._tree.topLevelItem(row)
            if not item.isHidden():
                orig_idx = item.data(0, Qt.UserRole)
                if orig_idx is not None and orig_idx < len(entries):
                    _, msgstr, is_fuzzy = entries[orig_idx]
                    if not msgstr or is_fuzzy:
                        self._tree.setCurrentItem(item)
                        self._tree.scrollToItem(item)
                        return
            row += direction

        self._show_toast(self.tr("No more untranslated strings"))

    # ══════════════════════════════════════════════════════════════
    #  ENTRY DISPLAY / EDITING
    # ══════════════════════════════════════════════════════════════

    def _display_entry(self, idx: int):
        entries = self._get_entries()
        if idx < 0 or idx >= len(entries):
            return
        msgid, msgstr, is_fuzzy = entries[idx]

        self._source_view.setPlainText(msgid)
        self._source_header.setText(f"<b>{self.tr('Source text')}</b>  <span style='color:gray'>({len(msgid.split())} {self.tr('words')})</span>")

        self._trans_block = True
        self._trans_view.setPlainText(msgstr)
        self._trans_block = False

        if idx not in self._undo_stacks:
            self._undo_stacks[idx] = [msgstr]

        self._fuzzy_check.blockSignals(True)
        self._fuzzy_check.setChecked(is_fuzzy)
        self._fuzzy_check.blockSignals(False)

        self._setup_plural_tabs(idx)
        self._clear_info_panel()
        self._diff_frame.setVisible(False)

        # File-type specific info
        if self._file_type == "po":
            e = self._file_data.entries[idx]
            if e.tcomment:
                self._translator_note_label.setText(e.tcomment)
                self._translator_note_row.setVisible(True)
            if e.comment:
                self._extracted_comment_label.setText(e.comment)
                self._extracted_comment_row.setVisible(True)
            if e.msgctxt:
                self._msgctxt_label.setText(e.msgctxt)
                self._msgctxt_row.setVisible(True)
            if e.occurrences:
                refs = ", ".join(f"{f}:{l}" for f, l in e.occurrences[:8])
                if len(e.occurrences) > 8:
                    refs += f" (+{len(e.occurrences) - 8} more)"
                self._references_label.setText(refs)
                self._references_row.setVisible(True)
            flags = [f for f in getattr(e, 'flags', []) if f != 'fuzzy']
            if flags:
                self._flags_label.setText(", ".join(flags))
                self._flags_row.setVisible(True)
            prev = getattr(e, 'previous_msgid', None)
            if prev:
                self._previous_label.setText(prev)
                self._previous_row.setVisible(True)
                self._show_fuzzy_diff(prev, e.msgid)
        elif self._file_type == "ts":
            e = self._file_data.entries[idx]
            if e.context_name:
                self._msgctxt_label.setText(e.context_name)
                self._msgctxt_row.setVisible(True)
            if e.comment:
                self._extracted_comment_label.setText(e.comment)
                self._extracted_comment_row.setVisible(True)
            if e.location_file:
                self._references_label.setText(f"{e.location_file}:{e.location_line}")
                self._references_row.setVisible(True)
        elif self._file_type == "json":
            e = self._file_data.entries[idx]
            self._msgctxt_label.setText(e.key)
            self._msgctxt_row.setVisible(True)
        elif self._file_type == "xliff":
            e = self._file_data.entries[idx]
            if e.note:
                self._extracted_comment_label.setText(e.note)
                self._extracted_comment_row.setVisible(True)
            if e.id:
                self._msgctxt_label.setText(f"ID: {e.id}")
                self._msgctxt_row.setVisible(True)
            if e.state:
                self._flags_label.setText(f"State: {e.state}")
                self._flags_row.setVisible(True)
        elif self._file_type == "arb":
            e = self._file_data.entries[idx]
            if e.description:
                self._extracted_comment_label.setText(e.description)
                self._extracted_comment_row.setVisible(True)
            self._msgctxt_label.setText(e.key)
            self._msgctxt_row.setVisible(True)
        elif self._file_type in ("android", "php", "yaml"):
            entries_list = self._file_data.entries
            if idx < len(entries_list):
                e = entries_list[idx]
                self._msgctxt_label.setText(e.key)
                self._msgctxt_row.setVisible(True)
                if hasattr(e, 'comment') and e.comment:
                    self._extracted_comment_label.setText(e.comment)
                    self._extracted_comment_row.setVisible(True)

        self._info_label.setText("")
        self._lint_inline_label.setText("")
        self._show_tm_suggestions(msgid)
        self._display_comment_threads()
        self._update_split_view(idx)
        self._run_inline_lint()

        # Focus translation editor
        self._trans_view.setFocus()

    def _copy_source_to_target(self):
        if self._current_index < 0 or not self._file_data:
            return
        entries = self._get_entries()
        if self._current_index < len(entries):
            self._trans_view.setPlainText(entries[self._current_index][0])

    # ── Plural tabs ───────────────────────────────────────────────

    def _setup_plural_tabs(self, idx: int):
        self._plural_notebook.clear()
        if self._file_type != "po":
            self._plural_notebook.setVisible(False)
            self._trans_view.setVisible(True)
            return
        entry = self._file_data.entries[idx]
        if not entry.msgid_plural:
            self._plural_notebook.setVisible(False)
            self._trans_view.setVisible(True)
            return
        self._trans_view.setVisible(False)
        self._plural_notebook.setVisible(True)
        src_label = QLabel(f"Plural: {entry.msgid_plural}")
        src_label.setWordWrap(True)
        self._plural_notebook.addTab(src_label, "msgid_plural")
        n_forms = max(2, max(entry.msgstr_plural.keys(), default=1) + 1)
        self._plural_views: list[QTextEdit] = []
        for i in range(n_forms):
            tv = QTextEdit()
            tv.setPlainText(entry.msgstr_plural.get(i, ""))
            self._plural_notebook.addTab(tv, f"msgstr[{i}]")
            self._plural_views.append(tv)
        self._plural_notebook.setCurrentIndex(1)

    def _save_plural_entries(self, idx: int):
        if self._file_type != "po":
            return
        entry = self._file_data.entries[idx]
        if not entry.msgid_plural or not hasattr(self, '_plural_views'):
            return
        changed = False
        for i, tv in enumerate(self._plural_views):
            text = tv.toPlainText()
            if entry.msgstr_plural.get(i) != text:
                entry.msgstr_plural[i] = text
                changed = True
        if changed:
            self._modified = True

    # ── Fuzzy diff ────────────────────────────────────────────────

    def _show_fuzzy_diff(self, previous: str, current: str):
        if not previous or previous == current:
            self._diff_frame.setVisible(False)
            return
        prev_words = previous.split()
        curr_words = current.split()
        sm = SequenceMatcher(None, prev_words, curr_words)
        parts = []
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == 'equal':
                parts.append(html_escape(" ".join(prev_words[i1:i2])))
            elif tag == 'delete':
                parts.append(f"<s style='color:red'>{html_escape(' '.join(prev_words[i1:i2]))}</s>")
            elif tag == 'insert':
                parts.append(f"<span style='color:green'>{html_escape(' '.join(curr_words[j1:j2]))}</span>")
            elif tag == 'replace':
                parts.append(f"<s style='color:red'>{html_escape(' '.join(prev_words[i1:i2]))}</s>")
                parts.append(f"<span style='color:green'>{html_escape(' '.join(curr_words[j1:j2]))}</span>")
        self._diff_label.setText(" ".join(parts))
        self._diff_frame.setVisible(True)

    # ── Translation buffer ────────────────────────────────────────

    def _on_trans_buffer_changed(self):
        if self._trans_block:
            return
        self._push_undo_snapshot()
        self._lint_timer.start()

    # ── Inline linting ────────────────────────────────────────────

    def _run_inline_lint(self):
        if self._current_index < 0 or not self._file_data:
            self._lint_inline_label.setText("")
            return
        entries = self._get_entries()
        if self._current_index >= len(entries):
            return
        msgid, _, is_fuzzy = entries[self._current_index]
        msgstr = self._trans_view.toPlainText()
        flags = ["fuzzy"] if is_fuzzy else []
        issues = _lint_single(msgid, msgstr, flags)
        self._lint_cache[self._current_index] = issues
        if issues:
            lines = []
            for issue in issues[:5]:
                icon = "🔴" if issue.severity == "error" else ("🟡" if issue.severity == "warning" else "ℹ️")
                lines.append(f"{icon} {issue.message}")
            self._lint_inline_label.setText("\n".join(lines))
            self._lint_inline_label.setStyleSheet("color: #c00;")
        else:
            self._lint_inline_label.setText("")
            self._lint_inline_label.setStyleSheet("")

    # ── Info panel ────────────────────────────────────────────────

    def _clear_info_panel(self):
        for row, label in [
            (self._translator_note_row, self._translator_note_label),
            (self._extracted_comment_row, self._extracted_comment_label),
            (self._msgctxt_row, self._msgctxt_label),
            (self._references_row, self._references_label),
            (self._flags_row, self._flags_label),
            (self._previous_row, self._previous_label),
            (self._comments_row, self._comments_label),
        ]:
            row.setVisible(False)
            label.setText("")

    @staticmethod
    def _make_info_row(title: str, value_label: QLabel) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 2, 0, 2)
        title_label = QLabel(f"<b>{title}:</b>")
        title_label.setFixedWidth(80)
        title_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        layout.addWidget(title_label)
        layout.addWidget(value_label, 1)
        return row

    # ── TM suggestions ────────────────────────────────────────────

    def _show_tm_suggestions(self, msgid: str):
        while self._tm_layout.count():
            item = self._tm_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        matches = lookup_tm(msgid, threshold=0.6, max_results=5)
        if not matches:
            self._tm_no_match_label.setVisible(True)
            return
        self._tm_no_match_label.setVisible(False)
        for m in matches:
            container = QWidget()
            row = QVBoxLayout(container)
            row.setContentsMargins(2, 2, 2, 2)
            row.setSpacing(1)
            pct_label = QLabel(f"<b>{m.similarity:.0%}</b> match")
            pct_label.setStyleSheet("color: gray; font-size: 10px;")
            row.addWidget(pct_label)
            btn = QPushButton(m.target[:80])
            btn.setToolTip(f"Source: {m.source}\nTarget: {m.target}")
            btn.setStyleSheet("text-align: left; padding: 4px;")
            btn.clicked.connect(lambda checked, t=m.target: self._apply_tm_match(t))
            row.addWidget(btn)
            self._tm_layout.addWidget(container)

    def _apply_tm_match(self, text):
        self._trans_view.setPlainText(text)

    # ── Concordance search ────────────────────────────────────────

    def _on_concordance_search(self, query):
        while self._concordance_results.count():
            item = self._concordance_results.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not query or len(query) < 2:
            return
        matches = lookup_tm(query, threshold=0.3, max_results=10)
        for m in matches:
            btn = QPushButton(f"[{m.similarity:.0%}] {m.target[:60]}")
            btn.setToolTip(f"Source: {m.source}\nTarget: {m.target}")
            btn.setStyleSheet("text-align: left; padding: 2px;")
            btn.clicked.connect(lambda checked, t=m.target: self._apply_tm_match(t))
            self._concordance_results.addWidget(btn)

    # ── Comment threads ───────────────────────────────────────────

    def _on_add_comment(self):
        if self._current_index < 0 or not self._file_data:
            return
        existing = ""
        if self._file_type == "po":
            existing = self._file_data.entries[self._current_index].tcomment or ""
        text, ok = QInputDialog.getText(self, self.tr("Add Comment"), self.tr("Enter translator note:"), text=existing)
        if ok and self._current_index >= 0:
            if self._file_type == "po":
                self._file_data.entries[self._current_index].tcomment = text
                self._modified = True
                self._display_entry(self._current_index)
            self._save_comment_thread(text)

    def _save_comment_thread(self, text: str):
        if not self._file_data or self._current_index < 0:
            return
        entries = self._get_entries()
        msgid = entries[self._current_index][0]
        key = f"{self._file_data.path}:{msgid[:50]}"
        comments = _load_comments()
        thread = comments.get(key, [])
        if text:
            from datetime import datetime
            thread.append({"text": text, "date": datetime.now().isoformat(), "author": "translator"})
        comments[key] = thread
        _save_comments(comments)

    def _display_comment_threads(self):
        if not self._file_data or self._current_index < 0:
            self._comments_row.setVisible(False)
            return
        entries = self._get_entries()
        msgid = entries[self._current_index][0]
        key = f"{self._file_data.path}:{msgid[:50]}"
        comments = _load_comments()
        thread = comments.get(key, [])
        if not thread:
            self._comments_row.setVisible(False)
            return
        lines = []
        for c in thread[-5:]:
            date = c.get("date", "")[:10]
            author = c.get("author", "")
            text = c.get("text", "")
            lines.append(f"<b>{html_escape(author)}</b> ({date}): {html_escape(text)}")
        self._comments_label.setText("<br>".join(lines))
        self._comments_row.setVisible(True)

    # ══════════════════════════════════════════════════════════════
    #  FILTER / SORT / SEARCH
    # ══════════════════════════════════════════════════════════════

    def _on_filter_combo_changed(self, index):
        modes = ["all", "untranslated", "fuzzy", "translated", "warnings"]
        if index < len(modes):
            self._filter_mode = modes[index]
            self._apply_filter()

    def _on_search_changed(self, text):
        self._apply_filter()

    _SORT_MODES = ["file", "src_az", "src_za", "trans_az", "trans_za",
                   "status", "length", "reference"]

    def _on_sort_changed(self, index):
        if index < len(self._SORT_MODES):
            self._sort_mode = self._SORT_MODES[index]
            if self._file_data:
                self._save_current_entry()
                self._populate_list()

    def _apply_filter(self):
        query = self._search_entry.text().lower()
        entries = self._get_entries()

        visible_count = 0
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            orig_idx = item.data(0, Qt.UserRole)
            visible = True

            if query and orig_idx is not None and orig_idx < len(entries):
                msgid, msgstr, _ = entries[orig_idx]
                if query not in msgid.lower() and query not in msgstr.lower():
                    visible = False

            if visible and orig_idx is not None and orig_idx < len(entries):
                _, msgstr, is_fuzzy = entries[orig_idx]
                lint_issues = self._lint_cache.get(orig_idx, [])
                has_warning = any(iss.severity in ("error", "warning") for iss in lint_issues)

                if self._filter_mode == "untranslated":
                    visible = not bool(msgstr)
                elif self._filter_mode == "fuzzy":
                    visible = is_fuzzy
                elif self._filter_mode == "translated":
                    visible = bool(msgstr) and not is_fuzzy
                elif self._filter_mode == "warnings":
                    visible = has_warning

            item.setHidden(not visible)
            if visible:
                visible_count += 1

        if query:
            self._show_toast(self.tr("%d matches") % visible_count)

    def _update_nav_counter(self):
        entries = self._get_entries()
        untranslated = sum(1 for _, msgstr, fuzzy in entries if not msgstr or fuzzy)
        total = len(entries)
        self._nav_counter_label.setText(f" {untranslated} / {total} ")

    def _get_entries(self) -> list[tuple[str, str, bool]]:
        if not self._file_data:
            return []
        if self._file_type == "po":
            return [(e.msgid, e.msgstr, e.fuzzy) for e in self._file_data.entries]
        elif self._file_type == "ts":
            return [(e.source, e.translation, e.is_fuzzy) for e in self._file_data.entries]
        elif self._file_type == "json":
            return [(e.key, e.value, False) for e in self._file_data.entries]
        elif self._file_type == "xliff":
            return [(e.source, e.target, e.is_fuzzy) for e in self._file_data.entries]
        elif self._file_type == "android":
            return [(e.key, e.value, False) for e in self._file_data.entries]
        elif self._file_type == "arb":
            return [(e.key, e.value, False) for e in self._file_data.entries]
        elif self._file_type == "php":
            return [(e.key, e.value, False) for e in self._file_data.entries]
        elif self._file_type == "yaml":
            return [(e.key, e.value, False) for e in self._file_data.entries]
        return []

    def _get_reference(self, idx: int) -> str:
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
                return 0 if not msgstr else (1 if fuzzy else 2)
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

    # ── Search & Replace ─────────────────────────────────────────

    def _on_focus_search(self):
        self._search_entry.setFocus()
        self._search_entry.selectAll()

    def _toggle_search_replace(self):
        self._search_replace_visible = not self._search_replace_visible
        self._search_replace_box.setVisible(self._search_replace_visible)
        if self._search_replace_visible:
            self._sr_search_entry.setFocus()

    def _on_sr_search_changed(self, text):
        if not text or not self._file_data:
            self._sr_match_label.setText("")
            return
        use_regex = self._sr_regex_check.isChecked()
        entries = self._get_entries()
        count = 0
        try:
            pattern = re.compile(text, re.IGNORECASE) if use_regex else None
        except re.error:
            self._sr_match_label.setText(self.tr("Invalid regex"))
            return
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            orig_idx = item.data(0, Qt.UserRole)
            if orig_idx is not None and orig_idx < len(entries):
                _, msgstr, _ = entries[orig_idx]
                if use_regex and pattern:
                    match = bool(pattern.search(msgstr))
                else:
                    match = text.lower() in msgstr.lower()
                item.setHidden(not match)
                if match:
                    count += 1
        self._sr_match_label.setText(self.tr("%d matches") % count)

    def _on_sr_replace(self):
        if self._current_index < 0 or not self._file_data:
            return
        search = self._sr_search_entry.text()
        replace = self._sr_replace_entry.text()
        if not search:
            return
        text = self._trans_view.toPlainText()
        if self._sr_regex_check.isChecked():
            try:
                new_text = re.sub(search, replace, text, count=1)
            except re.error:
                return
        else:
            new_text = text.replace(search, replace, 1)
        if new_text != text:
            self._trans_view.setPlainText(new_text)

    def _on_sr_replace_all(self):
        if not self._file_data:
            return
        search = self._sr_search_entry.text()
        replace = self._sr_replace_entry.text()
        if not search:
            return
        self._save_current_entry()
        use_regex = self._sr_regex_check.isChecked()
        count = 0
        entries = self._get_entries()
        for i in range(len(entries)):
            _, msgstr, _ = entries[i]
            if not msgstr:
                continue
            if use_regex:
                try:
                    new_text = re.sub(search, replace, msgstr)
                except re.error:
                    return
            else:
                new_text = msgstr.replace(search, replace)
            if new_text != msgstr:
                self._set_entry_translation(i, new_text)
                count += 1
        self._modified = True
        self._populate_list()
        self._show_toast(self.tr("Replaced in %d entries") % count)

    # ══════════════════════════════════════════════════════════════
    #  UNDO / REDO
    # ══════════════════════════════════════════════════════════════

    def _push_undo_snapshot(self):
        if self._current_index < 0:
            return
        text = self._trans_view.toPlainText()
        idx = self._current_index
        if idx not in self._undo_stacks:
            self._undo_stacks[idx] = []
        stack = self._undo_stacks[idx]
        if not stack or stack[-1] != text:
            stack.append(text)
            if len(stack) > 100:
                del stack[0]
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
        self._trans_block = True
        self._trans_view.setPlainText(stack[-1])
        self._trans_block = False

    def _do_redo(self):
        idx = self._current_index
        if idx < 0:
            return
        stack = self._redo_stacks.get(idx, [])
        if not stack:
            return
        text = stack.pop()
        self._undo_stacks.setdefault(idx, []).append(text)
        self._trans_block = True
        self._trans_view.setPlainText(text)
        self._trans_block = False

    # ══════════════════════════════════════════════════════════════
    #  MASS ENTRY OPERATIONS
    # ══════════════════════════════════════════════════════════════

    def _set_entry_translation(self, idx: int, text: str):
        if self._file_type == "po":
            self._file_data.entries[idx].msgstr = text
        elif self._file_type == "ts":
            self._file_data.entries[idx].translation = text
        elif self._file_type == "json":
            self._file_data.entries[idx].value = text
        elif self._file_type in ("xliff",):
            self._file_data.entries[idx].target = text
        elif self._file_type in ("android", "arb", "php", "yaml"):
            self._file_data.entries[idx].value = text

    def _set_entry_fuzzy(self, idx: int, fuzzy: bool):
        if self._file_type == "po":
            entry = self._file_data.entries[idx]
            if fuzzy:
                if "fuzzy" not in entry.flags:
                    entry.flags.append("fuzzy")
                entry.fuzzy = True
            else:
                entry.flags = [f for f in entry.flags if f != "fuzzy"]
                entry.fuzzy = False

    # ── Auto-propagate ────────────────────────────────────────────

    def _set_theme(self, theme: str):
        """Set application theme: system, light, or dark."""
        from PySide6.QtWidgets import QStyleFactory
        app = QApplication.instance()
        settings = Settings.get()
        settings["theme"] = theme

        if theme == "dark":
            palette = QPalette()
            palette.setColor(QPalette.Window, QColor(30, 30, 30))
            palette.setColor(QPalette.WindowText, QColor(224, 224, 224))
            palette.setColor(QPalette.Base, QColor(22, 22, 22))
            palette.setColor(QPalette.AlternateBase, QColor(35, 35, 35))
            palette.setColor(QPalette.ToolTipBase, QColor(40, 40, 40))
            palette.setColor(QPalette.ToolTipText, QColor(224, 224, 224))
            palette.setColor(QPalette.Text, QColor(224, 224, 224))
            palette.setColor(QPalette.Button, QColor(40, 40, 40))
            palette.setColor(QPalette.ButtonText, QColor(224, 224, 224))
            palette.setColor(QPalette.BrightText, QColor(255, 50, 50))
            palette.setColor(QPalette.Link, QColor(90, 170, 255))
            palette.setColor(QPalette.Highlight, QColor(50, 100, 180))
            palette.setColor(QPalette.HighlightedText, QColor(240, 240, 240))
            app.setPalette(palette)
        elif theme == "light":
            app.setPalette(app.style().standardPalette())
        else:
            # System default
            app.setPalette(app.style().standardPalette())

        settings.save()
        # Refresh list to update row colors
        if self._file_data:
            self._populate_list()
        self._show_toast(self.tr("Theme changed"))

    def _on_auto_propagate(self):
        if not self._file_data:
            self._show_toast(self.tr("No file loaded"))
            return
        self._save_current_entry()
        entries = self._get_entries()
        source_map: dict[str, list[int]] = {}
        for i, (msgid, msgstr, _) in enumerate(entries):
            if msgid:
                source_map.setdefault(msgid, []).append(i)
        count = 0
        for source, indices in source_map.items():
            if len(indices) < 2:
                continue
            translated = None
            for idx in indices:
                _, msgstr, _ = entries[idx]
                if msgstr:
                    translated = msgstr
                    break
            if not translated:
                continue
            for idx in indices:
                _, msgstr, _ = entries[idx]
                if not msgstr:
                    self._set_entry_translation(idx, translated)
                    count += 1
        if count:
            self._modified = True
            self._populate_list()
            self._update_stats()
        self._show_toast(self.tr("Auto-propagated %d entries") % count)

    # ══════════════════════════════════════════════════════════════
    #  FILE OPERATIONS
    # ══════════════════════════════════════════════════════════════

    def _on_open(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Translation File", "", _FILE_FILTER)
        if path:
            self._load_file(path)

    def _load_file(self, path: str):
        p = Path(path)
        if not p.exists():
            self._show_toast(self.tr("File not found: %s") % str(p))
            return

        if self._file_data and self._tab_widget.count() > 0:
            self._save_current_tab()
            self._create_tab_for_file(path)
        elif self._tab_widget.count() == 0:
            index = self._tab_widget.addTab(QWidget(), p.name)
            self._tabs[index] = TabData()
            self._tabs[index].file_path = path

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
            elif p.suffix in (".xliff", ".xlf"):
                self._file_data = parse_xliff(p)
                self._file_type = "xliff"
            elif p.suffix == ".xml":
                self._file_data = parse_android(p)
                self._file_type = "android"
            elif p.suffix == ".arb":
                self._file_data = parse_arb(p)
                self._file_type = "arb"
            elif p.suffix == ".php":
                self._file_data = parse_php(p)
                self._file_type = "php"
            elif p.suffix in (".yml", ".yaml"):
                self._file_data = parse_yaml(p)
                self._file_type = "yaml"
            else:
                self._show_toast(self.tr("Unsupported file type: %s") % p.suffix)
                return
        except Exception as e:
            self._show_toast(self.tr("Error loading file: %s") % str(e))
            return

        self.setWindowTitle(f"LinguaEdit — {p.name}")

        idx = self._tab_widget.currentIndex()
        if idx >= 0:
            self._tab_widget.setTabText(idx, p.name)

        self._sb_filename.setText(p.name)
        self._sb_format.setText(self._file_type.upper())

        _add_recent(str(p))
        self._rebuild_recent_menu()
        self._populate_list()
        self._update_stats()
        self._modified = False
        self._undo_stacks.clear()
        self._redo_stacks.clear()
        self._lint_cache.clear()
        self._selected_indices.clear()
        self._setup_file_monitor(p)

        # Select first entry
        if self._tree.topLevelItemCount() > 0:
            self._tree.setCurrentItem(self._tree.topLevelItem(0))

    def _rebuild_recent_menu(self):
        self._recent_menu.clear()
        for rp in _load_recent()[:10]:
            name = Path(rp).name
            act = self._recent_menu.addAction(name)
            act.triggered.connect(lambda checked, p=rp: self._load_file(p))

    # ── File monitoring ───────────────────────────────────────────

    def _setup_file_monitor(self, path: Path):
        if self._file_watcher:
            files = self._file_watcher.files()
            if files:
                self._file_watcher.removePaths(files)
        else:
            self._file_watcher = QFileSystemWatcher()
            self._file_watcher.fileChanged.connect(self._on_file_changed)
        self._file_watcher.addPath(str(path))

    def _on_file_changed(self, path):
        self._reload_timer.start()

    def _reload_file(self):
        if not self._file_data:
            return
        path = str(self._file_data.path)
        saved_idx = self._current_index
        self._load_file(path)
        if saved_idx >= 0:
            for i in range(self._tree.topLevelItemCount()):
                item = self._tree.topLevelItem(i)
                if item.data(0, Qt.UserRole) == saved_idx:
                    self._tree.setCurrentItem(item)
                    break
        self._show_toast(self.tr("File reloaded (changed externally)"))

    # ── Save ──────────────────────────────────────────────────────

    def _save_current_entry(self):
        if self._current_index < 0 or not self._file_data:
            return
        self._save_plural_entries(self._current_index)
        text = self._trans_view.toPlainText()

        if self._file_type == "po":
            entry = self._file_data.entries[self._current_index]
            if entry.msgstr != text:
                entry.msgstr = text
                self._modified = True
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
        elif self._file_type == "xliff":
            entry = self._file_data.entries[self._current_index]
            if entry.target != text:
                entry.target = text
                self._modified = True
        elif self._file_type in ("android", "arb", "php", "yaml"):
            entry = self._file_data.entries[self._current_index]
            if entry.value != text:
                entry.value = text
                self._modified = True

    def _on_fuzzy_toggled(self, checked):
        if self._current_index < 0 or not self._file_data:
            return
        if self._file_type == "po":
            entry = self._file_data.entries[self._current_index]
            if checked:
                if "fuzzy" not in entry.flags:
                    entry.flags.append("fuzzy")
                entry.fuzzy = True
            else:
                entry.flags = [f for f in entry.flags if f != "fuzzy"]
                entry.fuzzy = False
            self._modified = True

    def _on_save(self):
        self._save_current_entry()
        if not self._file_data:
            return

        if self._file_watcher:
            files = self._file_watcher.files()
            if files:
                self._file_watcher.removePaths(files)

        if self._file_type == "po":
            s = self._app_settings
            if s.last_translator:
                self._file_data.metadata["Last-Translator"] = s.last_translator
            if s.language_team:
                self._file_data.metadata["Language-Team"] = s.language_team

        try:
            if self._file_type == "po":
                save_po(self._file_data)
            elif self._file_type == "ts":
                save_ts(self._file_data)
            elif self._file_type == "json":
                save_json(self._file_data)
            elif self._file_type == "xliff":
                save_xliff(self._file_data)
            elif self._file_type == "android":
                save_android(self._file_data)
            elif self._file_type == "arb":
                save_arb(self._file_data)
            elif self._file_type == "php":
                save_php(self._file_data)
            elif self._file_type == "yaml":
                save_yaml(self._file_data)
            self._modified = False
            self._show_toast(self.tr("Saved!"))
            self._update_stats()
            self._populate_list()

            # Auto-compile if enabled
            if self._app_settings.get_value("auto_compile_on_save", False):
                self._on_compile()
        except Exception as e:
            self._show_toast(self.tr("Save error: %s") % str(e))
        finally:
            if self._file_data:
                self._setup_file_monitor(self._file_data.path)

    # ── Stats ─────────────────────────────────────────────────────

    def _update_stats(self):
        if not self._file_data:
            self._stats_label.setText(self.tr("No file loaded"))
            self._progress_bar.setValue(0)
            return
        d = self._file_data
        fuzzy = getattr(d, 'fuzzy_count', 0)
        frac = d.translated_count / d.total_count if d.total_count else 1.0
        pct = int(frac * 100)

        self._stats_label.setText(
            self.tr("%d strings — %d translated, %d fuzzy, %d untranslated")
            % (d.total_count, d.translated_count, fuzzy, d.untranslated_count)
        )
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(pct)

        self._sb_total.setText(self.tr("%d strings") % d.total_count)
        self._sb_translated.setText(self.tr("Translated: %d") % d.translated_count)
        self._sb_fuzzy.setText(self.tr("Fuzzy: %d") % fuzzy)
        self._sb_untranslated.setText(self.tr("Untranslated: %d") % d.untranslated_count)

    # ── Cursor position ──────────────────────────────────────────

    def _on_cursor_position_changed(self):
        cursor = self._trans_view.textCursor()
        line = cursor.blockNumber() + 1
        col = cursor.columnNumber() + 1
        self._sb_cursor.setText(self.tr("Ln %d, Col %d") % (line, col))

    # ── Tab management ────────────────────────────────────────────

    def _on_tab_changed(self, index):
        if index >= 0 and index in self._tabs:
            self._restore_tab(self._tabs[index])

    def _on_tab_close(self, index):
        if index < 0:
            return
        if index in self._tabs:
            del self._tabs[index]
        self._tab_widget.removeTab(index)
        new_tabs = {}
        for i in range(self._tab_widget.count()):
            for k, v in self._tabs.items():
                if v.file_path and self._tab_widget.tabText(i) == Path(v.file_path).name:
                    new_tabs[i] = v
                    break
        self._tabs = new_tabs
        if self._tab_widget.count() == 0:
            self._file_data = None
            self._file_type = None
            self._current_index = -1
            self._tree.clear()
            self.setWindowTitle("LinguaEdit")

    def _save_current_tab(self):
        index = self._tab_widget.currentIndex()
        if index < 0 or index not in self._tabs:
            return
        td = self._tabs[index]
        td.file_data = self._file_data
        td.file_type = self._file_type
        td.current_index = self._current_index
        td.modified = self._modified
        td.undo_stacks = self._undo_stacks
        td.redo_stacks = self._redo_stacks
        td.lint_cache = self._lint_cache

    def _restore_tab(self, td: TabData):
        self._file_data = td.file_data
        self._file_type = td.file_type
        self._current_index = td.current_index
        self._modified = td.modified
        self._undo_stacks = td.undo_stacks
        self._redo_stacks = td.redo_stacks
        self._lint_cache = td.lint_cache
        if self._file_data:
            self._populate_list()
            self._update_stats()
            name = Path(str(self._file_data.path)).name
            self.setWindowTitle(f"LinguaEdit — {name}")

    def _create_tab_for_file(self, path: str):
        self._save_current_tab()
        index = self._tab_widget.addTab(QWidget(), Path(path).name)
        td = TabData()
        td.file_path = path
        self._tabs[index] = td
        self._tab_widget.setCurrentIndex(index)
        return td

    # ── Drag & drop ──────────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path and Path(path).suffix in _ALL_EXTENSIONS:
                self._load_file(path)
                return

    # ══════════════════════════════════════════════════════════════
    #  TOOLS & DIALOGS
    # ══════════════════════════════════════════════════════════════

    # ── Lint ──────────────────────────────────────────────────────

    def _on_lint(self):
        if not self._file_data:
            self._show_toast(self.tr("No file loaded"))
            return
        self._save_current_entry()
        entries = self._get_entries()
        lint_input = []
        for i, (msgid, msgstr, is_fuzzy) in enumerate(entries):
            flags = ["fuzzy"] if is_fuzzy else []
            lint_input.append({"index": i, "msgid": msgid, "msgstr": msgstr, "flags": flags})
        result = lint_entries(lint_input)

        self._lint_cache.clear()
        for issue in result.issues:
            self._lint_cache.setdefault(issue.entry_index, []).append(issue)

        self._populate_list()

        msg = (f"Quality score: {result.score}%\n"
               f"Errors: {result.error_count} | Warnings: {result.warning_count}\n\n")
        for issue in result.issues[:20]:
            src = issue.msgid[:40].replace("\n", " ")
            msg += f"[{issue.severity}] #{issue.entry_index}: {issue.message} — \"{src}\"\n"
        if len(result.issues) > 20:
            msg += f"\n… and {len(result.issues) - 20} more issues"
        self._show_dialog(self.tr("Validation Results"), msg)

    # ── Consistency check ─────────────────────────────────────────

    def _on_consistency_check(self):
        if not self._file_data:
            self._show_toast(self.tr("No file loaded"))
            return
        self._save_current_entry()
        entries = self._get_entries()
        source_map: dict[str, set[str]] = {}
        source_indices: dict[str, list[int]] = {}
        for i, (msgid, msgstr, _) in enumerate(entries):
            if msgid and msgstr:
                source_map.setdefault(msgid, set()).add(msgstr)
                source_indices.setdefault(msgid, []).append(i)
        inconsistencies = []
        for source, translations in source_map.items():
            if len(translations) > 1:
                indices = source_indices[source]
                inconsistencies.append(
                    f"Source: \"{source[:60]}\"\n"
                    f"  Entries: {', '.join(f'#{i}' for i in indices)}\n"
                    f"  Translations: {'; '.join(t[:40] for t in translations)}\n"
                )
        if inconsistencies:
            msg = f"Found {len(inconsistencies)} inconsistencies:\n\n" + "\n".join(inconsistencies[:20])
        else:
            msg = "No inconsistencies found! ✓"
        self._show_dialog(self.tr("Consistency Check"), msg)

    # ── Glossary ──────────────────────────────────────────────────

    def _on_glossary(self):
        terms = get_terms()
        terms_text = "\n".join(f"• {t.source} → {t.target}" for t in terms[:20]) or "No terms defined"
        result = QMessageBox.question(
            self, self.tr("Glossary / Terminology"),
            f"{terms_text}\n\nAdd a new term or check file?",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
        )
        if result == QMessageBox.Yes:
            src, ok1 = QInputDialog.getText(self, self.tr("Add Term"), self.tr("Source term:"))
            if ok1 and src:
                tgt, ok2 = QInputDialog.getText(self, self.tr("Add Term"), self.tr("Target term:"))
                if ok2 and tgt:
                    add_term(src, tgt)
                    self._show_toast(self.tr("Added: %s → %s") % (src, tgt))
        elif result == QMessageBox.No:
            self._run_glossary_check()

    def _run_glossary_check(self):
        if not self._file_data:
            return
        entries = self._get_entries()
        check_input = [{"index": i, "msgid": msgid, "msgstr": msgstr}
                       for i, (msgid, msgstr, _) in enumerate(entries)]
        violations = check_glossary(check_input)
        if violations:
            msg = f"Found {len(violations)} glossary violations:\n\n"
            for v in violations[:20]:
                msg += f"#{v.entry_index}: {v.message}\n"
        else:
            msg = "No glossary violations found! ✓"
        self._show_dialog(self.tr("Glossary Check"), msg)

    # ── QA profiles ───────────────────────────────────────────────

    def _on_qa_profile(self, profile_name: str):
        if not self._file_data:
            self._show_toast(self.tr("No file loaded"))
            return
        self._save_current_entry()
        entries = self._get_entries()
        check_input = [{"index": i, "msgstr": msgstr} for i, (_, msgstr, _) in enumerate(entries)]
        violations = check_profile(profile_name, check_input)
        if violations:
            msg = f"QA Profile '{profile_name}': {len(violations)} issues:\n\n"
            for v in violations[:20]:
                msg += f"[{v.severity}] #{v.entry_index}: {v.message}\n"
        else:
            msg = f"QA Profile '{profile_name}': No issues found! ✓"
        self._show_dialog(self.tr("QA Profile: %s") % profile_name, msg)

    # ── Export report ─────────────────────────────────────────────

    def _on_export_report(self):
        if not self._file_data:
            self._show_toast(self.tr("No file loaded"))
            return
        self._save_current_entry()
        entries = self._get_entries()
        lint_input = [{"index": i, "msgid": msgid, "msgstr": msgstr,
                       "flags": ["fuzzy"] if is_fuzzy else []}
                      for i, (msgid, msgstr, is_fuzzy) in enumerate(entries)]
        result = lint_entries(lint_input)
        gloss_input = [{"index": i, "msgid": msgid, "msgstr": msgstr}
                       for i, (msgid, msgstr, _) in enumerate(entries)]
        gloss_violations = check_glossary(gloss_input)
        d = self._file_data
        report_path = Path(str(d.path)).with_suffix(".report.html")
        generate_report(
            file_name=Path(str(d.path)).name,
            total=d.total_count, translated=d.translated_count,
            fuzzy=getattr(d, 'fuzzy_count', 0), untranslated=d.untranslated_count,
            quality_score=result.score,
            lint_issues=[{"severity": i.severity, "message": i.message,
                         "entry_index": i.entry_index, "msgid": i.msgid} for i in result.issues],
            glossary_violations=[{"entry_index": v.entry_index, "message": v.message} for v in gloss_violations],
            output_path=report_path,
        )
        self._show_toast(self.tr("Report saved to %s") % str(report_path))

    # ── Statistics ────────────────────────────────────────────────

    def _on_statistics(self):
        if not self._file_data:
            self._show_toast(self.tr("No file loaded"))
            return
        d = self._file_data
        total = d.total_count
        translated = d.translated_count
        fuzzy = getattr(d, 'fuzzy_count', 0)
        untranslated = d.untranslated_count
        pct = round(translated / total * 100, 1) if total else 100.0
        entries = self._get_entries()
        source_words = sum(len(msgid.split()) for msgid, _, _ in entries)
        trans_words = sum(len(msgstr.split()) for _, msgstr, _ in entries if msgstr)
        msg = (
            f"📊 Translation Statistics\n{'─' * 40}\n\n"
            f"Total strings:  {total}\n"
            f"Translated:     {translated} ({pct}%)\n"
            f"Fuzzy:          {fuzzy}\n"
            f"Untranslated:   {untranslated}\n\n"
            f"Source words:   {source_words}\n"
            f"Target words:   {trans_words}\n\n"
            f"Progress: {'█' * int(pct / 5)}{'░' * (20 - int(pct / 5))} {pct}%\n"
        )
        self._show_dialog(self.tr("Statistics"), msg)

    # ── Git integration ───────────────────────────────────────────

    def _on_git_status(self):
        if not self._file_data:
            self._show_toast(self.tr("No file loaded"))
            return
        status = get_status(self._file_data.path)
        if not status.is_repo:
            self._show_dialog(self.tr("Git Status"), self.tr("Not a git repository"))
            return
        msg = f"Branch: {status.branch}\n"
        if status.modified_files:
            msg += f"\nModified:\n" + "\n".join(f"  {f}" for f in status.modified_files)
        if status.staged_files:
            msg += f"\nStaged:\n" + "\n".join(f"  {f}" for f in status.staged_files)
        if status.untracked_files:
            msg += f"\nUntracked:\n" + "\n".join(f"  {f}" for f in status.untracked_files)
        if not status.has_changes:
            msg += "\nWorking tree clean ✓"
        self._show_dialog(self.tr("Git Status"), msg)

    def _on_git_diff(self):
        if not self._file_data:
            self._show_toast(self.tr("No file loaded"))
            return
        diff = get_diff(self._file_data.path)
        if not diff:
            diff = "No changes"
        self._show_dialog(self.tr("Git Diff"), diff[:3000])

    def _on_git_commit(self):
        if not self._file_data:
            self._show_toast(self.tr("No file loaded"))
            return
        msg, ok = QInputDialog.getText(
            self, self.tr("Git Commit"), self.tr("Commit message:"),
            text=f"Update translation: {Path(str(self._file_data.path)).name}"
        )
        if ok and msg:
            stage_file(self._file_data.path)
            success, output = commit(self._file_data.path, msg)
            if success:
                self._show_toast(self.tr("Committed!"))
            else:
                self._show_toast(self.tr("Commit failed: %s") % output)

    def _on_git_branch(self):
        if not self._file_data:
            self._show_toast(self.tr("No file loaded"))
            return
        branches = get_branches(self._file_data.path)
        status = get_status(self._file_data.path)
        msg = f"Current: {status.branch}\n\nBranches:\n" + "\n".join(f"  {b}" for b in branches)
        self._show_dialog(self.tr("Git Branches"), msg)

    # ── Pre-translate ─────────────────────────────────────────────

    def _on_translate_current(self):
        if self._current_index < 0 or not self._file_data:
            return
        entries = self._get_entries()
        msgid = entries[self._current_index][0]
        if not msgid:
            return
        engine_key = self._engine_dropdown.currentData()
        if engine_key:
            self._trans_engine = engine_key
        extra = self._build_engine_kwargs()
        try:
            result = translate(msgid, engine=self._trans_engine,
                               source=self._trans_source, target=self._trans_target, **extra)
            self._trans_view.setPlainText(result)
            self._info_label.setText(self.tr("Translated via %s") % self._trans_engine)
        except TranslationError as e:
            self._info_label.setText(str(e))

    def _build_engine_kwargs(self) -> dict:
        kw: dict = {}
        if self._trans_engine == "deepl" and hasattr(self, "_deepl_formality"):
            kw["formality"] = self._deepl_formality
        if self._trans_engine == "openai" and hasattr(self, "_openai_model"):
            kw["model"] = self._openai_model
        if self._trans_engine == "anthropic" and hasattr(self, "_anthropic_model"):
            kw["model"] = self._anthropic_model
        return kw

    def _on_pretranslate_all(self):
        if not self._file_data:
            self._show_toast(self.tr("No file loaded"))
            return
        self._show_pretranslate_dialog()

    def _show_pretranslate_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr("Pre-translate"))
        dialog.resize(420, 500)
        layout = QVBoxLayout(dialog)

        engine_group = QGroupBox(self.tr("Translation Engine"))
        engine_layout = QVBoxLayout(engine_group)
        engine_combo = QComboBox()
        engine_keys = list(ENGINES.keys())
        for k in engine_keys:
            v = ENGINES[k]
            suffix = "" if v["free"] else " (API key required)"
            engine_combo.addItem(f"{v['name']}{suffix}", k)
        try:
            engine_combo.setCurrentIndex(engine_keys.index(self._trans_engine))
        except ValueError:
            pass
        engine_layout.addWidget(engine_combo)
        layout.addWidget(engine_group)

        lang_group = QGroupBox(self.tr("Languages"))
        lang_form = QFormLayout(lang_group)
        source_edit = QLineEdit(self._trans_source)
        lang_form.addRow(self.tr("Source language:"), source_edit)
        target_edit = QLineEdit(self._trans_target)
        lang_form.addRow(self.tr("Target language:"), target_edit)
        layout.addWidget(lang_group)

        options_group = QGroupBox(self.tr("Options"))
        opt_form = QFormLayout(options_group)
        formality_combo = QComboBox()
        formality_combo.addItems(["default", "less", "more", "prefer_less", "prefer_more"])
        opt_form.addRow("DeepL formality:", formality_combo)
        openai_edit = QLineEdit(getattr(self, "_openai_model", "gpt-4o-mini"))
        opt_form.addRow("OpenAI model:", openai_edit)
        anthropic_edit = QLineEdit(getattr(self, "_anthropic_model", "claude-sonnet-4-20250514"))
        opt_form.addRow("Anthropic model:", anthropic_edit)
        layout.addWidget(options_group)

        keys_btn = QPushButton(self.tr("Manage API Keys…"))
        keys_btn.clicked.connect(self._show_api_keys_dialog)
        layout.addWidget(keys_btn)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.Accepted:
            engine_key = engine_combo.currentData()
            if engine_key:
                self._trans_engine = engine_key
            self._trans_source = source_edit.text().strip() or "en"
            self._trans_target = target_edit.text().strip() or "sv"
            formality_vals = ["default", "less", "more", "prefer_less", "prefer_more"]
            self._deepl_formality = formality_vals[formality_combo.currentIndex()]
            self._openai_model = openai_edit.text().strip() or "gpt-4o-mini"
            self._anthropic_model = anthropic_edit.text().strip() or "claude-sonnet-4-20250514"
            self._do_pretranslate_all()

    def _do_pretranslate_all(self):
        self._save_current_entry()
        count = 0
        entries = self._get_entries()
        extra = self._build_engine_kwargs()
        for i, (msgid, msgstr, _) in enumerate(entries):
            if msgstr or not msgid:
                continue
            try:
                result = translate(msgid, engine=self._trans_engine,
                                   source=self._trans_source, target=self._trans_target, **extra)
                if result:
                    self._set_entry_translation(i, result)
                    count += 1
            except TranslationError:
                continue
        self._modified = True
        self._populate_list()
        self._update_stats()
        self._show_toast(self.tr("Pre-translated %d entries via %s") % (count, self._trans_engine))

    def _show_api_keys_dialog(self):
        from linguaedit.services.keystore import store_secret, get_secret as ks_get, backend_name

        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr("API Keys"))
        dialog.resize(400, 450)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(f"Backend: {backend_name()}"))

        services = [
            ("openai", "OpenAI"), ("anthropic", "Anthropic"), ("deepl", "DeepL"),
            ("google_cloud", "Google Cloud Translation"), ("microsoft_translator", "Microsoft Translator"),
            ("aws", "Amazon Translate"), ("huggingface", "HuggingFace (NLLB)"),
            ("libretranslate", "LibreTranslate"),
        ]
        form = QFormLayout()
        rows = {}
        for svc, label in services:
            edit = QLineEdit()
            edit.setEchoMode(QLineEdit.Password)
            existing = ks_get(svc, "api_key")
            if existing:
                edit.setPlaceholderText("••••••••")
            rows[svc] = edit
            form.addRow(f"{label}:", edit)

        ms_region_edit = QLineEdit(ks_get("microsoft_translator", "region") or "global")
        form.addRow("MS Azure region:", ms_region_edit)
        aws_secret_edit = QLineEdit()
        aws_secret_edit.setEchoMode(QLineEdit.Password)
        if ks_get("aws", "secret_access_key"):
            aws_secret_edit.setPlaceholderText("••••••••")
        form.addRow("AWS Secret Key:", aws_secret_edit)
        aws_region_edit = QLineEdit(ks_get("aws", "region") or "us-east-1")
        form.addRow("AWS Region:", aws_region_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.Accepted:
            for svc, edit in rows.items():
                val = edit.text().strip()
                if val:
                    if svc == "aws":
                        store_secret("aws", "access_key_id", val)
                    else:
                        store_secret(svc, "api_key", val)
            if aws_secret_edit.text().strip():
                store_secret("aws", "secret_access_key", aws_secret_edit.text().strip())
            if aws_region_edit.text().strip():
                store_secret("aws", "region", aws_region_edit.text().strip())
            if ms_region_edit.text().strip():
                store_secret("microsoft_translator", "region", ms_region_edit.text().strip())
            self._show_toast(self.tr("API keys saved"))

    # ── Feed TM ───────────────────────────────────────────────────

    def _on_feed_tm(self):
        if not self._file_data:
            self._show_toast(self.tr("No file loaded"))
            return
        entries = self._get_entries()
        pairs = [(msgid, msgstr) for msgid, msgstr, _ in entries if msgid and msgstr]
        count = feed_file_to_tm(pairs)
        self._show_toast(self.tr("Added %d entries to Translation Memory") % count)

    # ── Spellcheck ────────────────────────────────────────────────

    def _run_spellcheck(self):
        text = self._trans_view.toPlainText()
        if not text:
            self._info_label.setText(self.tr("No text to check"))
            return
        issues = check_text(text, language=self._spell_lang)
        if not issues:
            self._info_label.setText(self.tr("✓ No spelling issues found"))
        else:
            msg = "\n".join(
                f"'{i.word}' → {', '.join(i.suggestions[:3]) or '(no suggestions)'}"
                for i in issues[:10]
            )
            self._info_label.setText(self.tr("Spelling issues:\n%s") % msg)

    # ── Metadata ──────────────────────────────────────────────────

    def _on_show_metadata(self):
        if not self._file_data:
            self._show_toast(self.tr("No file loaded"))
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr("File Header / Metadata"))
        dialog.setMinimumSize(600, 450)
        layout = QVBoxLayout(dialog)

        # Description
        desc = QLabel(self.tr("Edit file header metadata. Changes are applied when you click Save."))
        desc.setWordWrap(True)
        layout.addWidget(desc)

        if self._file_type == "po":
            # Editable key-value table for PO metadata
            meta = self._file_data.metadata
            table = QTableWidget(len(meta), 2)
            table.setHorizontalHeaderLabels([self.tr("Key"), self.tr("Value")])
            table.horizontalHeader().setStretchLastSection(True)
            table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
            table.verticalHeader().setVisible(False)

            for row, (key, value) in enumerate(meta.items()):
                key_item = QTableWidgetItem(key)
                val_item = QTableWidgetItem(value)
                table.setItem(row, 0, key_item)
                table.setItem(row, 1, val_item)

            layout.addWidget(table)

            # Add/Remove buttons
            btn_row = QHBoxLayout()
            add_btn = QPushButton(self.tr("Add Field"))
            remove_btn = QPushButton(self.tr("Remove Selected"))

            def add_field():
                row = table.rowCount()
                table.insertRow(row)
                table.setItem(row, 0, QTableWidgetItem(""))
                table.setItem(row, 1, QTableWidgetItem(""))

            def remove_field():
                row = table.currentRow()
                if row >= 0:
                    table.removeRow(row)

            add_btn.clicked.connect(add_field)
            remove_btn.clicked.connect(remove_field)
            btn_row.addWidget(add_btn)
            btn_row.addWidget(remove_btn)
            btn_row.addStretch()
            layout.addLayout(btn_row)

        elif self._file_type == "ts":
            form = QFormLayout()
            lang_edit = QLineEdit(getattr(self._file_data, 'language', ''))
            src_lang_edit = QLineEdit(getattr(self._file_data, 'source_language', ''))
            form.addRow(self.tr("Language:"), lang_edit)
            form.addRow(self.tr("Source language:"), src_lang_edit)
            layout.addLayout(form)

        elif self._file_type == "xliff":
            form = QFormLayout()
            ver_edit = QLineEdit(getattr(self._file_data, 'version', ''))
            src_edit = QLineEdit(getattr(self._file_data, 'source_language', ''))
            tgt_edit = QLineEdit(getattr(self._file_data, 'target_language', ''))
            form.addRow(self.tr("Version:"), ver_edit)
            form.addRow(self.tr("Source language:"), src_edit)
            form.addRow(self.tr("Target language:"), tgt_edit)
            layout.addLayout(form)

        elif self._file_type == "arb":
            form = QFormLayout()
            locale_edit = QLineEdit(getattr(self._file_data, 'locale', ''))
            form.addRow(self.tr("Locale:"), locale_edit)
            layout.addLayout(form)

        elif self._file_type == "yaml":
            form = QFormLayout()
            root_edit = QLineEdit(getattr(self._file_data, 'root_key', ''))
            form.addRow(self.tr("Root key:"), root_edit)
            layout.addLayout(form)

        else:
            info = QLabel(f"File: {self._file_data.path.name}\nEntries: {self._file_data.total_count}")
            layout.addWidget(info)

        # Dialog buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)

        def on_save():
            if self._file_type == "po":
                new_meta = {}
                for row in range(table.rowCount()):
                    key = table.item(row, 0)
                    val = table.item(row, 1)
                    if key and key.text().strip():
                        new_meta[key.text().strip()] = val.text() if val else ""
                self._file_data.metadata = new_meta
                self._modified = True
            elif self._file_type == "ts":
                self._file_data.language = lang_edit.text()
                self._file_data.source_language = src_lang_edit.text()
                self._modified = True
            elif self._file_type == "xliff":
                self._file_data.version = ver_edit.text()
                self._file_data.source_language = src_edit.text()
                self._file_data.target_language = tgt_edit.text()
                self._modified = True
            elif self._file_type == "arb":
                self._file_data.locale = locale_edit.text()
                self._modified = True
            elif self._file_type == "yaml":
                self._file_data.root_key = root_edit.text()
                self._modified = True
            self._show_toast(self.tr("Metadata updated"))
            dialog.accept()

        buttons.accepted.connect(on_save)
        buttons.rejected.connect(dialog.reject)
        dialog.exec()

    # ── Compare language / Split view ─────────────────────────────

    def _on_compare_lang(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Reference File", "", _FILE_FILTER)
        if path:
            self._load_split_file(path)

    def _load_split_file(self, path: str):
        p = Path(path)
        try:
            if p.suffix in (".po", ".pot"):
                self._split_file_data = parse_po(p)
                self._split_file_type = "po"
            elif p.suffix == ".ts":
                self._split_file_data = parse_ts(p)
                self._split_file_type = "ts"
            elif p.suffix == ".json":
                self._split_file_data = parse_json(p)
                self._split_file_type = "json"
            elif p.suffix in (".xliff", ".xlf"):
                self._split_file_data = parse_xliff(p)
                self._split_file_type = "xliff"
            elif p.suffix == ".xml":
                self._split_file_data = parse_android(p)
                self._split_file_type = "android"
            elif p.suffix == ".arb":
                self._split_file_data = parse_arb(p)
                self._split_file_type = "arb"
            elif p.suffix == ".php":
                self._split_file_data = parse_php(p)
                self._split_file_type = "php"
            elif p.suffix in (".yml", ".yaml"):
                self._split_file_data = parse_yaml(p)
                self._split_file_type = "yaml"
            else:
                return
        except Exception as e:
            self._show_toast(self.tr("Error loading reference: %s") % str(e))
            return
        self._side_panel.setCurrentIndex(2)  # Switch to Reference tab
        self._show_toast(self.tr("Loaded reference: %s") % p.name)
        if self._current_index >= 0:
            self._update_split_view(self._current_index)

    def _update_split_view(self, idx: int):
        if not self._split_file_data:
            return
        entries = self._get_entries()
        if idx >= len(entries):
            return
        msgid = entries[idx][0]
        ref_entries = self._get_split_entries()
        for ref_msgid, ref_msgstr, _ in ref_entries:
            if ref_msgid == msgid:
                self._split_source_label.setText(ref_msgid[:300])
                self._split_trans_label.setText(ref_msgstr[:300])
                return
        self._split_source_label.setText(msgid[:300])
        self._split_trans_label.setText(self.tr("<i>(no match in reference)</i>"))

    def _get_split_entries(self) -> list[tuple[str, str, bool]]:
        if not self._split_file_data:
            return []
        ft = self._split_file_type
        d = self._split_file_data
        if ft == "po":
            return [(e.msgid, e.msgstr, e.fuzzy) for e in d.entries]
        elif ft == "ts":
            return [(e.source, e.translation, e.is_fuzzy) for e in d.entries]
        elif ft == "json":
            return [(e.key, e.value, False) for e in d.entries]
        elif ft == "xliff":
            return [(e.source, e.target, e.is_fuzzy) for e in d.entries]
        elif ft in ("android", "arb", "php", "yaml"):
            return [(e.key, e.value, False) for e in d.entries]
        return []

    # ── GitHub PR ─────────────────────────────────────────────────

    def _on_github_pr(self):
        self._show_dialog(
            self.tr("GitHub PR"),
            "To push a PR, configure your GitHub token in Preferences → GitHub.\n\n"
            "This feature will:\n1. Ask for auth token\n2. Fetch POT from the repo\n"
            "3. Create a branch\n4. Push your translation\n5. Open a PR\n\n"
            "(Full implementation in services/github.py)"
        )

    # ── Updates ───────────────────────────────────────────────────

    def _on_check_updates(self):
        from linguaedit.services.updater import check_for_updates
        update = check_for_updates()
        if update:
            self._show_dialog(self.tr("Update Available"),
                              f"Version {update['version']} is available!\n\n{update['url']}")
        else:
            self._show_dialog(self.tr("Up to date"), f"You are running the latest version ({__version__}).")

    # ── Donate ────────────────────────────────────────────────────

    def _on_donate(self):
        msg = QMessageBox(self)
        msg.setWindowTitle(self.tr("Donate ♥"))
        msg.setTextFormat(Qt.RichText)
        msg.setText(self.tr(
            "<p>LinguaEdit is free software.</p>"
            "<p>If you find it useful, consider supporting development:</p>"
            "<p>❤️ <b>GitHub Sponsors:</b> <a href='https://github.com/sponsors/yeager'>"
            "github.com/sponsors/yeager</a></p>"
            "<p>🇸🇪 <b>Swish:</b> +46702526206 — "
            "<a href='swish://payment?payee=0702526206&message=LinguaEdit'>"
            "Öppna Swish</a></p>"
        ))
        msg.exec()

    # ── About ─────────────────────────────────────────────────────

    def _on_about(self):
        icon_html = ""
        if self._app_icon_path:
            icon_html = f"<p><img src='{self._app_icon_path}' width='64' height='64'></p>"
        QMessageBox.about(
            self,
            self.tr("About LinguaEdit"),
            f"{icon_html}"
            f"<h2>LinguaEdit</h2>"
            f"<p>Version {__version__}</p>"
            f"<p>A translation file editor for PO, TS, JSON, XLIFF, "
            f"Android, ARB, PHP, and YAML files.</p>"
            f"<p>Developer: Daniel Nylander &lt;po@danielnylander.se&gt;</p>"
            f"<p>License: GPL-3.0-or-later</p>"
            f"<p>Website: <a href='https://github.com/yeager/linguaedit'>"
            f"github.com/yeager/linguaedit</a></p>"
            f"<p>© 2025 Daniel Nylander</p>"
        )

    # ── Platform integration ──────────────────────────────────────

    def _on_platform_settings(self):
        dialog = PlatformSettingsDialog(self)
        dialog.exec()

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
        dialog.exec()

    # ── Compile translation ──────────────────────────────────────

    def _on_compile(self):
        """Compile the current translation file (.po → .mo, .ts → .qm)."""
        if not self._file_data:
            self._show_toast(self.tr("No file loaded"))
            return

        path = Path(str(self._file_data.path))

        if self._file_type == "po":
            mo_path = path.with_suffix(".mo")
            try:
                import polib
                po = polib.pofile(str(path))
                po.save_as_mofile(str(mo_path))
                self._show_toast(self.tr("Compiled: %s") % str(mo_path))
            except ImportError:
                # Fallback to msgfmt
                if shutil.which("msgfmt"):
                    result = subprocess.run(
                        ["msgfmt", "-o", str(mo_path), str(path)],
                        capture_output=True, text=True
                    )
                    if result.returncode == 0:
                        self._show_toast(self.tr("Compiled: %s") % str(mo_path))
                    else:
                        self._show_toast(self.tr("msgfmt error: %s") % result.stderr.strip())
                else:
                    self._show_toast(self.tr("Cannot compile: install 'polib' or 'gettext' (msgfmt)"))
            except Exception as e:
                self._show_toast(self.tr("Compile error: %s") % str(e))

        elif self._file_type == "ts":
            qm_path = path.with_suffix(".qm")
            lrelease = shutil.which("pyside6-lrelease") or shutil.which("lrelease")
            if not lrelease:
                self._show_toast(self.tr("Cannot compile: pyside6-lrelease or lrelease not found"))
                return
            try:
                result = subprocess.run(
                    [lrelease, str(path), "-qm", str(qm_path)],
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    self._show_toast(self.tr("Compiled: %s") % str(qm_path))
                else:
                    self._show_toast(self.tr("lrelease error: %s") % result.stderr.strip())
            except Exception as e:
                self._show_toast(self.tr("Compile error: %s") % str(e))
        else:
            self._show_toast(self.tr("Compile not supported for %s files") % self._file_type)

    # ── Helpers ───────────────────────────────────────────────────

    def _show_toast(self, message: str):
        self.statusBar().showMessage(message, 3000)

    def _show_dialog(self, title: str, body: str):
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(body)
        msg.exec()
