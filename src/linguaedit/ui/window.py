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

import sys
import json
import re
import shutil
import subprocess
from difflib import SequenceMatcher, unified_diff, ndiff
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
    QMessageBox, QInputDialog, QApplication, QToolButton, QProgressDialog,
    QAbstractItemView, QSpinBox, QDockWidget, QStyledItemDelegate,
)
from PySide6.QtCore import Qt, QTimer, QFileSystemWatcher, Signal, Slot, QPropertyAnimation, QEasingCurve, QSettings, QThread
from PySide6.QtGui import (
    QAction, QKeySequence, QFont, QColor, QIcon, QBrush,
    QDragEnterEvent, QDropEvent, QPalette, QShortcut, QDesktopServices,
)
from PySide6.QtWidgets import QGraphicsOpacityEffect
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
from linguaedit.parsers.godot import parse_godot, save_godot, GodotFileData
from linguaedit.parsers.chrome_i18n import parse_chrome_i18n, save_chrome_i18n, ChromeI18nFileData
from linguaedit.parsers.java_properties import parse_java_properties, save_java_properties, JavaPropertiesFileData
from linguaedit.parsers.subtitles import parse_subtitles, save_subtitles, SubtitleFileData
from linguaedit.parsers.apple_strings import parse_apple_strings, save_apple_strings, AppleStringsData
from linguaedit.parsers.unity_asset import parse_unity_asset, save_unity_asset, UnityAssetData
from linguaedit.parsers.resx import parse_resx, save_resx, RESXData
from linguaedit.parsers.sdlxliff_parser import parse_sdlxliff, save_sdlxliff, SDLXLIFFFileData
from linguaedit.parsers.mqxliff_parser import parse_mqxliff, save_mqxliff, MQXLIFFFileData
from linguaedit.services.linter import lint_entries, LintResult, LintIssue
from linguaedit.services.spellcheck import check_text, available_languages
from linguaedit.services.translator import translate, ENGINES, TranslationError
from linguaedit.services.tm import lookup_tm, add_to_tm, feed_file_to_tm
from linguaedit.services.glossary import get_terms, add_term, remove_term, check_glossary
from linguaedit.services.qa_profiles import get_profiles, check_profile
from linguaedit.services.report import generate_report
from linguaedit.services.git_integration import (
    get_status, get_diff, stage_file, commit, get_branches, switch_branch, create_branch,
    get_file_at_commit, get_commits_for_file,
)
from linguaedit.ui.platform_dialog import PlatformSettingsDialog
from linguaedit.ui.sync_dialog import SyncDialog
from linguaedit.ui.search_replace_dialog import SearchReplaceDialog
from linguaedit.ui.batch_edit_dialog import BatchEditDialog
from linguaedit.ui.glossary_dialog import GlossaryDialog
from linguaedit.ui.statistics_dialog import StatisticsDialog
from linguaedit.ui.header_dialog import HeaderDialog
from linguaedit.ui.diff_dialog import DiffDialog, GitDiffDialog
from linguaedit.ui.dashboard_dialog import DashboardDialog
from linguaedit.ui.batch_translate_dialog import BatchTranslateDialog
from linguaedit.ui.project_dock import ProjectDockWidget
from linguaedit.ui.ai_review_dialog import AIReviewDialog
from linguaedit.ui.translation_editor import TranslationEditor
from linguaedit.ui.plural_forms_editor import PluralFormsEditor
from linguaedit.ui.minimap import MinimapWidget
from linguaedit.ui.quick_actions import QuickActionsMenu
from linguaedit.ui.regex_tester_dialog import RegexTesterDialog
from linguaedit.ui.layout_simulator_dialog import LayoutSimulatorDialog
from linguaedit.ui.locale_map_dialog import LocaleMapDialog
from linguaedit.ui.ocr_dialog import OCRDialog
from linguaedit.ui.context_panel import ContextPanel
from linguaedit.services.settings import Settings
from linguaedit.services.context_lookup import get_context_service
from linguaedit.services.terminology import get_terminology_service
from linguaedit.services.confidence import get_confidence_calculator
from linguaedit.services.source_context import get_source_context_service
from linguaedit.services.plugins import get_plugin_manager
from linguaedit.services.history import get_history_manager
from linguaedit.services.tmx import TMXService
from linguaedit.services.segmenter import EntrySegmenter, TextSegmenter
from linguaedit.services.achievements import get_achievement_manager
from linguaedit.services.macros import get_macro_manager, MacroActionType
from linguaedit.ui.plugin_dialog import PluginDialog
from linguaedit.ui.history_dialog import HistoryDialog, FileHistoryDialog
from linguaedit.ui.video_subtitle_dialog import VideoSubtitleDialog
from linguaedit.ui.video_preview import VideoPreviewWidget, VideoDockWidget
from linguaedit.ui.zen_mode import ZenModeWidget
from linguaedit.ui.entry_delegate import EntryItemDelegate
from linguaedit.ui.collapsible_panel import CollapsibleSidePanel
from linguaedit.ui.toolbar_customizer import ToolbarCustomizeDialog
from linguaedit.ui.unicode_dialog import UnicodeDialog
from linguaedit.ui.achievements_dialog import AchievementsDialog
from linguaedit.ui.macro_dialog import MacroDialog
from linguaedit.ui.concordance_dialog import ConcordanceDialog
from linguaedit.ui.segment_ops import SplitDialog, MergePreviewDialog
from linguaedit.ui.progress_ring import ProgressRing

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
    ".sdlxliff", ".mqxliff",
}

_FILE_FILTER = "Translation files (*.po *.pot *.ts *.json *.xliff *.xlf *.xml *.arb *.php *.yml *.yaml *.csv *.tres *.properties *.srt *.vtt *.sdlxliff *.mqxliff);;CAT files (*.sdlxliff *.mqxliff);;Video files (*.mkv *.mp4 *.avi *.mov *.webm *.flv *.wmv *.ogv)"


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


# ── Subtitle extraction worker ───────────────────────────────────────

class _SubtitleExtractWorker(QThread):
    """Run FFmpeg subtitle extraction in a background thread."""
    progress = Signal(int)       # 0-100
    finished = Signal()
    error = Signal(str)

    def __init__(self, video_path, track, output_path, duration, parent=None):
        super().__init__(parent)
        self._video_path = video_path
        self._track = track
        self._output_path = output_path
        self._duration = duration
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        from linguaedit.services.ffmpeg import extract_subtitle
        try:
            def on_progress(pct):
                if not self._cancelled:
                    self.progress.emit(int(pct * 100))
            extract_subtitle(
                self._video_path, self._track, self._output_path, ".srt",
                progress_callback=on_progress, duration=self._duration,
            )
            if not self._cancelled:
                self.progress.emit(100)
                self.finished.emit()
        except Exception as e:
            if not self._cancelled:
                self.error.emit(str(e))


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


# ── Validation Dialog ─────────────────────────────────────────────────

class ValidationDialog(QDialog):
    """Rich validation results dialog with filtering and navigation."""

    def __init__(self, parent, result, lint_cache):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Validation Results"))
        self.setMinimumSize(900, 550)
        self._parent_window = parent

        layout = QVBoxLayout(self)

        # Score header
        self._score_label = QLabel(self.tr("Quality score: %s%%") % result.score)
        self._score_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(self._score_label)

        self._stats_label = QLabel(self.tr("Errors: %d | Warnings: %d") % (result.error_count, result.warning_count))
        layout.addWidget(self._stats_label)

        # Filter checkboxes
        filter_row = QHBoxLayout()
        self._show_errors = QCheckBox(self.tr("Errors"))
        self._show_errors.setChecked(True)
        self._show_errors.toggled.connect(self._apply_filter)
        self._show_warnings = QCheckBox(self.tr("Warnings"))
        self._show_warnings.setChecked(True)
        self._show_warnings.toggled.connect(self._apply_filter)
        self._show_info = QCheckBox(self.tr("Info"))
        self._show_info.setChecked(True)
        self._show_info.toggled.connect(self._apply_filter)
        filter_row.addWidget(self._show_errors)
        filter_row.addWidget(self._show_warnings)
        filter_row.addWidget(self._show_info)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        # Issue list
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels([self.tr("#"), self.tr("Severity"), self.tr("Message"), self.tr("Source text")])
        self._tree.setRootIsDecorated(False)
        self._tree.setSortingEnabled(True)
        self._tree.sortByColumn(0, Qt.AscendingOrder)
        self._tree.itemDoubleClicked.connect(self._on_item_clicked)
        self._issues = result.issues
        self._populate()
        layout.addWidget(self._tree, 1)

        # Buttons
        btn_row = QHBoxLayout()
        update_btn = QPushButton(self.tr("Re-validate"))
        update_btn.clicked.connect(self._on_revalidate)
        btn_row.addWidget(update_btn)
        btn_row.addStretch()
        close_btn = QPushButton(self.tr("Close"))
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _populate(self):
        # Remember current selection
        current = self._tree.currentItem()
        selected_idx = current.data(0, Qt.UserRole) if current else None

        self._tree.clear()
        restore_item = None
        for issue in self._issues:
            if issue.severity == "error" and not self._show_errors.isChecked():
                continue
            if issue.severity == "warning" and not self._show_warnings.isChecked():
                continue
            if issue.severity == "info" and not self._show_info.isChecked():
                continue
            src = issue.msgid[:80].replace("\n", " ")
            item = _SortableItem([str(issue.entry_index + 1), issue.severity, issue.message, src])
            item.setData(0, Qt.UserRole, issue.entry_index)
            self._tree.addTopLevelItem(item)
            if issue.entry_index == selected_idx:
                restore_item = item

        self._tree.resizeColumnToContents(0)
        self._tree.resizeColumnToContents(1)
        header = self._tree.header()
        header.setStretchLastSection(True)
        header.resizeSection(2, 250)

        if restore_item:
            self._tree.setCurrentItem(restore_item)
            self._tree.scrollToItem(restore_item)

    def _apply_filter(self):
        self._populate()

    def _on_item_clicked(self, item, column):
        idx = item.data(0, Qt.UserRole)
        self._parent_window._navigate_to_entry(idx)

    def _on_revalidate(self):
        self._parent_window._save_current_entry()
        entries = self._parent_window._get_entries()
        lint_input = []
        for i, (msgid, msgstr, is_fuzzy) in enumerate(entries):
            flags = ["fuzzy"] if is_fuzzy else []
            lint_input.append({"index": i, "msgid": msgid, "msgstr": msgstr, "flags": flags})
        result = lint_entries(lint_input)
        self._parent_window._lint_cache.clear()
        for issue in result.issues:
            self._parent_window._lint_cache.setdefault(issue.entry_index, []).append(issue)
        self._parent_window._populate_list()
        self._issues = result.issues
        self._populate()
        self._score_label.setText(self.tr("Quality score: %s%%") % result.score)
        self._stats_label.setText(self.tr("Errors: %d | Warnings: %d") % (result.error_count, result.warning_count))


# ── Window ────────────────────────────────────────────────────────────

class LinguaEditWindow(QMainWindow):
    """Main editor window — POedit / Qt Linguist inspired layout."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("LinguaEdit"))
        self.resize(1200, 800)
        self.setAcceptDrops(True)

        # Window icon — check multiple locations (dev, installed, bundled)
        _icon_candidates = [
            Path(__file__).parent.parent.parent.parent / "resources" / "icon.png",  # dev
            Path(__file__).parent.parent / "resources" / "icon.png",  # installed package
            Path(getattr(sys, '_MEIPASS', '')) / "resources" / "icon.png",  # PyInstaller bundle
        ]
        self._app_icon_path = None
        for _icon_path in _icon_candidates:
            if _icon_path.exists():
                self.setWindowIcon(QIcon(str(_icon_path)))
                self._app_icon_path = str(_icon_path)
                break

        # Feature 13: Quick Actions
        self._quick_actions_menu = QuickActionsMenu(self)
        
        # Feature 15: Watch Mode
        self._file_watcher = None
        self._watch_mode_enabled = False

        # File state
        self._file_data = None
        self._file_type = None
        self._current_index = -1
        self._modified = False
        self._video_dock: Optional[VideoDockWidget] = None
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
        self._sort_mode = "status"
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
        
        # New dialogs and dock widgets
        self._search_replace_dialog: Optional[SearchReplaceDialog] = None
        self._project_dock: Optional[ProjectDockWidget] = None
        
        # Feature 1: AI Review
        self._ai_review_dialog: Optional[AIReviewDialog] = None
        
        # Feature 5: Plural Forms Editor
        self._plural_forms_editor: Optional[PluralFormsEditor] = None
        
        # Feature 6: Bokmärken
        self._bookmarks: set[int] = set()
        self._bookmarks_file = Path.home() / ".local" / "share" / "linguaedit" / "bookmarks.json"
        self._show_bookmarked_only = False
        
        # Feature 11: Pinned Entries
        self._pinned_entries: set[int] = set()
        self._pinned_file = Path.home() / ".local" / "share" / "linguaedit" / "pinned.json"
        self._show_pinned_first = True
        
        # Feature 7: Taggar/Filter  
        self._tags: dict[int, list[str]] = {}  # index -> [tags]
        self._tags_file = Path.home() / ".local" / "share" / "linguaedit" / "tags.json"
        self._active_tag_filter: Optional[str] = None
        
        # Feature 8: Review Mode
        self._review_mode = False
        self._review_status: dict[int, str] = {}  # index -> "needs_review", "approved", "rejected"
        self._review_comments: dict[int, str] = {}  # index -> comment
        
        # Feature 11: Screenshot Context Panel
        self._context_dock: Optional[QDockWidget] = None
        
        # Feature 12: Preview Panel  
        self._preview_dock: Optional[QDockWidget] = None
        
        # Feature 13: Focus Mode
        self._focus_mode = False
        
        # New services initialization
        self._plugin_manager = get_plugin_manager()
        self._history_manager = get_history_manager()
        self._achievement_manager = get_achievement_manager()
        self._macro_manager = get_macro_manager()
        
        # Character counter state
        self._char_count_limit = 280  # Default Twitter-like limit
        self._char_count_widget = None
        
        # TTS state
        self._tts_process = None
        
        # Fullscreen state
        self._is_fullscreen = False
        self._pre_fullscreen_state = None

        # UX improvements
        self._zen_mode_active = False
        self._zen_widget: ZenModeWidget | None = None
        self._editor_on_right = self._app_settings.get_value("editor_on_right", False)
        self._side_panel_expanded = True
        self._saved_flash_timer = QTimer()
        self._saved_flash_timer.setSingleShot(True)
        self._saved_flash_timer.setInterval(300)
        self._saved_flash_timer.timeout.connect(self._clear_saved_flash)

        self._horizontal_split = self._app_settings.get_value("horizontal_split", False)
        self._context_panel = None
        self._dirty = False

        self._build_ui()
        self._apply_settings()
        self._setup_shortcuts()

        # Apply saved split orientation
        if self._horizontal_split:
            self._apply_split_orientation()

        # Restore saved geometry and splitter positions
        settings = QSettings("LinguaEdit", "LinguaEdit")
        geo = settings.value("geometry")
        if geo:
            self.restoreGeometry(geo)
        ws = settings.value("windowState")
        if ws:
            self.restoreState(ws)
        outer = settings.value("outerSplitter")
        if outer:
            self._outer_splitter.restoreState(outer)
        vs = settings.value("vSplitter")
        if vs:
            self._v_splitter.restoreState(vs)

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
        self._outer_splitter = QSplitter(Qt.Horizontal)

        # ── Left: vertical splitter [entry table | editors] ──
        self._v_splitter = QSplitter(Qt.Vertical)

        # ── Top: entry table with filter bar ──
        self._table_container = QWidget()
        table_container = self._table_container
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(2)

        # Filter / search bar above table
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(4)

        self._filter_combo = QComboBox()
        self._filter_combo.addItems([self.tr("All strings"), self.tr("Untranslated"), self.tr("Fuzzy / Needs work"),
                                      self.tr("Translated"), self.tr("Reviewed"), self.tr("With warnings")])
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
            self.tr("Untranslated/errors first"), self.tr("By length"), self.tr("By reference"),
        ])
        self._sort_combo.setMinimumWidth(120)
        self._sort_combo.setCurrentIndex(self._SORT_MODES.index(self._sort_mode))
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
        self._tree.setHeaderLabels(["#", "⭐", self.tr("Source text"), self.tr("Translation"), self.tr("Tags"), ""])
        self._tree.setSortingEnabled(True)
        header = self._tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # #
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # ⭐ (bookmark)
        header.setSectionResizeMode(2, QHeaderView.Interactive)        # Source text (draggable)
        header.setSectionResizeMode(3, QHeaderView.Stretch)           # Translation (fills remaining)
        header.resizeSection(2, 320)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Tags
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Status/flags
        self._tree.currentItemChanged.connect(self._on_tree_item_changed)
        self._tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._show_tree_context_menu)
        self._tree.setMouseTracking(True)
        self._tree.viewport().installEventFilter(self)
        
        # Custom delegate for colored borders
        self._entry_delegate = EntryItemDelegate(self._tree, dark_mode=_is_dark_theme())
        self._tree.setItemDelegate(self._entry_delegate)
        
        # Tree + minimap layout
        tree_minimap_layout = QHBoxLayout()
        tree_minimap_layout.setContentsMargins(0, 0, 0, 0)
        tree_minimap_layout.setSpacing(2)
        
        tree_minimap_layout.addWidget(self._tree, 1)
        
        # Minimap
        self._minimap = MinimapWidget()
        self._minimap.jump_to_entry.connect(self._on_minimap_jump)
        self._minimap.setVisible(False)  # Dolt som standard
        tree_minimap_layout.addWidget(self._minimap)
        
        tree_minimap_widget = QWidget()
        tree_minimap_widget.setLayout(tree_minimap_layout)
        table_layout.addWidget(tree_minimap_widget, 1)

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
        self._editor_container = QWidget()
        editor_container = self._editor_container
        editor_layout = QVBoxLayout(editor_container)
        editor_layout.setContentsMargins(8, 4, 8, 0)
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

        # Subtitle timestamp editor (hidden by default)
        self._timestamp_frame = QGroupBox(self.tr("Time interval"))
        ts_layout = QHBoxLayout(self._timestamp_frame)
        ts_layout.setContentsMargins(8, 4, 8, 4)
        self._timestamp_edit = QLineEdit()
        self._timestamp_edit.setPlaceholderText("HH:MM:SS,mmm --> HH:MM:SS,mmm")
        self._timestamp_edit.setFont(QFont("Menlo"))
        self._timestamp_edit.editingFinished.connect(self._on_timestamp_edited)
        ts_layout.addWidget(QLabel(self.tr("Time:")))
        ts_layout.addWidget(self._timestamp_edit, 1)
        self._timestamp_frame.setVisible(False)
        editor_layout.addWidget(self._timestamp_frame)

        # Source label + view
        self._source_header = QLabel(self.tr("<b>Source text:</b>"))
        self._source_header.setContentsMargins(12, 2, 12, 0)
        self._source_view = QTextEdit()
        self._source_view.setReadOnly(True)
        self._source_view.setMinimumHeight(80)
        self._source_view.setMaximumHeight(300)
        self._source_view.setFrameShape(QFrame.StyledPanel)
        self._source_view.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._source_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._source_view.setStyleSheet("QTextEdit { background: palette(alternate-base); }")
        # Use a splitter so user can drag between source and translation
        self._editor_splitter = QSplitter(Qt.Vertical)
        # Wrap source in a widget with its header
        source_widget = QWidget()
        source_layout = QVBoxLayout(source_widget)
        source_layout.setContentsMargins(0, 0, 0, 0)
        source_layout.setSpacing(2)
        source_layout.addWidget(self._source_header)
        source_layout.addWidget(self._source_view)
        self._editor_splitter.addWidget(source_widget)

        # Translation label + view
        self._trans_header = QLabel(self.tr("<b>Translation:</b>"))
        self._trans_header.setContentsMargins(12, 2, 12, 0)
        self._trans_view = TranslationEditor()
        self._trans_view.setFrameShape(QFrame.StyledPanel)
        self._trans_view.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._trans_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._trans_view.textChanged.connect(self._on_trans_buffer_changed)
        self._trans_view.translation_changed.connect(self._on_trans_buffer_changed)
        self._trans_view._load_save_user_dict(save=False)  # Load user dictionary
        # Wrap translation in a widget with its header
        trans_widget = QWidget()
        trans_layout = QVBoxLayout(trans_widget)
        trans_layout.setContentsMargins(0, 0, 0, 0)
        trans_layout.setSpacing(2)
        trans_layout.addWidget(self._trans_header)
        trans_layout.addWidget(self._trans_view, 1)
        self._editor_splitter.addWidget(trans_widget)
        # Set initial splitter sizes (source smaller, translation bigger)
        self._editor_splitter.setSizes([150, 300])
        self._editor_splitter.setStretchFactor(0, 0)
        self._editor_splitter.setStretchFactor(1, 1)
        editor_layout.addWidget(self._editor_splitter, 1)

        # MT suggestion widget (below translation editor)
        self._mt_suggestion_widget = self._trans_view.get_mt_widget()
        editor_layout.addWidget(self._mt_suggestion_widget)
        
        # Translator comment field
        comment_label = QLabel(self.tr("<b>Translator comment:</b>"))
        comment_label.setContentsMargins(6, 0, 6, 0)
        editor_layout.addWidget(comment_label)
        
        self._comment_view = QTextEdit()
        self._comment_view.setMaximumHeight(60)
        self._comment_view.setFrameShape(QFrame.StyledPanel)
        self._comment_view.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._comment_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._comment_view.setPlaceholderText(self.tr("Add translator notes..."))
        self._comment_view.textChanged.connect(self._on_comment_changed)
        editor_layout.addWidget(self._comment_view)

        # Plural tabs (shown for plural entries only)
        self._plural_notebook = QTabWidget()
        self._plural_notebook.setVisible(False)
        editor_layout.addWidget(self._plural_notebook)

        # Inline lint warnings
        self._lint_inline_label = QLabel()
        self._lint_inline_label.setWordWrap(True)
        editor_layout.addWidget(self._lint_inline_label)

        # Source references (where the string is used in code)
        self._source_refs_label = QLabel()
        self._source_refs_label.setWordWrap(True)
        self._source_refs_label.setStyleSheet("color: #666; font-size: 11px; padding: 2px 6px;")
        self._source_refs_label.setVisible(False)
        editor_layout.addWidget(self._source_refs_label)

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

        # Quick Actions Toolbar (Feature 3)
        self._quick_toolbar = QFrame()
        self._quick_toolbar.setFrameShape(QFrame.StyledPanel)
        self._quick_toolbar.setStyleSheet("QFrame { background: palette(alternate-base); padding: 2px; }")
        qt_layout = QHBoxLayout(self._quick_toolbar)
        qt_layout.setContentsMargins(4, 2, 4, 2)
        qt_layout.setSpacing(4)

        self._qa_copy_src_btn = QPushButton(self.tr("📋 Copy Source"))
        self._qa_copy_src_btn.setToolTip(self.tr("Copy source text to translation"))
        self._qa_copy_src_btn.clicked.connect(self._copy_source_to_target)
        qt_layout.addWidget(self._qa_copy_src_btn)

        self._qa_apply_tm_btn = QPushButton(self.tr("💾 Apply TM #1"))
        self._qa_apply_tm_btn.setToolTip(self.tr("Apply best Translation Memory match"))
        self._qa_apply_tm_btn.setEnabled(False)
        self._qa_apply_tm_btn.clicked.connect(self._qa_apply_best_tm)
        qt_layout.addWidget(self._qa_apply_tm_btn)

        self._qa_apply_mt_btn = QPushButton(self.tr("🤖 Apply MT"))
        self._qa_apply_mt_btn.setToolTip(self.tr("Apply Machine Translation suggestion"))
        self._qa_apply_mt_btn.setEnabled(False)
        self._qa_apply_mt_btn.clicked.connect(self._qa_apply_mt)
        qt_layout.addWidget(self._qa_apply_mt_btn)

        self._qa_mark_reviewed_btn = QPushButton(self.tr("✅ Mark Reviewed"))
        self._qa_mark_reviewed_btn.setToolTip(self.tr("Mark current entry as reviewed"))
        self._qa_mark_reviewed_btn.clicked.connect(lambda: self._set_review_status("approved"))
        qt_layout.addWidget(self._qa_mark_reviewed_btn)

        self._qa_toggle_fuzzy_btn = QPushButton(self.tr("⚠️ Toggle Fuzzy"))
        self._qa_toggle_fuzzy_btn.setToolTip(self.tr("Toggle fuzzy/needs work flag"))
        self._qa_toggle_fuzzy_btn.clicked.connect(lambda: self._fuzzy_check.toggle())
        qt_layout.addWidget(self._qa_toggle_fuzzy_btn)

        qt_layout.addStretch()
        editor_layout.addWidget(self._quick_toolbar)

        # Info label (spellcheck results, etc.)
        self._info_label = QLabel()
        self._info_label.setWordWrap(True)
        editor_layout.addWidget(self._info_label)

        self._v_splitter.addWidget(editor_container)
        self._v_splitter.setSizes([400, 350])

        self._outer_splitter.addWidget(self._v_splitter)

        # ── Right: side panel (TM, string info, concordance) ──
        self._side_panel = QTabWidget()
        self._side_panel.setMinimumWidth(200)

        # String Information tab
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(4, 4, 4, 4)

        self._translator_note_label = QLabel()
        self._translator_note_label.setWordWrap(True)
        self._translator_note_row = self._make_info_row(self.tr("Notes"), self._translator_note_label)
        info_layout.addWidget(self._translator_note_row)

        self._extracted_comment_label = QLabel()
        self._extracted_comment_label.setWordWrap(True)
        self._extracted_comment_row = self._make_info_row(self.tr("Developer"), self._extracted_comment_label)
        info_layout.addWidget(self._extracted_comment_row)

        self._msgctxt_label = QLabel()
        self._msgctxt_label.setWordWrap(True)
        self._msgctxt_row = self._make_info_row(self.tr("Context"), self._msgctxt_label)
        info_layout.addWidget(self._msgctxt_row)

        self._references_label = QLabel()
        self._references_label.setWordWrap(True)
        self._references_row = self._make_info_row(self.tr("References"), self._references_label)
        info_layout.addWidget(self._references_row)

        self._flags_label = QLabel()
        self._flags_label.setWordWrap(True)
        self._flags_row = self._make_info_row(self.tr("Flags"), self._flags_label)
        info_layout.addWidget(self._flags_row)

        self._previous_label = QLabel()
        self._previous_label.setWordWrap(True)
        self._previous_row = self._make_info_row(self.tr("Previous"), self._previous_label)
        info_layout.addWidget(self._previous_row)

        self._comments_label = QLabel()
        self._comments_label.setWordWrap(True)
        self._comments_label.setTextFormat(Qt.RichText)
        self._comments_row = self._make_info_row(self.tr("Comments"), self._comments_label)
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
        
        # Feature 11: Context Panel (Screenshot)
        context_widget = QWidget()
        context_layout = QVBoxLayout(context_widget)
        context_layout.setContentsMargins(4, 4, 4, 4)
        
        self._context_image_label = QLabel(self.tr("No screenshot available"))
        self._context_image_label.setAlignment(Qt.AlignCenter)
        self._context_image_label.setStyleSheet("QLabel { border: 1px dashed gray; min-height: 150px; color: gray; }")
        context_layout.addWidget(self._context_image_label)
        
        context_layout.addStretch()
        self._side_panel.addTab(context_widget, self.tr("Context"))
        
        # Feature 12: Preview Panel
        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.setContentsMargins(4, 4, 4, 4)
        
        self._preview_label = QLabel(self.tr("Translation preview will appear here"))
        self._preview_label.setWordWrap(True)
        self._preview_label.setAlignment(Qt.AlignTop)
        self._preview_label.setStyleSheet("QLabel { border: 1px solid gray; padding: 8px; min-height: 100px; }")
        preview_layout.addWidget(self._preview_label)
        
        # Preview controls
        preview_controls = QHBoxLayout()
        preview_controls.addWidget(QLabel(self.tr("Max width:")))
        self._preview_width_spin = QSpinBox()
        self._preview_width_spin.setRange(100, 1000)
        self._preview_width_spin.setValue(300)
        self._preview_width_spin.setSuffix(" px")
        self._preview_width_spin.valueChanged.connect(self._update_preview)
        preview_controls.addWidget(self._preview_width_spin)
        preview_controls.addStretch()
        preview_layout.addLayout(preview_controls)
        
        preview_layout.addStretch()
        self._side_panel.addTab(preview_widget, self.tr("Preview"))

        # Wrap side panel in collapsible container
        self._collapsible_side = CollapsibleSidePanel(self._side_panel)
        self._outer_splitter.addWidget(self._collapsible_side)
        self._outer_splitter.setSizes([850, 300])

        # ── Left sidebar (quick actions — full panel) ──
        from PySide6.QtCore import QSize
        self._sidebar = QToolBar()
        self._sidebar.setObjectName("SidebarToolBar")
        self._sidebar.setOrientation(Qt.Vertical)
        self._sidebar.setMovable(False)
        self._sidebar.setIconSize(QSize(28, 28))
        self._sidebar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self._sidebar.setStyleSheet(
            "QToolBar { spacing: 8px; padding: 6px; background: palette(window); "
            "border-right: 1px solid palette(mid); }"
            "QToolButton { min-width: 72px; padding: 6px 4px; font-size: 11px; }"
        )

        style = self.style()
        # File operations
        self._sidebar.addAction(style.standardIcon(style.StandardPixmap.SP_DialogOpenButton), self.tr("Open"), self._on_open)
        self._sidebar.addAction(style.standardIcon(style.StandardPixmap.SP_DialogSaveButton), self.tr("Save"), self._on_save)
        self._sidebar.addSeparator()
        # Quality
        self._sidebar.addAction(style.standardIcon(style.StandardPixmap.SP_DialogApplyButton), self.tr("Validate"), self._on_lint)
        self._compile_action = self._sidebar.addAction(style.standardIcon(style.StandardPixmap.SP_MediaPlay), self.tr("Compile"), self._on_compile)
        self._compile_status = None  # None=neutral, True=ok, False=error
        self._sidebar.addSeparator()
        # Translation
        self._sidebar.addAction(style.standardIcon(style.StandardPixmap.SP_ComputerIcon), self.tr("Pre-translate"), self._on_pretranslate_all)
        self._sidebar.addAction(style.standardIcon(style.StandardPixmap.SP_FileDialogContentsView), self.tr("Search"), self._toggle_search_replace)
        self._sidebar.addSeparator()
        # Video subtitle extraction
        self._sidebar.addAction(style.standardIcon(style.StandardPixmap.SP_DriveDVDIcon), self.tr("Video"), self._on_open_video)
        self._sidebar.addSeparator()
        # Tools
        self._sidebar.addAction(style.standardIcon(style.StandardPixmap.SP_MessageBoxInformation), self.tr("Statistics"), self._show_statistics_dialog)
        self._sidebar.addAction(style.standardIcon(style.StandardPixmap.SP_BrowserReload), self.tr("AI Review"), self._show_ai_review)
        self._sidebar.addAction(style.standardIcon(style.StandardPixmap.SP_FileDialogDetailedView), self.tr("Glossary"), self._show_glossary_dialog)
        self._sidebar.addSeparator()
        self._sidebar.addAction(style.standardIcon(style.StandardPixmap.SP_FileDialogDetailedView), self.tr("Settings"), self._on_preferences)

        # Toolbar right-click customization
        self._sidebar.setContextMenuPolicy(Qt.CustomContextMenu)
        self._sidebar.customContextMenuRequested.connect(self._on_toolbar_context_menu)

        # ── Central widget ──
        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(self._tab_widget)

        content_row = QHBoxLayout()
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.setSpacing(0)
        content_row.addWidget(self._sidebar)
        content_row.addWidget(self._outer_splitter, 1)
        central_layout.addLayout(content_row, 1)
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

        # ── Smooth transition effects ─────────────────────────────
        self._source_opacity = QGraphicsOpacityEffect(self._source_view)
        self._source_view.setGraphicsEffect(self._source_opacity)
        self._source_opacity.setOpacity(1.0)

        self._trans_opacity = QGraphicsOpacityEffect(self._trans_view)
        self._trans_view.setGraphicsEffect(self._trans_opacity)
        self._trans_opacity.setOpacity(1.0)

        self._fade_anim_source = QPropertyAnimation(self._source_opacity, b"opacity")
        self._fade_anim_source.setDuration(150)
        self._fade_anim_source.setEasingCurve(QEasingCurve.InOutQuad)

        self._fade_anim_trans = QPropertyAnimation(self._trans_opacity, b"opacity")
        self._fade_anim_trans.setDuration(150)
        self._fade_anim_trans.setEasingCurve(QEasingCurve.InOutQuad)

        # ── Progress ring in status bar ───────────────────────────
        self._progress_ring = ProgressRing()
        self._progress_ring.setFixedSize(32, 32)
        self.statusBar().addPermanentWidget(self._progress_ring)

        # ── Live word/char count label ────────────────────────────
        self._sb_wordcount = QLabel("")
        self._sb_wordcount.setStyleSheet("color: gray; padding: 0 6px;")
        self.statusBar().addPermanentWidget(self._sb_wordcount)
        self._trans_view.textChanged.connect(self._update_live_word_count)

        # Install event filter for Tab/Shift+Tab navigation in translation editor
        self._trans_view.installEventFilter(self)
        
        # Apply saved layout preference
        if self._editor_on_right:
            self._apply_editor_layout()
        
        # Feature 7: Character counter setup
        if self._app_settings.get_value("show_character_counter", True):
            self._setup_character_counter()
        
        # Setup character limit
        self._char_count_limit = self._app_settings.get_value("character_limit", 280)

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

        save_as_act = file_menu.addAction(self.tr("Save &As…"))
        save_as_act.setShortcut(QKeySequence("Ctrl+Shift+S"))
        save_as_act.triggered.connect(self._on_save_as)

        file_menu.addSeparator()
        self._recent_menu = file_menu.addMenu(self.tr("Recent Files"))
        self._rebuild_recent_menu()

        file_menu.addSeparator()
        close_act = file_menu.addAction(self.tr("Close Tab"))
        close_act.setShortcut(QKeySequence("Ctrl+W"))
        close_act.triggered.connect(lambda: self._on_tab_close(self._tab_widget.currentIndex()))

        file_menu.addSeparator()
        file_menu.addAction(self.tr("Open Project…"), self._show_project_dock, QKeySequence("Ctrl+Shift+O"))
        file_menu.addSeparator()
        file_menu.addAction(self.tr("Quit"), QApplication.quit, QKeySequence.Quit)

        # Edit
        edit_menu = mb.addMenu(self.tr("&Edit"))
        edit_menu.addAction(self.tr("Undo"), self._do_undo, QKeySequence.Undo)
        edit_menu.addAction(self.tr("Redo"), self._do_redo, QKeySequence.Redo)
        edit_menu.addSeparator()
        edit_menu.addAction(self.tr("Find…"), self._on_focus_search, QKeySequence.Find)
        edit_menu.addAction(self.tr("Find && Replace…"), self._show_search_replace_dialog, QKeySequence("Ctrl+H"))
        edit_menu.addSeparator()
        edit_menu.addAction(self.tr("Copy source to translation"), self._copy_source_to_target, QKeySequence("Ctrl+B"))
        edit_menu.addAction(self.tr("Propagate Translation"), self._on_propagate_translation, QKeySequence("Ctrl+P"))
        edit_menu.addSeparator()
        edit_menu.addAction(self.tr("Batch Edit…"), self._show_batch_edit_dialog, QKeySequence("Ctrl+Shift+B"))
        edit_menu.addSeparator()
        # Feature 4: Segmentation
        edit_menu.addAction(self.tr("Split Entry…"), self._on_split_entry, QKeySequence("Ctrl+Alt+P"))
        edit_menu.addAction(self.tr("Merge Entries…"), self._on_merge_entries, QKeySequence("Ctrl+Alt+M"))
        edit_menu.addSeparator()
        edit_menu.addAction(self.tr("Preferences…"), self._on_preferences, QKeySequence("Ctrl+,"))

        # Catalog (POedit calls it this)
        catalog_menu = mb.addMenu(self.tr("&Catalog"))
        catalog_menu.addAction(self.tr("Validate (Lint)"), self._on_lint, QKeySequence("Ctrl+Shift+V"))
        catalog_menu.addAction(self.tr("Pre-translate…"), self._on_pretranslate_all, QKeySequence("Ctrl+Shift+T"))
        catalog_menu.addAction(self.tr("Batch Translate…"), self._show_batch_translate_dialog, QKeySequence("Ctrl+Alt+T"))
        catalog_menu.addAction(self.tr("Spell check current"), self._run_spellcheck, QKeySequence("F7"))
        catalog_menu.addAction(self.tr("File metadata…"), self._on_show_metadata)
        catalog_menu.addAction(self.tr("Edit Header…"), self._show_header_dialog, QKeySequence("Ctrl+Shift+H"))
        catalog_menu.addAction(self.tr("Feed file to TM"), self._on_feed_tm)
        catalog_menu.addSeparator()
        catalog_menu.addAction(self.tr("Statistics…"), self._show_statistics_dialog, QKeySequence("Ctrl+I"))
        catalog_menu.addSeparator()
        catalog_menu.addAction(self.tr("Compile translation"), self._on_compile, QKeySequence("Ctrl+Shift+B"))
        catalog_menu.addSeparator()
        catalog_menu.addAction(self.tr("Email Translation…"), self._email_translation)
        catalog_menu.addAction(self.tr("Merge with POT…"), self._msgmerge_with_pot, QKeySequence("Ctrl+Shift+M"))
        catalog_menu.addSeparator()
        catalog_menu.addAction(self.tr("Generate Report…"), self._on_generate_report, QKeySequence("Ctrl+Shift+R"))

        qa_menu = catalog_menu.addMenu(self.tr("Quality"))
        qa_menu.addAction(self.tr("Consistency check"), self._on_consistency_check)
        qa_menu.addAction(self.tr("Glossary…"), self._show_glossary_dialog)
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

        # Tools
        tools_menu = mb.addMenu(self.tr("&Tools"))
        tools_menu.addAction(self.tr("AI Review"), self._show_ai_review, QKeySequence("Ctrl+Shift+A"))
        tools_menu.addSeparator()
        tools_menu.addAction(self.tr("Compare Files…"), self._show_diff_dialog)
        tools_menu.addAction(self.tr("Diff with Previous Version…"), self._show_git_diff_dialog, QKeySequence("Ctrl+Shift+D"))
        tools_menu.addAction(self.tr("Project Dashboard"), self._show_dashboard, QKeySequence("Ctrl+D"))
        tools_menu.addSeparator()
        # Feature 3: TMX Import/Export
        tmx_menu = tools_menu.addMenu(self.tr("TMX"))
        tmx_menu.addAction(self.tr("Import TMX…"), self._on_import_tmx)
        tmx_menu.addAction(self.tr("Export TMX…"), self._on_export_tmx)
        tools_menu.addSeparator()
        # Feature 8: Unicode Inspector
        tools_menu.addAction(self.tr("Unicode Inspector"), self._show_unicode_inspector, QKeySequence("Ctrl+Shift+U"))
        tools_menu.addSeparator()
        # Feature 2: Plugin management
        tools_menu.addAction(self.tr("Manage Plugins…"), self._show_plugin_dialog)
        tools_menu.addSeparator()
        # Feature 14: Macros
        macros_menu = tools_menu.addMenu(self.tr("Macros"))
        macros_menu.addAction(self.tr("Record Macro"), self._on_record_macro, QKeySequence("Ctrl+Shift+M"))
        macros_menu.addAction(self.tr("Play Macro"), self._on_play_macro, QKeySequence("Ctrl+M"))
        macros_menu.addAction(self.tr("Manage Macros…"), self._show_macro_dialog)
        tools_menu.addSeparator()
        # Feature 11: Git Integration
        git_integration_menu = tools_menu.addMenu(self.tr("Git"))
        git_integration_menu.addAction(self.tr("Commit…"), self._on_git_commit_dialog, QKeySequence("Ctrl+Shift+G"))
        git_integration_menu.addAction(self.tr("Status"), self._on_git_status)
        git_integration_menu.addAction(self.tr("Diff"), self._on_git_diff)
        # New features
        tools_menu.addAction(self.tr("Regex Tester"), self._show_regex_tester, QKeySequence("Ctrl+Shift+X"))
        tools_menu.addAction(self.tr("Layout Simulator"), self._show_layout_simulator, QKeySequence("Ctrl+Shift+L"))
        tools_menu.addAction(self.tr("OCR Screenshot…"), self._show_ocr_dialog, QKeySequence("Ctrl+Shift+O"))
        tools_menu.addSeparator()
        
        # Crowdin submenu
        crowdin_menu = tools_menu.addMenu(self.tr("Crowdin"))
        crowdin_menu.addAction(self.tr("Pull Latest"), self._crowdin_pull_latest)
        tools_menu.addSeparator()
        tools_menu.addAction(self.tr("Glossary…"), self._show_glossary_dialog)
        tools_menu.addAction(self.tr("Concordance Search…"), self._show_concordance_dialog, QKeySequence("Ctrl+Alt+K"))
        tools_menu.addSeparator()
        tools_menu.addAction(self.tr("Open Video…"), self._on_open_video, QKeySequence("Ctrl+Shift+V"))
        tools_menu.addAction(self.tr("Extract Subtitles from Video…"), self._on_video_subtitles)
        
        # View
        view_menu = mb.addMenu(self.tr("&View"))
        view_menu.addAction(self.tr("Compare language…"), self._on_compare_lang)
        view_menu.addAction(self.tr("Auto-propagate"), self._on_auto_propagate)
        view_menu.addSeparator()
        view_menu.addAction(self.tr("Show Bookmarked Only"), self._toggle_bookmarked_filter, QKeySequence("Ctrl+Shift+K"))
        view_menu.addAction(self.tr("Show Pinned First"), self._toggle_pinned_first, QKeySequence("Ctrl+Shift+P"))
        view_menu.addAction(self.tr("Review Mode"), self._toggle_review_mode, QKeySequence("Ctrl+R"))
        view_menu.addAction(self.tr("Focus Mode"), self._toggle_focus_mode, QKeySequence("Ctrl+Shift+F"))

        # Layout toggle
        self._layout_toggle_action = view_menu.addAction(
            self.tr("Editor on Right") if not self._editor_on_right else self.tr("Editor Below"),
            self._toggle_editor_layout)

        # Simple Mode
        self._simple_mode_action = view_menu.addAction(self.tr("Simple Mode"), self._toggle_simple_mode, QKeySequence("Ctrl+Shift+L"))
        self._simple_mode_action.setCheckable(True)
        self._simple_mode = False

        # Zen Mode
        view_menu.addAction(self.tr("Zen Mode"), self._toggle_zen_mode, QKeySequence("Ctrl+Shift+Z"))

        # Feature 13: Fullscreen Mode
        view_menu.addAction(self.tr("Fullscreen"), self._toggle_fullscreen, QKeySequence("F11"))
        view_menu.addSeparator()
        # Feature 10: Minimap
        view_menu.addAction(self.tr("Minimap"), self._toggle_minimap, QKeySequence("Ctrl+Shift+M"))
        # Feature 15: Watch Mode
        view_menu.addAction(self.tr("Watch File"), self._toggle_watch_mode, QKeySequence("Ctrl+W"))
        view_menu.addAction(self.tr("Translation Map…"), self._show_locale_map_dialog)
        view_menu.addSeparator()
        # Feature 10: Achievements
        view_menu.addAction(self.tr("Achievements…"), self._show_achievements_dialog)
        view_menu.addSeparator()
        theme_menu = view_menu.addMenu(self.tr("Theme"))
        theme_menu.addAction(self.tr("System Default"), lambda: self._set_theme("system"))
        theme_menu.addAction(self.tr("Light"), lambda: self._set_theme("light"))
        theme_menu.addAction(self.tr("Dark"), lambda: self._set_theme("dark"))
        theme_menu.addAction(self.tr("Solarized Dark"), lambda: self._set_theme("solarized_dark"))
        theme_menu.addAction(self.tr("Nord"), lambda: self._set_theme("nord"))
        theme_menu.addAction(self.tr("Monokai"), lambda: self._set_theme("monokai"))

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
        help_menu.addAction(self.tr("Documentation"), lambda: QDesktopServices.openUrl(QUrl("https://github.com/yeager/linguaedit/tree/main/docs")))
        help_menu.addAction(self.tr("Report a Bug"), lambda: QDesktopServices.openUrl(QUrl("https://github.com/yeager/linguaedit/issues")))
        help_menu.addSeparator()
        help_menu.addAction(self.tr("Donate ♥"), self._on_donate)
        help_menu.addSeparator()
        help_menu.addAction(self.tr("About LinguaEdit"), self._on_about)
        help_menu.addAction(self.tr("About Qt"), lambda: QApplication.instance().aboutQt())

    # ── Toolbar ───────────────────────────────────────────────────

    def _build_toolbar(self):
        tb = QToolBar(self.tr("Main"))
        tb.setObjectName("MainToolBar")
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.addToolBar(tb)

        style = self.style()

        def _make_arrow_icon(direction: str, color: str = "#8ab4f8") -> QIcon:
            """Create a modern rounded arrow icon."""
            from PySide6.QtGui import QPixmap, QPainter, QPen, QPainterPath
            px = QPixmap(24, 24)
            px.fill(QColor(0, 0, 0, 0))
            p = QPainter(px)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            pen = QPen(QColor(color), 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            if direction == "undo":  # curved left arrow
                path = QPainterPath()
                path.moveTo(16, 6)
                path.cubicTo(10, 6, 6, 10, 6, 14)
                path.lineTo(6, 10)
                p.drawPath(path)
                p.drawLine(6, 14, 10, 14)
                p.drawLine(6, 14, 6, 10)
            elif direction == "redo":  # curved right arrow
                path = QPainterPath()
                path.moveTo(8, 6)
                path.cubicTo(14, 6, 18, 10, 18, 14)
                path.lineTo(18, 10)
                p.drawPath(path)
                p.drawLine(14, 14, 18, 14)
                p.drawLine(18, 14, 18, 10)
            elif direction == "up":  # chevron up
                p.drawLine(6, 15, 12, 8)
                p.drawLine(12, 8, 18, 15)
            elif direction == "down":  # chevron down
                p.drawLine(6, 9, 12, 16)
                p.drawLine(12, 16, 18, 9)
            p.end()
            return QIcon(px)

        # Undo / Redo
        tb.addAction(_make_arrow_icon("undo", "#f0a050"), self.tr("Undo"), self._do_undo)
        tb.addAction(_make_arrow_icon("redo", "#f0a050"), self.tr("Redo"), self._do_redo)
        tb.addAction(style.standardIcon(style.StandardPixmap.SP_DialogSaveButton),
                     self.tr("Save As…"), self._on_save_as)
        tb.addSeparator()

        # Navigation
        tb.addAction(_make_arrow_icon("up", "#8ab4f8"), self.tr("Previous"), lambda: self._navigate(-1))
        self._nav_counter_label = QLabel(" 0 / 0 ")
        self._nav_counter_label.setStyleSheet("font-weight: bold; padding: 0 4px;")
        tb.addWidget(self._nav_counter_label)
        tb.addAction(_make_arrow_icon("down", "#8ab4f8"), self.tr("Next"), lambda: self._navigate(1))
        tb.addSeparator()

        # Copy Source
        tb.addAction(style.standardIcon(style.StandardPixmap.SP_FileIcon), self.tr("Copy Source"), self._copy_source_to_target)
        tb.addSeparator()

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
        tb.addAction(style.standardIcon(style.StandardPixmap.SP_FileDialogContentsView),
                     self.tr("Concordance"), self._show_concordance_dialog)

    # ── Keyboard shortcuts ────────────────────────────────────────

    def _setup_shortcuts(self):
        # Poedit-style shortcuts
        QShortcut(QKeySequence("Ctrl+Return"), self, self._copy_source_to_target)
        QShortcut(QKeySequence("Ctrl+U"), self, lambda: self._fuzzy_check.toggle())
        QShortcut(QKeySequence("Alt+Return"), self, lambda: self._navigate_untranslated(1))
        QShortcut(QKeySequence("Ctrl+Shift+Up"), self, lambda: self._navigate_fuzzy(-1))
        QShortcut(QKeySequence("Ctrl+Shift+Down"), self, lambda: self._navigate_fuzzy(1))

        # Feature 6: Bokmärken
        QShortcut(QKeySequence("Ctrl+B"), self, self._toggle_bookmark)
        QShortcut(QKeySequence("F2"), self, lambda: self._navigate_bookmarks(1))
        QShortcut(QKeySequence("Shift+F2"), self, lambda: self._navigate_bookmarks(-1))

        # Feature 7: Taggar
        QShortcut(QKeySequence("Ctrl+T"), self, self._add_tag)

        # Feature 13: Fullscreen escape / Zen mode escape
        QShortcut(QKeySequence("Escape"), self, self._on_escape_pressed)

        # Feature 13: Quick Actions
        QShortcut(QKeySequence("Ctrl+."), self, self._show_quick_actions)
        
        # Zen Mode
        QShortcut(QKeySequence("Ctrl+Shift+Z"), self, self._toggle_zen_mode)

    def eventFilter(self, obj, event):
        """Handle Tab/Shift+Tab in translation editor and tree hover tooltips."""
        from PySide6.QtCore import QEvent
        from PySide6.QtWidgets import QToolTip

        # Entry Preview on Hover (Feature 4)
        if obj is self._tree.viewport() and event.type() == QEvent.ToolTip:
            pos = event.pos()
            item = self._tree.itemAt(pos)
            if item and self._file_data:
                idx = item.data(0, Qt.UserRole)
                entries = self._get_entries()
                if idx is not None and 0 <= idx < len(entries):
                    msgid, msgstr, is_fuzzy = entries[idx]
                    # Truncate long texts
                    src = msgid[:120].replace("\n", " ")
                    if len(msgid) > 120:
                        src += "…"
                    trn = msgstr[:120].replace("\n", " ")
                    if len(msgstr) > 120:
                        trn += "…"
                    # Status color
                    if is_fuzzy:
                        status_html = "<span style='color:#b8860b;'>🔶 Fuzzy</span>"
                    elif msgstr:
                        status_html = "<span style='color:#1e8232;'>✓ Translated</span>"
                    else:
                        status_html = "<span style='color:#a03232;'>● Untranslated</span>"
                    tooltip = (
                        f"<b>{self.tr('Source:')}</b> {src}<br>"
                        f"{self.tr('Translation:')} {trn}<br>"
                        f"{status_html}"
                    )
                    QToolTip.showText(event.globalPos(), tooltip, self._tree)
                    return True
            QToolTip.hideText()
            return True

        if getattr(self, '_trans_view', None) is not None and obj is self._trans_view and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Tab and not event.modifiers():
                self._tab_save_next()
                return True
            if event.key() == Qt.Key_Backtab or (event.key() == Qt.Key_Tab and event.modifiers() & Qt.ShiftModifier):
                self._shift_tab_save_prev()
                return True
            if event.key() == Qt.Key_Return and event.modifiers() & Qt.ControlModifier:
                self._ctrl_enter_save_next_untranslated()
                return True
        return super().eventFilter(obj, event)

    # ══════════════════════════════════════════════════════════════
    #  ENTRY TABLE (QTreeWidget)
    # ══════════════════════════════════════════════════════════════

    def _populate_list(self):
        self._tree.blockSignals(True)
        self._tree.setSortingEnabled(False)
        self._tree.clear()

        # Set headers based on file type
        if self._file_type == "subtitles":
            self._tree.setHeaderLabels([
                "#", "⭐",
                self.tr("Time interval"),
                self.tr("Source text"),
                self.tr("Translation"),
                "",
            ])
        else:
            self._tree.setHeaderLabels([
                "#", "⭐",
                self.tr("Source text"),
                self.tr("Translation"),
                self.tr("Tags"),
                "",
            ])

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

            # Bokmärke, pinned och taggar
            icons = []
            if orig_idx in self._pinned_entries:
                icons.append("📌")
            if orig_idx in self._bookmarks:
                icons.append("⭐")
            bookmark_icon = " ".join(icons)

            if self._file_type == "subtitles":
                entry = self._file_data.entries[orig_idx]
                timestamp = entry.timestamp
                item = _SortableItem([str(orig_idx + 1), bookmark_icon, timestamp, src_preview, trans_preview, status])
            else:
                tags_text = ", ".join(self._tags.get(orig_idx, []))
                item = _SortableItem([str(orig_idx + 1), bookmark_icon, src_preview, trans_preview, tags_text, status])
            item.setData(0, Qt.UserRole, orig_idx)

            # Set delegate status for colored borders
            if has_warning:
                delegate_status = EntryItemDelegate.STATUS_WARNING
            elif is_fuzzy:
                delegate_status = EntryItemDelegate.STATUS_FUZZY
            elif not msgstr:
                delegate_status = EntryItemDelegate.STATUS_UNTRANSLATED
            else:
                delegate_status = EntryItemDelegate.STATUS_TRANSLATED
            for col in range(6):
                item.setData(col, Qt.UserRole + 1, delegate_status)

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
        
        # Update minimap
        self._update_minimap()

    @staticmethod
    def _color_row(item: QTreeWidgetItem, color: QColor):
        brush = QBrush(color)
        for col in range(4):
            item.setBackground(col, brush)

    def _on_tree_item_changed(self, current: QTreeWidgetItem | None, previous: QTreeWidgetItem | None):
        self._save_current_entry()

        # Lint the previous row and update its status icon/color
        if previous is not None and self._file_data:
            prev_idx = previous.data(0, Qt.UserRole)
            if prev_idx is not None:
                self._lint_and_update_row(previous, prev_idx)

        if current is None:
            self._current_index = -1
            return
        idx = current.data(0, Qt.UserRole)
        if idx is not None:
            self._current_index = idx
            # Smooth fade transition
            self._play_entry_fade()
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

    def _navigate_fuzzy(self, direction: int):
        """Navigate to next/previous fuzzy entry (Poedit-style)."""
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
                    _, _, is_fuzzy = entries[orig_idx]
                    if is_fuzzy:
                        self._tree.setCurrentItem(item)
                        self._tree.scrollToItem(item)
                        return
            row += direction

        self._show_toast(self.tr("No more fuzzy strings"))

    def _navigate_to_entry(self, orig_idx):
        """Navigate to a specific entry by its original index."""
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            if item.data(0, Qt.UserRole) == orig_idx:
                self._tree.setCurrentItem(item)
                self._tree.scrollToItem(item)
                break

    # ══════════════════════════════════════════════════════════════
    #  ENTRY DISPLAY / EDITING
    # ══════════════════════════════════════════════════════════════

    def _display_entry(self, idx: int):
        entries = self._get_entries()
        if idx < 0 or idx >= len(entries):
            return
        msgid, msgstr, is_fuzzy = entries[idx]

        self._source_view.setPlainText(msgid)
        if self._file_type == "subtitles":
            entry = self._file_data.entries[idx]
            self._source_header.setText(
                f"<b>{self.tr('Source text')}</b>  "
                f"<span style='color:gray'>#{entry.index} | {entry.timestamp}</span>"
            )
            # Show timestamp editor
            self._timestamp_frame.setVisible(True)
            fmt = "," if self._file_data.format == "srt" else "."
            start = entry.start_time.replace(".", fmt)
            end = entry.end_time.replace(".", fmt)
            self._timestamp_edit.setText(f"{start} --> {end}")

            # Seek video preview to this timestamp
            if self._video_dock and self._video_dock.isVisible() and self._video_dock.player.has_video():
                self._video_dock.player.seek_to_time(entry.start_time)
                self._video_dock.player.set_segment(
                    entry.start_time, entry.end_time, msgid, msgstr
                )
        else:
            self._source_header.setText(f"<b>{self.tr('Source text')}</b>  <span style='color:gray'>({len(msgid.split())} {self.tr('words')})</span>")
            self._timestamp_frame.setVisible(False)

        self._trans_block = True
        self._trans_view.setPlainText(msgstr)
        self._trans_block = False

        # Trigger MT suggestions for source text (if translation is empty)
        if not msgstr.strip():
            self._trans_view.set_source_text(msgid)
        else:
            self._trans_view.set_source_text("")  # hide suggestions

        # Set spell check language
        self._trans_view.set_spell_language(self._spell_lang)

        # Load translator comment
        comment = ""
        if self._file_type == "po":
            comment = self._file_data.entries[idx].tcomment or ""
        elif self._file_type == "ts":
            comment = self._file_data.entries[idx].comment or ""
        self._comment_view.setPlainText(comment)

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
        elif self._file_type in ("sdlxliff", "mqxliff"):
            e = self._file_data.entries[idx]
            if e.note:
                self._extracted_comment_label.setText(e.note)
                self._extracted_comment_row.setVisible(True)
            if e.id:
                self._msgctxt_label.setText(f"ID: {e.id}")
                self._msgctxt_row.setVisible(True)
            info_parts = []
            if e.state:
                info_parts.append(f"State: {e.state}")
            if hasattr(e, 'origin') and e.origin:
                info_parts.append(f"Origin: {e.origin}")
            if hasattr(e, 'match_percent') and e.match_percent:
                info_parts.append(f"Match: {e.match_percent}%")
            if e.locked:
                info_parts.append("Locked")
            if e.confirmed:
                info_parts.append("Confirmed")
            if info_parts:
                self._flags_label.setText(" | ".join(info_parts))
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

        # Source references (where the string appears in code)
        if self._file_type == "po" and hasattr(self._file_data.entries[idx], 'occurrences') and self._file_data.entries[idx].occurrences:
            refs = self._file_data.entries[idx].occurrences
            ref_parts = [f"📍 {f}:{l}" for f, l in refs[:10]]
            if len(refs) > 10:
                ref_parts.append(self.tr("… and %d more") % (len(refs) - 10))
            self._source_refs_label.setText("  ".join(ref_parts))
            self._source_refs_label.setVisible(True)
        elif self._file_type == "ts" and hasattr(self._file_data.entries[idx], 'location_file') and self._file_data.entries[idx].location_file:
            e = self._file_data.entries[idx]
            self._source_refs_label.setText(f"📍 {e.location_file}:{e.location_line}")
            self._source_refs_label.setVisible(True)
        else:
            self._source_refs_label.setVisible(False)

        self._show_tm_suggestions(msgid)
        self._display_comment_threads()
        self._update_split_view(idx)

        # Update context panel and quick toolbar
        self._update_context_panel(msgid)
        self._update_quick_toolbar_state()
        self._run_inline_lint()
        
        # Update minimap current index
        if hasattr(self, '_minimap'):
            self._minimap.set_current_index(idx)

        # Focus translation editor
        self._trans_view.setFocus()

    def _copy_source_to_target(self):
        if self._current_index < 0 or not self._file_data:
            return
        entries = self._get_entries()
        if self._current_index < len(entries):
            self._trans_view.setPlainText(entries[self._current_index][0])
    
    def _on_propagate_translation(self):
        """Propagera aktuell översättning till alla identiska source-strängar."""
        if self._current_index < 0 or not self._file_data:
            return
            
        entries = self._get_entries()
        current_entry = entries[self._current_index]
        current_source = current_entry[0]
        current_translation = self._trans_view.toPlainText().strip()
        
        if not current_translation:
            QMessageBox.information(self, self.tr("Propagate Translation"), 
                                  self.tr("Current string has no translation to propagate."))
            return
        
        # Hitta alla entries med samma source text
        identical_entries = []
        for i, entry in enumerate(entries):
            if i != self._current_index and entry[0] == current_source:
                identical_entries.append((i, entry))
        
        if not identical_entries:
            QMessageBox.information(self, self.tr("Propagate Translation"), 
                                  self.tr("No identical source strings found."))
            return
        
        # Visa bekräftelsedialog
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QCheckBox, QDialogButtonBox
        
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr("Propagate Translation"))
        dialog.setMinimumWidth(500)
        
        layout = QVBoxLayout(dialog)
        
        # Header text
        header = QLabel(self.tr(f"Found {len(identical_entries)} identical strings. Apply this translation to all?"))
        header.setWordWrap(True)
        layout.addWidget(header)
        
        # Show current translation
        current_label = QLabel(self.tr(f"<b>Translation:</b> {html_escape(current_translation[:100])}"))
        current_label.setWordWrap(True)
        layout.addWidget(current_label)
        
        # Checkbox list
        checkboxes = []
        for i, (entry_idx, entry) in enumerate(identical_entries):
            cb = QCheckBox(f"{entry_idx + 1}. {entry[0][:80]}...")
            cb.setChecked(True)
            checkboxes.append((cb, entry_idx))
            layout.addWidget(cb)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        if dialog.exec() == QDialog.Accepted:
            # Apply translation to selected entries
            applied_count = 0
            for cb, entry_idx in checkboxes:
                if cb.isChecked():
                    if self._file_type == "po":
                        self._file_data.entries[entry_idx].msgstr = current_translation
                    elif self._file_type == "ts":
                        self._file_data.entries[entry_idx].translation = current_translation
                    elif self._file_type == "json":
                        self._file_data.translations[list(self._file_data.translations.keys())[entry_idx]] = current_translation
                    # Add other file types as needed
                    applied_count += 1
            
            if applied_count > 0:
                self._modified = True
                self._refresh_tree()
                QMessageBox.information(self, self.tr("Propagate Translation"), 
                                      self.tr(f"Applied translation to {applied_count} strings."))
            
            self._update_progress()

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
        src_label = QLabel(self.tr("Plural: %s") % entry.msgid_plural)
        src_label.setWordWrap(True)
        self._plural_notebook.addTab(src_label, "msgid_plural")
        n_forms = max(2, max(entry.msgstr_plural.keys(), default=1) + 1)
        self._plural_views: list[QTextEdit] = []
        for i in range(n_forms):
            tv = QTextEdit()
            tv.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            tv.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
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
        # Reset compile icon — file changed since last compile
        if hasattr(self, '_compile_action') and self._compile_status is not None:
            style = self.style()
            self._compile_action.setIcon(style.standardIcon(style.StandardPixmap.SP_MediaPlay))
            self._compile_status = None
        # Auto-clear fuzzy flag when user edits a fuzzy entry
        if self._current_index >= 0 and self._file_data and self._fuzzy_check.isChecked():
            self._fuzzy_check.setChecked(False)  # triggers _on_fuzzy_toggled
            # Update the current tree row immediately
            current_item = self._tree.currentItem()
            if current_item is not None:
                self._lint_and_update_row(current_item, self._current_index)
        self._lint_timer.start()
        
        # Feature 7: Update character counter
        if self._app_settings.get_value("show_character_counter", True):
            self._update_character_count()
        
        # Record macro action if recording
        if hasattr(self, '_macro_manager') and self._macro_manager.is_recording:
            self._record_macro_action(MacroActionType.EDIT_TEXT, 
                                    entry_index=self._current_index,
                                    text=self._trans_view.toPlainText())
        
    def _on_comment_changed(self):
        """Handle translator comment changes."""
        if self._current_index >= 0 and self._file_data:
            comment_text = self._comment_view.toPlainText()
            
            if self._file_type == "po":
                self._file_data.entries[self._current_index].tcomment = comment_text
                self._modified = True
            elif self._file_type == "ts":
                # For TS files, we can use the comment field
                self._file_data.entries[self._current_index].comment = comment_text
                self._modified = True

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

    def _lint_and_update_row(self, item: QTreeWidgetItem, idx: int):
        """Lint a single entry and update its tree row status icon and color."""
        entries = self._get_entries()
        if idx >= len(entries):
            return
        msgid, msgstr, is_fuzzy = entries[idx]
        flags = ["fuzzy"] if is_fuzzy else []
        issues = _lint_single(msgid, msgstr, flags)
        self._lint_cache[idx] = issues
        has_warning = any(iss.severity in ("error", "warning") for iss in issues)

        # Update status icon (column 5 = status column)
        if has_warning:
            status = "⚠"
        elif is_fuzzy:
            status = "🔶"
        elif msgstr:
            status = "✓"
        else:
            status = "●"
        item.setText(5, status)

        # Update delegate status for colored borders
        if has_warning:
            delegate_status = EntryItemDelegate.STATUS_WARNING
        elif is_fuzzy:
            delegate_status = EntryItemDelegate.STATUS_FUZZY
        elif not msgstr:
            delegate_status = EntryItemDelegate.STATUS_UNTRANSLATED
        else:
            delegate_status = EntryItemDelegate.STATUS_TRANSLATED
        for col in range(6):
            item.setData(col, Qt.UserRole + 1, delegate_status)

        # Update row color
        colors = _get_colors()
        if has_warning:
            self._color_row(item, colors['warning'])
        elif is_fuzzy:
            self._color_row(item, colors['fuzzy'])
        elif not msgstr:
            self._color_row(item, colors['untranslated'])
        else:
            # Clear background for translated rows
            for col in range(6):
                item.setBackground(col, QBrush())

        # Update status column foreground (column 5)
        if not msgstr:
            item.setForeground(5, QBrush(colors['untranslated_fg']))
        elif is_fuzzy:
            item.setForeground(5, QBrush(colors['fuzzy_fg']))
        else:
            item.setForeground(5, QBrush(colors['translated_fg']))

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
    
    def _generate_word_diff_html(self, source_text: str, tm_source: str) -> str:
        """Genererar HTML-diff på ord-nivå mellan source och TM-förslag."""
        if not source_text or not tm_source:
            return ""
        
        # Split på ord
        source_words = source_text.split()
        tm_words = tm_source.split()
        
        # Använd SequenceMatcher för att hitta skillnader
        matcher = SequenceMatcher(None, source_words, tm_words)
        html_parts = []
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                # Identiska ord
                html_parts.extend(source_words[i1:i2])
            elif tag == 'delete':
                # Ord som tagits bort från source
                deleted = " ".join(source_words[i1:i2])
                html_parts.append(f'<span style="background-color: #ffcccc; text-decoration: line-through;">{html_escape(deleted)}</span>')
            elif tag == 'insert':
                # Ord som lagts till i TM
                inserted = " ".join(tm_words[j1:j2])
                html_parts.append(f'<span style="background-color: #ccffcc;">{html_escape(inserted)}</span>')
            elif tag == 'replace':
                # Ersatta ord
                deleted = " ".join(source_words[i1:i2])
                inserted = " ".join(tm_words[j1:j2])
                html_parts.append(f'<span style="background-color: #ffcccc; text-decoration: line-through;">{html_escape(deleted)}</span>')
                html_parts.append(f'<span style="background-color: #ccffcc;">{html_escape(inserted)}</span>')
        
        return " ".join(html_parts)

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
            
            # Match percentage
            pct_label = QLabel(f"<b>{m.similarity:.0%}</b> match")
            pct_label.setStyleSheet("color: gray; font-size: 10px;")
            row.addWidget(pct_label)
            
            # Diff mellan source och TM source
            if m.similarity < 1.0:  # Visa bara diff om inte 100% match
                diff_html = self._generate_word_diff_html(msgid, m.source)
                if diff_html:
                    diff_label = QLabel(diff_html)
                    diff_label.setWordWrap(True)
                    diff_label.setTextFormat(Qt.RichText)
                    diff_label.setStyleSheet("font-size: 9px; padding: 2px; border: 1px solid #ddd; background-color: #f9f9f9;")
                    row.addWidget(diff_label)
            
            # Target text button
            btn = QPushButton(m.target[:80] + ("..." if len(m.target) > 80 else ""))
            btn.setToolTip(f"Source: {m.source}\nTarget: {m.target}")
            btn.setStyleSheet("text-align: left; padding: 4px;")
            btn.clicked.connect(lambda checked, t=m.target: self._apply_tm_match(t))
            row.addWidget(btn)
            self._tm_layout.addWidget(container)

    def _apply_tm_match(self, text):
        self._trans_view.setPlainText(text)
        self._fuzzy_check.setChecked(True)

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
        modes = ["all", "untranslated", "fuzzy", "translated", "reviewed", "warnings"]
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
                elif self._filter_mode == "reviewed":
                    visible = self._review_status.get(orig_idx) == "approved"
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
        elif self._file_type in ("sdlxliff", "mqxliff"):
            return [(e.source, e.target, e.is_fuzzy) for e in self._file_data.entries]
        elif self._file_type == "android":
            return [(e.key, e.value, False) for e in self._file_data.entries]
        elif self._file_type == "arb":
            return [(e.key, e.value, False) for e in self._file_data.entries]
        elif self._file_type == "php":
            return [(e.key, e.value, False) for e in self._file_data.entries]
        elif self._file_type == "yaml":
            return [(e.key, e.value, False) for e in self._file_data.entries]
        elif self._file_type == "godot":
            # För Godot CSV/TRES - använd första språket som target
            if self._file_data.languages:
                target_lang = self._file_data.languages[0]
                return [(e.key, e.translations.get(target_lang, ""), False) for e in self._file_data.entries]
            return [(e.key, "", False) for e in self._file_data.entries]
        elif self._file_type == "chrome_i18n":
            return [(e.key, e.message, False) for e in self._file_data.entries]
        elif self._file_type == "java_properties":
            return [(e.key, e.value, False) for e in self._file_data.entries]
        elif self._file_type == "subtitles":
            return [(e.text, e.translation, e.fuzzy) for e in self._file_data.entries]
        elif self._file_type in ("apple_strings", "unity_asset", "resx"):
            return [(e.msgid, e.msgstr, e.fuzzy) for e in self._file_data.entries]
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
        
        # Apply filters first
        filtered_indices = []
        for i in indices:
            msgid, msgstr, is_fuzzy = entries[i]
            
            # Feature 6: Bokmärken filter
            if self._show_bookmarked_only and i not in self._bookmarks:
                continue
            
            # Feature 7: Taggar filter
            if self._active_tag_filter:
                entry_tags = self._tags.get(i, [])
                if self._active_tag_filter not in entry_tags:
                    continue
            
            # Feature 8: Review mode filter
            if self._review_mode:
                review_status = self._review_status.get(i, "needs_review")
                if review_status not in ["needs_review", "rejected"]:
                    continue
            
            # Feature 13: Focus mode filter
            if self._focus_mode:
                # Hide completed translations (har översättning och inte fuzzy)
                if msgstr and not is_fuzzy:
                    continue
            
            # Standard filter mode
            if self._filter_mode == "untranslated" and msgstr:
                continue
            elif self._filter_mode == "fuzzy" and not is_fuzzy:
                continue
            elif self._filter_mode == "translated" and (not msgstr or is_fuzzy):
                continue
            elif self._filter_mode == "warnings":
                lint_issues = self._lint_cache.get(i, [])
                has_warning = any(iss.severity in ("error", "warning") for iss in lint_issues)
                if not has_warning:
                    continue
            
            filtered_indices.append(i)
        
        indices = filtered_indices
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
                has_lint = bool(self._lint_cache.get(i))
                if not msgstr:
                    return 0  # untranslated first
                if has_lint:
                    return 1  # lint errors second
                if fuzzy:
                    return 2  # fuzzy third
                return 3  # translated last
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
        
        # Apply pinned first sorting if enabled
        if self._show_pinned_first and self._pinned_entries:
            pinned_indices = [i for i in self._sort_order if i in self._pinned_entries]
            unpinned_indices = [i for i in self._sort_order if i not in self._pinned_entries]
            self._sort_order = pinned_indices + unpinned_indices

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
        elif self._file_type in ("xliff", "sdlxliff", "mqxliff"):
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
        """Set application theme."""
        app = QApplication.instance()
        settings = Settings.get()
        settings["theme"] = theme

        # Clear stylesheet first (dark theme sets one)
        app.setStyleSheet("")

        if theme == "dark":
            self._apply_dark_theme(app)
        elif theme == "solarized_dark":
            self._apply_solarized_dark_theme(app)
        elif theme == "nord":
            self._apply_nord_theme(app)
        elif theme == "monokai":
            self._apply_monokai_theme(app)
        elif theme == "light":
            app.setPalette(app.style().standardPalette())
            app.setStyleSheet("")
        else:
            # System default
            app.setPalette(app.style().standardPalette())
            app.setStyleSheet("")

        settings.save()
        # Refresh list to update row colors
        if self._file_data:
            self._populate_list()
        self._show_toast(self.tr("Theme changed to %s") % theme)

    def _apply_dark_theme(self, app):
        """Apply dark theme with comprehensive palette and stylesheet."""
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
        palette.setColor(QPalette.Mid, QColor(60, 60, 60))
        palette.setColor(QPalette.Dark, QColor(18, 18, 18))
        palette.setColor(QPalette.Shadow, QColor(10, 10, 10))
        # Disabled colors
        palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(100, 100, 100))
        palette.setColor(QPalette.Disabled, QPalette.Text, QColor(100, 100, 100))
        palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(100, 100, 100))
        app.setPalette(palette)

        # Comprehensive stylesheet for all widgets
        app.setStyleSheet("""
            QMainWindow, QDialog {
                background-color: #1e1e1e;
            }
            QToolBar {
                background-color: #252525;
                border-bottom: 1px solid #3a3a3a;
                spacing: 4px;
                padding: 2px;
            }
            QToolBar QToolButton {
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 3px;
                padding: 4px;
                color: #e0e0e0;
            }
            QToolBar QToolButton:hover {
                background-color: #3a3a3a;
                border-color: #505050;
            }
            QToolBar QToolButton:pressed {
                background-color: #2a5a8a;
            }
            QMenuBar {
                background-color: #252525;
                color: #e0e0e0;
                border-bottom: 1px solid #3a3a3a;
            }
            QMenuBar::item:selected {
                background-color: #3a3a3a;
            }
            QMenu {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: 1px solid #3a3a3a;
            }
            QMenu::item:selected {
                background-color: #3264b4;
            }
            QMenu::separator {
                height: 1px;
                background: #3a3a3a;
                margin: 4px 8px;
            }
            QTreeWidget, QTableWidget, QListWidget {
                background-color: #1a1a1a;
                alternate-background-color: #222222;
                color: #e0e0e0;
                border: 1px solid #3a3a3a;
                selection-background-color: #2a5a8a;
                gridline-color: #3a3a3a;
            }
            QTreeWidget::item:hover, QTableWidget::item:hover {
                background-color: #2a2a2a;
            }
            QHeaderView::section {
                background-color: #2a2a2a;
                color: #c0c0c0;
                border: 1px solid #3a3a3a;
                padding: 4px;
            }
            QTextEdit, QPlainTextEdit {
                background-color: #1a1a1a;
                color: #e0e0e0;
                border: 1px solid #3a3a3a;
                selection-background-color: #2a5a8a;
            }
            QLineEdit {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: 1px solid #3a3a3a;
                border-radius: 3px;
                padding: 4px;
            }
            QLineEdit:focus {
                border-color: #5a8aba;
            }
            QComboBox {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: 1px solid #3a3a3a;
                border-radius: 3px;
                padding: 4px;
            }
            QComboBox::drop-down {
                border-left: 1px solid #3a3a3a;
            }
            QComboBox QAbstractItemView {
                background-color: #2a2a2a;
                color: #e0e0e0;
                selection-background-color: #3264b4;
            }
            QPushButton {
                background-color: #353535;
                color: #e0e0e0;
                border: 1px solid #4a4a4a;
                border-radius: 3px;
                padding: 5px 12px;
            }
            QPushButton:hover {
                background-color: #404040;
                border-color: #5a5a5a;
            }
            QPushButton:pressed {
                background-color: #2a5a8a;
            }
            QPushButton:disabled {
                background-color: #2a2a2a;
                color: #666666;
            }
            QCheckBox {
                color: #e0e0e0;
                spacing: 6px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #4a4a4a;
                border-radius: 3px;
                background-color: #2a2a2a;
            }
            QCheckBox::indicator:checked {
                background-color: #3264b4;
                border-color: #5a8aba;
            }
            QProgressBar {
                background-color: #2a2a2a;
                border: 1px solid #3a3a3a;
                border-radius: 3px;
                text-align: center;
                color: #e0e0e0;
            }
            QProgressBar::chunk {
                background-color: #3264b4;
                border-radius: 2px;
            }
            QTabWidget::pane {
                border: 1px solid #3a3a3a;
                background-color: #1e1e1e;
            }
            QTabBar::tab {
                background-color: #252525;
                color: #b0b0b0;
                border: 1px solid #3a3a3a;
                padding: 6px 12px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #1e1e1e;
                color: #e0e0e0;
                border-bottom-color: #1e1e1e;
            }
            QTabBar::tab:hover {
                background-color: #303030;
            }
            QGroupBox {
                color: #c0c0c0;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QStatusBar {
                background-color: #252525;
                color: #b0b0b0;
                border-top: 1px solid #3a3a3a;
            }
            QSplitter::handle {
                background-color: #3a3a3a;
            }
            QScrollBar:vertical {
                background-color: #1e1e1e;
                width: 12px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background-color: #4a4a4a;
                border-radius: 4px;
                min-height: 20px;
                margin: 2px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #5a5a5a;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
            QScrollBar:horizontal {
                background-color: #1e1e1e;
                height: 12px;
                border: none;
            }
            QScrollBar::handle:horizontal {
                background-color: #4a4a4a;
                border-radius: 4px;
                min-width: 20px;
                margin: 2px;
            }
            QScrollBar::handle:horizontal:hover {
                background-color: #5a5a5a;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0;
            }
            QDockWidget {
                color: #e0e0e0;
                titlebar-close-icon: none;
            }
            QDockWidget::title {
                background-color: #252525;
                border: 1px solid #3a3a3a;
                padding: 4px;
            }
            QLabel {
                color: #e0e0e0;
            }
            QSpinBox {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: 1px solid #3a3a3a;
                border-radius: 3px;
                padding: 2px;
            }
            QToolTip {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: 1px solid #4a4a4a;
                padding: 4px;
            }
        """)

    def _apply_solarized_dark_theme(self, app):
        """Apply Solarized Dark theme."""
        palette = QPalette()
        # Solarized Dark colors
        palette.setColor(QPalette.Window, QColor(0, 43, 54))        # base03
        palette.setColor(QPalette.WindowText, QColor(131, 148, 150)) # base0
        palette.setColor(QPalette.Base, QColor(7, 54, 66))          # base02
        palette.setColor(QPalette.AlternateBase, QColor(0, 43, 54))  # base03
        palette.setColor(QPalette.ToolTipBase, QColor(7, 54, 66))
        palette.setColor(QPalette.ToolTipText, QColor(131, 148, 150))
        palette.setColor(QPalette.Text, QColor(147, 161, 161))       # base1
        palette.setColor(QPalette.Button, QColor(7, 54, 66))
        palette.setColor(QPalette.ButtonText, QColor(131, 148, 150))
        palette.setColor(QPalette.BrightText, QColor(220, 50, 47))   # red
        palette.setColor(QPalette.Link, QColor(38, 139, 210))        # blue
        palette.setColor(QPalette.Highlight, QColor(42, 161, 152))   # cyan
        palette.setColor(QPalette.HighlightedText, QColor(253, 246, 227)) # base3
        app.setPalette(palette)

    def _apply_nord_theme(self, app):
        """Apply Nord theme."""
        palette = QPalette()
        # Nord colors
        palette.setColor(QPalette.Window, QColor(46, 52, 64))        # nord0
        palette.setColor(QPalette.WindowText, QColor(216, 222, 233)) # nord4
        palette.setColor(QPalette.Base, QColor(59, 66, 82))          # nord1
        palette.setColor(QPalette.AlternateBase, QColor(67, 76, 94)) # nord2
        palette.setColor(QPalette.ToolTipBase, QColor(67, 76, 94))
        palette.setColor(QPalette.ToolTipText, QColor(216, 222, 233))
        palette.setColor(QPalette.Text, QColor(229, 233, 240))       # nord5
        palette.setColor(QPalette.Button, QColor(67, 76, 94))
        palette.setColor(QPalette.ButtonText, QColor(216, 222, 233))
        palette.setColor(QPalette.BrightText, QColor(191, 97, 106))  # nord11
        palette.setColor(QPalette.Link, QColor(136, 192, 208))       # nord8
        palette.setColor(QPalette.Highlight, QColor(94, 129, 172))   # nord10
        palette.setColor(QPalette.HighlightedText, QColor(236, 239, 244)) # nord6
        app.setPalette(palette)

    def _apply_monokai_theme(self, app):
        """Apply Monokai theme."""
        palette = QPalette()
        # Monokai colors
        palette.setColor(QPalette.Window, QColor(39, 40, 34))        # background
        palette.setColor(QPalette.WindowText, QColor(248, 248, 242)) # foreground
        palette.setColor(QPalette.Base, QColor(30, 31, 26))          # darker bg
        palette.setColor(QPalette.AlternateBase, QColor(49, 51, 44))
        palette.setColor(QPalette.ToolTipBase, QColor(49, 51, 44))
        palette.setColor(QPalette.ToolTipText, QColor(248, 248, 242))
        palette.setColor(QPalette.Text, QColor(248, 248, 242))
        palette.setColor(QPalette.Button, QColor(49, 51, 44))
        palette.setColor(QPalette.ButtonText, QColor(248, 248, 242))
        palette.setColor(QPalette.BrightText, QColor(249, 38, 114))  # pink
        palette.setColor(QPalette.Link, QColor(102, 217, 239))       # cyan
        palette.setColor(QPalette.Highlight, QColor(73, 72, 62))     # selection
        palette.setColor(QPalette.HighlightedText, QColor(248, 248, 242))
        app.setPalette(palette)

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

    @staticmethod
    def _file_dialog_options():
        """Return file dialog options — use non-native dialog on Windows to avoid hang on cancel."""
        if sys.platform == "win32":
            return QFileDialog.DontUseNativeDialog
        return QFileDialog.Options()

    def _on_open(self):
        if not self._ask_save_changes():
            return
        last_dir = self._app_settings.get_value("last_open_directory", "")
        path, _ = QFileDialog.getOpenFileName(self, self.tr("Open Translation File"), last_dir, _FILE_FILTER, options=self._file_dialog_options())
        QApplication.processEvents()
        if path:
            self._app_settings.set_value("last_open_directory", str(Path(path).parent))
            self._load_file(path)

    def _load_file(self, path: str):
        p = Path(path)
        if not p.exists():
            self._show_toast(self.tr("File not found: %s") % str(p))
            return
        # Reset compile icon to neutral
        if hasattr(self, '_compile_action'):
            style = self.style()
            self._compile_action.setIcon(style.standardIcon(style.StandardPixmap.SP_MediaPlay))
            self._compile_status = None

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
            elif p.suffix == ".sdlxliff":
                self._file_data = parse_sdlxliff(p)
                self._file_type = "sdlxliff"
            elif p.suffix == ".mqxliff":
                self._file_data = parse_mqxliff(p)
                self._file_type = "mqxliff"
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
            elif p.suffix in (".csv", ".tres"):
                self._file_data = parse_godot(p)
                self._file_type = "godot"
            elif p.suffix == ".properties":
                self._file_data = parse_java_properties(p)
                self._file_type = "java_properties"
            elif p.suffix in (".srt", ".vtt"):
                self._file_data = parse_subtitles(p)
                self._file_type = "subtitles"
                # Auto-detect matching video file
                self._check_matching_video(p)
            elif p.name == "messages.json" or p.parent.name == "_locales":
                # Chrome extension i18n (heuristik)
                self._file_data = parse_chrome_i18n(p)
                self._file_type = "chrome_i18n"
            elif p.suffix in (".strings", ".stringsdict"):
                self._file_data = parse_apple_strings(p)
                self._file_type = "apple_strings"
            elif p.suffix == ".asset":
                self._file_data = parse_unity_asset(p)
                self._file_type = "unity_asset"
            elif p.suffix == ".resx":
                self._file_data = parse_resx(p)
                self._file_type = "resx"
            elif p.suffix.lower() in (".mkv", ".mp4", ".avi", ".mov", ".webm", ".flv", ".wmv", ".ogv", ".mpg", ".mpeg", ".m2ts", ".3gp"):
                # Video file — ask to extract subtitles, then show dialog
                reply = QMessageBox.question(
                    self,
                    self.tr("Video file"),
                    self.tr("Would you like to extract subtitles from this video?"),
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes,
                )
                dlg = VideoSubtitleDialog(self)
                dlg.subtitle_extracted.connect(self._load_file)
                dlg.open_video(p)
                if reply == QMessageBox.Yes:
                    dlg.exec()
                else:
                    dlg.show()
                return
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
        
        # Load bookmarks and tags for this file  
        self._load_bookmarks()
        self._load_pinned()
        self._load_tags()
        
        self._populate_list()
        self._update_stats()
        self._modified = False
        self._undo_stacks.clear()
        self._redo_stacks.clear()
        self._lint_cache.clear()
        self._selected_indices.clear()

        # Run linting on all entries at load time
        entries = self._get_entries()
        lint_input = []
        for i, (msgid, msgstr, is_fuzzy) in enumerate(entries):
            flags = ["fuzzy"] if is_fuzzy else []
            lint_input.append({"index": i, "msgid": msgid, "msgstr": msgstr, "flags": flags})
        if lint_input:
            result = lint_entries(lint_input)
            for issue in result.issues:
                self._lint_cache.setdefault(issue.entry_index, []).append(issue)
            self._populate_list()

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
                # Only auto-clear "unfinished" if the fuzzy checkbox is not checked
                if text and entry.translation_type == "unfinished" and not self._fuzzy_check.isChecked():
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
        elif self._file_type in ("sdlxliff", "mqxliff"):
            entry = self._file_data.entries[self._current_index]
            if entry.target != text:
                entry.target = text
                # Only auto-confirm if the fuzzy checkbox is not checked
                if text.strip() and not self._fuzzy_check.isChecked():
                    entry.confirmed = True
                self._modified = True
        elif self._file_type in ("android", "arb", "php", "yaml"):
            entry = self._file_data.entries[self._current_index]
            if entry.value != text:
                entry.value = text
                self._modified = True
        elif self._file_type == "subtitles":
            entry = self._file_data.entries[self._current_index]
            if entry.translation != text:
                entry.translation = text
                # Auto-clear fuzzy when user edits translation
                if entry.fuzzy and not self._fuzzy_check.isChecked():
                    entry.fuzzy = False
                self._modified = True
        elif self._file_type in ("apple_strings", "unity_asset", "resx"):
            entry = self._file_data.entries[self._current_index]
            if entry.msgstr != text:
                entry.msgstr = text
                self._modified = True

    def _on_timestamp_edited(self):
        """Handle timestamp editing for subtitle entries."""
        if self._current_index < 0 or not self._file_data or self._file_type != "subtitles":
            return
        text = self._timestamp_edit.text().strip()
        match = re.match(
            r'(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})',
            text,
        )
        if not match:
            return
        entry = self._file_data.entries[self._current_index]
        # Normalize to dot format for internal storage
        new_start = match.group(1).replace(",", ".")
        new_end = match.group(2).replace(",", ".")
        if entry.start_time != new_start or entry.end_time != new_end:
            entry.start_time = new_start
            entry.end_time = new_end
            self._modified = True
            # Update tree item
            for i in range(self._tree.topLevelItemCount()):
                item = self._tree.topLevelItem(i)
                if item.data(0, Qt.UserRole) == self._current_index:
                    item.setText(2, entry.timestamp)
                    break

    def _on_fuzzy_toggled(self, checked):
        if self._trans_block:
            return
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
        elif self._file_type == "ts":
            entry = self._file_data.entries[self._current_index]
            entry.translation_type = "unfinished" if checked else ""
            self._modified = True
        elif self._file_type == "xliff":
            entry = self._file_data.entries[self._current_index]
            entry.state = "needs-review-translation" if checked else "translated"
            self._modified = True
        elif self._file_type in ("sdlxliff", "mqxliff"):
            entry = self._file_data.entries[self._current_index]
            if checked:
                entry.confirmed = False
                entry.state = "needs-review-translation"
                if hasattr(entry, 'confirmation_level'):
                    entry.confirmation_level = "Draft"
            else:
                entry.confirmed = True
                entry.state = "translated"
                if hasattr(entry, 'confirmation_level'):
                    entry.confirmation_level = "Translated"
            self._modified = True
        elif self._file_type == "subtitles":
            entry = self._file_data.entries[self._current_index]
            entry.fuzzy = checked
            self._modified = True

        # Update the current tree row visually
        current_item = self._tree.currentItem()
        if current_item is not None:
            self._lint_and_update_row(current_item, self._current_index)
        self._update_stats()

    def _on_save(self):
        self._save_current_entry()
        if not self._file_data:
            return

        # First save of extracted video subtitles → ask for filename
        if getattr(self, '_video_extract_suggested_path', None):
            suggested = self._video_extract_suggested_path
            self._video_extract_suggested_path = None
            path, _ = QFileDialog.getSaveFileName(
                self, self.tr("Save Extracted Subtitles"),
                suggested,
                self.tr("SRT files (*.srt);;VTT files (*.vtt);;All files (*)"),
            )
            if not path:
                return
            self._file_data.file_path = Path(path)
            self._file_data.path = Path(path)
            self.setWindowTitle(f"LinguaEdit — {Path(path).name}")
            # Update the tab label too
            idx = self._tab_widget.currentIndex()
            if idx >= 0:
                self._tab_widget.setTabText(idx, Path(path).name)

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
            elif self._file_type == "sdlxliff":
                save_sdlxliff(self._file_data)
            elif self._file_type == "mqxliff":
                save_mqxliff(self._file_data)
            elif self._file_type == "android":
                save_android(self._file_data)
            elif self._file_type == "arb":
                save_arb(self._file_data)
            elif self._file_type == "php":
                save_php(self._file_data)
            elif self._file_type == "yaml":
                save_yaml(self._file_data)
            elif self._file_type == "godot":
                save_godot(self._file_data)
            elif self._file_type == "chrome_i18n":
                save_chrome_i18n(self._file_data)
            elif self._file_type == "java_properties":
                save_java_properties(self._file_data)
            elif self._file_type == "subtitles":
                save_subtitles(self._file_data)
            elif self._file_type == "apple_strings":
                save_apple_strings(self._file_data, self._file_data.file_path)
            elif self._file_type == "unity_asset":
                save_unity_asset(self._file_data, self._file_data.file_path)
            elif self._file_type == "resx":
                save_resx(self._file_data, self._file_data.file_path)
            self._modified = False
            self._show_toast(self.tr("Saved!"))
            self._update_stats()
            self._populate_list()

            # Auto-compile if enabled (Feature 1)
            if self._app_settings.get_value("auto_compile_on_save", False):
                self._on_compile()
                self._show_toast(self.tr("Auto-compiled after save"))
        except Exception as e:
            self._show_toast(self.tr("Save error: %s") % str(e))
        finally:
            if self._file_data:
                self._setup_file_monitor(self._file_data.path)

    def _on_save_as(self):
        """Save current file with a new filename via file dialog."""
        if not self._file_data:
            self._show_toast(self.tr("No file loaded"))
            return
        self._save_current_entry()
        current_path = getattr(self._file_data, 'path', '') or getattr(self._file_data, 'file_path', '')
        suggested_dir = str(Path(current_path).parent) if current_path else ""
        suggested_name = Path(current_path).name if current_path else ""
        filters = self.tr("All files (*)")
        if self._file_type == "po":
            filters = self.tr("PO files (*.po);;All files (*)")
        elif self._file_type == "ts":
            filters = self.tr("TS files (*.ts);;All files (*)")
        elif self._file_type == "xliff":
            filters = self.tr("XLIFF files (*.xlf *.xliff);;All files (*)")
        elif self._file_type == "json":
            filters = self.tr("JSON files (*.json);;All files (*)")
        elif self._file_type == "subtitles":
            filters = self.tr("SRT files (*.srt);;VTT files (*.vtt);;All files (*)")

        new_path, _ = QFileDialog.getSaveFileName(
            self, self.tr("Save As…"), str(Path(suggested_dir) / suggested_name), filters,
            options=QFileDialog.Option.DontUseNativeDialog)
        if not new_path:
            return
        # Update the file path in data object and save
        # Clear video extract flag so _on_save doesn't show another dialog
        self._video_extract_suggested_path = None
        new_path_obj = Path(new_path)
        if hasattr(self._file_data, 'path'):
            self._file_data.path = new_path_obj
        if hasattr(self._file_data, 'file_path'):
            self._file_data.file_path = new_path_obj
        if hasattr(self._file_data, 'fpath'):
            self._file_data.fpath = new_path_obj
        self._on_save()
        self.setWindowTitle(f"LinguaEdit — {Path(new_path).name}")
        self._show_toast(self.tr("Saved as %s") % Path(new_path).name)

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

        # Update progress ring
        if hasattr(self, '_progress_ring'):
            self._progress_ring.set_value(pct, self.tr("translated"))

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

    # ── Smooth fade transition ────────────────────────────────────

    def _play_entry_fade(self):
        """Trigger a quick opacity fade-in on source and translation views."""
        for anim in (self._fade_anim_source, self._fade_anim_trans):
            anim.stop()
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.start()

    # ── Live word / char count ────────────────────────────────────

    def _update_live_word_count(self):
        """Update the statusbar word/char counter from trans_view content."""
        if self._trans_block or self._current_index < 0 or not self._file_data:
            return
        trans_text = self._trans_view.toPlainText()
        trans_words = len(trans_text.split()) if trans_text.strip() else 0
        trans_chars = len(trans_text)

        entries = self._get_entries()
        source_words = 0
        ratio_warning = ""
        if self._current_index < len(entries):
            src = entries[self._current_index][0]
            source_words = len(src.split()) if src.strip() else 0
            if source_words > 0 and trans_words > 0:
                ratio = trans_words / source_words
                if ratio > 2.0:
                    ratio_warning = self.tr(" ⚠ long")
                elif ratio < 0.3:
                    ratio_warning = self.tr(" ⚠ short")

        self._sb_wordcount.setText(
            self.tr("Words: %d | Chars: %d | Source: %dw%s")
            % (trans_words, trans_chars, source_words, ratio_warning)
        )

    # ── Tab management ────────────────────────────────────────────

    def _on_tab_changed(self, index):
        if index >= 0 and index in self._tabs:
            self._restore_tab(self._tabs[index])

    def _on_tab_close(self, index):
        if index < 0:
            return
        # Check for unsaved changes in the tab being closed
        if index in self._tabs:
            td = self._tabs[index]
            # If this is the current tab, check _modified directly
            if index == self._tab_widget.currentIndex():
                if self._modified:
                    if not self._ask_save_changes():
                        return
            elif td.modified:
                ret = QMessageBox.question(
                    self,
                    self.tr("Unsaved Changes"),
                    self.tr("The file '%s' has unsaved changes.\nDo you want to save before closing?") % (
                        Path(td.file_path).name if td.file_path else self.tr("Untitled")
                    ),
                    QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                    QMessageBox.Save,
                )
                if ret == QMessageBox.Cancel:
                    return
                elif ret == QMessageBox.Save:
                    # Switch to that tab, save, then close
                    old_index = self._tab_widget.currentIndex()
                    self._tab_widget.setCurrentIndex(index)
                    self._on_save()
                    self._tab_widget.setCurrentIndex(old_index)
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
            self.setWindowTitle(self.tr("LinguaEdit"))

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

        dialog = ValidationDialog(self, result, self._lint_cache)
        dialog.setModal(False)
        dialog.setAttribute(Qt.WA_DeleteOnClose)
        dialog.show()
        self._validation_dialog = dialog  # prevent GC

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
            msg = self.tr("No inconsistencies found! ✓")
        self._show_dialog(self.tr("Consistency Check"), msg)

    # ── Glossary ──────────────────────────────────────────────────

    def _on_glossary(self):
        terms = get_terms()
        terms_text = "\n".join(f"• {t.source} → {t.target}" for t in terms[:20]) or self.tr("No terms defined")
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
            msg = self.tr("No glossary violations found! ✓")
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

    # ── Generate Report (HTML/PDF) ───────────────────────────────

    def _on_generate_report(self):
        if not self._file_data:
            self._show_toast(self.tr("No file loaded"))
            return
        self._save_current_entry()
        path, _ = QFileDialog.getSaveFileName(
            self, self.tr("Save Report"), "",
            self.tr("HTML (*.html);;PDF (*.pdf)"), options=self._file_dialog_options())
        QApplication.processEvents()
        if not path:
            return
        html = self._build_report_html()
        if path.endswith('.pdf'):
            from PySide6.QtGui import QTextDocument
            from PySide6.QtPrintSupport import QPrinter
            doc = QTextDocument()
            doc.setHtml(html)
            printer = QPrinter(QPrinter.HighResolution)
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setOutputFileName(path)
            doc.print_(printer)
        else:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(html)
        self._show_toast(self.tr("Report saved"))

    def _build_report_html(self) -> str:
        """Build a dark-themed HTML report with quality score, stats, and lint issues."""
        from datetime import datetime

        d = self._file_data
        entries = self._get_entries()
        total = d.total_count
        translated = d.translated_count
        fuzzy = getattr(d, 'fuzzy_count', 0)
        untranslated = d.untranslated_count
        warnings_count = 0

        # Lint
        lint_input = [{"index": i, "msgid": msgid, "msgstr": msgstr,
                       "flags": ["fuzzy"] if is_fuzzy else []}
                      for i, (msgid, msgstr, is_fuzzy) in enumerate(entries)]
        result = lint_entries(lint_input)
        score = result.score
        issues = sorted(result.issues, key=lambda x: {"error": 0, "warning": 1, "info": 2}.get(x.severity, 3))
        warnings_count = len(issues)

        # Category summary
        category_counts: dict[str, int] = {}
        for issue in issues:
            key = issue.message.split(":")[0] if ":" in issue.message else issue.message
            category_counts[key] = category_counts.get(key, 0) + 1

        file_name = html_escape(Path(str(d.path)).name)
        language = html_escape(getattr(d, 'language', '') or getattr(d, 'target_language', '') or self.tr("Unknown"))
        date_str = datetime.now().strftime('%Y-%m-%d %H:%M')
        pct = round(translated / total * 100, 1) if total else 100.0

        # Score gauge color
        if score >= 80:
            gauge_color = "#4caf50"
        elif score >= 50:
            gauge_color = "#ff9800"
        else:
            gauge_color = "#f44336"

        # Issues rows
        issues_rows = ""
        for issue in issues:
            sev = issue.severity
            sev_color = {"error": "#f44336", "warning": "#ff9800"}.get(sev, "#2196f3")
            issues_rows += (
                f'<tr><td style="color:{sev_color};font-weight:600">{html_escape(sev.upper())}</td>'
                f'<td>#{issue.entry_index}</td>'
                f'<td>{html_escape(issue.message)}</td>'
                f'<td>{html_escape((issue.msgid or "")[:80])}</td></tr>\n'
            )

        # Category summary rows
        cat_rows = ""
        for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
            cat_rows += f'<tr><td>{html_escape(cat)}</td><td>{count}</td></tr>\n'

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{self.tr("Translation Report")} — {file_name}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, 'Segoe UI', sans-serif; background: #1e1e2e; color: #cdd6f4; padding: 2em; }}
  .container {{ max-width: 960px; margin: 0 auto; }}
  h1 {{ color: #89b4fa; margin-bottom: 0.3em; font-size: 1.8em; }}
  h2 {{ color: #a6adc8; margin: 1.5em 0 0.5em; font-size: 1.2em; border-bottom: 1px solid #313244; padding-bottom: 0.3em; }}
  .meta {{ color: #6c7086; margin-bottom: 1.5em; }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 1em; margin: 1em 0; }}
  .card {{ background: #313244; border-radius: 12px; padding: 1.2em; text-align: center; }}
  .card .value {{ font-size: 2em; font-weight: 700; }}
  .card .label {{ color: #6c7086; font-size: 0.85em; margin-top: 0.3em; }}
  .gauge-wrap {{ text-align: center; margin: 1.5em 0; }}
  .gauge {{ display: inline-block; width: 120px; height: 120px; border-radius: 50%; border: 8px solid #313244; position: relative; }}
  .gauge-inner {{ position: absolute; inset: 8px; border-radius: 50%; background: #1e1e2e; display: flex; align-items: center; justify-content: center; }}
  .gauge-score {{ font-size: 2.2em; font-weight: 700; color: {gauge_color}; }}
  .progress {{ background: #313244; border-radius: 8px; height: 20px; margin: 0.5em 0 1em; overflow: hidden; display: flex; }}
  .bar-ok {{ background: #4caf50; height: 100%; }}
  .bar-fuzzy {{ background: #ff9800; height: 100%; }}
  .bar-un {{ background: #f44336; height: 100%; }}
  table {{ width: 100%; border-collapse: collapse; margin: 0.5em 0 1.5em; }}
  th {{ background: #313244; color: #a6adc8; text-align: left; padding: 0.6em 0.8em; font-weight: 600; }}
  td {{ padding: 0.5em 0.8em; border-bottom: 1px solid #313244; }}
  tr:hover {{ background: #28283a; }}
  footer {{ color: #45475a; font-size: 0.8em; margin-top: 3em; text-align: center; }}
</style>
</head>
<body>
<div class="container">
<h1>📊 {self.tr("Translation Report")}</h1>
<p class="meta">
  <strong>{self.tr("File")}:</strong> {file_name} &nbsp;|&nbsp;
  <strong>{self.tr("Language")}:</strong> {language} &nbsp;|&nbsp;
  <strong>{self.tr("Date")}:</strong> {date_str}
</p>

<h2>{self.tr("Quality Score")}</h2>
<div class="gauge-wrap">
  <div class="gauge" style="border-color: {gauge_color}">
    <div class="gauge-inner"><span class="gauge-score">{score:.0f}</span></div>
  </div>
</div>

<h2>{self.tr("Statistics")}</h2>
<div class="cards">
  <div class="card"><div class="value">{total}</div><div class="label">{self.tr("Total")}</div></div>
  <div class="card"><div class="value" style="color:#4caf50">{translated}</div><div class="label">{self.tr("Translated")}</div></div>
  <div class="card"><div class="value" style="color:#f44336">{untranslated}</div><div class="label">{self.tr("Untranslated")}</div></div>
  <div class="card"><div class="value" style="color:#ff9800">{fuzzy}</div><div class="label">{self.tr("Fuzzy")}</div></div>
  <div class="card"><div class="value" style="color:#2196f3">{warnings_count}</div><div class="label">{self.tr("Warnings")}</div></div>
</div>
<div class="progress">
  <div class="bar-ok" style="width:{pct}%"></div>
  <div class="bar-fuzzy" style="width:{round(fuzzy / total * 100, 1) if total else 0}%"></div>
  <div class="bar-un" style="width:{round(untranslated / total * 100, 1) if total else 0}%"></div>
</div>

{'<h2>' + self.tr("Issues") + " (" + str(len(issues)) + ')</h2><table><tr><th>' + self.tr("Severity") + '</th><th>' + self.tr("Entry") + '</th><th>' + self.tr("Message") + '</th><th>' + self.tr("Source") + '</th></tr>' + issues_rows + '</table>' if issues else '<p style="color:#a6e3a1">✓ ' + self.tr("No issues found") + '</p>'}

{'<h2>' + self.tr("Summary by Category") + '</h2><table><tr><th>' + self.tr("Category") + '</th><th>' + self.tr("Count") + '</th></tr>' + cat_rows + '</table>' if cat_rows else ''}

<footer>{self.tr("Generated by LinguaEdit")} {__version__}</footer>
</div>
</body>
</html>"""

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
            diff = self.tr("No changes")
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
        anthropic_edit = QLineEdit(getattr(self, "_anthropic_model", "claude-sonnet-4-20260514"))
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
            self._anthropic_model = anthropic_edit.text().strip() or "claude-sonnet-4-20260514"
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

        elif self._file_type in ("sdlxliff", "mqxliff"):
            form = QFormLayout()
            src_edit = QLineEdit(getattr(self._file_data, 'source_language', ''))
            tgt_edit = QLineEdit(getattr(self._file_data, 'target_language', ''))
            fmt_label = QLineEdit("SDLXLIFF (Trados)" if self._file_type == "sdlxliff" else "MQXLIFF (memoQ)")
            fmt_label.setReadOnly(True)
            form.addRow(self.tr("Format:"), fmt_label)
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
            elif self._file_type in ("sdlxliff", "mqxliff"):
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
        path, _ = QFileDialog.getOpenFileName(self, self.tr("Open Reference File"), "", _FILE_FILTER, options=self._file_dialog_options())
        QApplication.processEvents()
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
        from PySide6.QtGui import QPixmap
        msg = QMessageBox(self)
        msg.setWindowTitle(self.tr("About LinguaEdit"))
        msg.setTextFormat(Qt.RichText)
        if self._app_icon_path:
            msg.setIconPixmap(QPixmap(self._app_icon_path).scaled(
                64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        msg.setText(
            f"<h2>LinguaEdit</h2>"
            f"<p>Version {__version__}</p>"
            "<p>" + self.tr("A translation file editor for PO, TS, JSON, XLIFF, "
            "Android, ARB, PHP, and YAML files.") + "</p>"
            "<p>" + self.tr("Developer:") + " Daniel Nylander &lt;po@danielnylander.se&gt;</p>"
            "<p>" + self.tr("License:") + " GPL-3.0-or-later</p>"
            "<p>" + self.tr("Website:") + " <a href='https://www.linguaedit.org'>"
            "www.linguaedit.org</a></p>"
            "<p>© 2026 Daniel Nylander</p>"
        )
        msg.exec()

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

    def _check_matching_video(self, subtitle_path: Path):
        """Check for a video file matching the subtitle filename and offer preview."""
        from linguaedit.services.ffmpeg import SUPPORTED_VIDEO_EXTENSIONS
        stem = subtitle_path.stem
        parent = subtitle_path.parent
        for ext in sorted(SUPPORTED_VIDEO_EXTENSIONS):
            candidate = parent / (stem + ext)
            if candidate.exists():
                self._ensure_video_dock()
                self._video_dock.open_video(candidate)
                self._sync_subtitle_entries_to_video()
                return

    def _on_video_subtitles(self):
        """Open the video subtitle extraction dialog."""
        dlg = VideoSubtitleDialog(self)
        dlg.subtitle_extracted.connect(self._load_file)
        dlg.exec()

    def _ensure_video_dock(self):
        """Create the video dock widget if it doesn't exist yet."""
        if not self._video_dock:
            self._video_dock = VideoDockWidget(self)
            self._video_dock.player.request_prev_segment.connect(lambda: self._navigate(-1))
            self._video_dock.player.request_next_segment.connect(lambda: self._navigate(1))
            self._video_dock.player.request_goto_current_time.connect(self._goto_subtitle_at_time)
            self.addDockWidget(Qt.RightDockWidgetArea, self._video_dock)

    def _goto_subtitle_at_time(self, position_ms: int):
        """Navigate to the subtitle entry matching a playback position."""
        if not self._file_data or self._file_type != "subtitles":
            return
        from linguaedit.ui.video_preview import _parse_time_to_ms
        target_idx = -1
        for i, entry in enumerate(self._file_data.entries):
            start = _parse_time_to_ms(entry.start_time)
            end = _parse_time_to_ms(entry.end_time)
            if start <= position_ms <= end:
                target_idx = i
                break
        if target_idx < 0:
            # Find nearest entry
            best_dist = float('inf')
            for i, entry in enumerate(self._file_data.entries):
                start = _parse_time_to_ms(entry.start_time)
                dist = abs(start - position_ms)
                if dist < best_dist:
                    best_dist = dist
                    target_idx = i
        if target_idx < 0:
            return
        # Find tree item with this orig_idx
        for row in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(row)
            if item and item.data(0, Qt.UserRole) == target_idx:
                self._tree.setCurrentItem(item)
                self._tree.scrollToItem(item)
                return

    def _sync_subtitle_entries_to_video(self):
        """Feed all subtitle entries to the video player for time-synced overlay."""
        if not self._video_dock or not self._file_data or self._file_type != "subtitles":
            return
        from linguaedit.ui.video_preview import _parse_time_to_ms
        entries = []
        for e in self._file_data.entries:
            entries.append((
                _parse_time_to_ms(e.start_time),
                _parse_time_to_ms(e.end_time),
                e.text,
                e.translation or "",
            ))
        self._video_dock.player.set_subtitle_entries(entries)

    def _on_open_video(self):
        """Open a video file — probe subtitle tracks, let user pick, extract."""
        from PySide6.QtWidgets import QFileDialog
        from linguaedit.services.ffmpeg import (
            is_ffmpeg_available, get_subtitle_tracks, get_video_duration,
            extract_subtitle, SUPPORTED_VIDEO_EXTENSIONS,
        )

        if not is_ffmpeg_available():
            from linguaedit.ui.video_subtitle_dialog import FFmpegMissingDialog
            dlg = FFmpegMissingDialog(self)
            if dlg.exec() != QDialog.Accepted:
                return

        path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Open Video"),
            "",
            self.tr("Video files (*.mkv *.mp4 *.avi *.mov *.webm *.flv *.wmv *.ogv);;All files (*)"),
        )
        if not path:
            return

        video_path = Path(path)

        # Show progress while probing
        progress = QProgressDialog(self.tr("Probing video for subtitle tracks…"), self.tr("Cancel"), 0, 0, self)
        progress.setWindowTitle(self.tr("Video"))
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        QApplication.processEvents()

        try:
            tracks = get_subtitle_tracks(video_path)
            duration = get_video_duration(video_path)
        except Exception as e:
            progress.close()
            QMessageBox.critical(self, self.tr("Error"), self.tr("Could not read video file:\n%s") % str(e))
            return
        finally:
            progress.close()

        if not tracks:
            QMessageBox.information(self, self.tr("No Subtitles"), self.tr("No embedded subtitle tracks found in this video file."))
            return

        # Let user pick a track
        track_labels = [t.display_label for t in tracks]
        chosen, ok = QInputDialog.getItem(
            self, self.tr("Select Subtitle Track"),
            self.tr("Found %d subtitle track(s). Select one:") % len(tracks),
            track_labels, 0, False,
        )
        if not ok:
            return
        track = tracks[track_labels.index(chosen)]

        # Extract with progress (threaded so the dialog stays responsive)
        import tempfile
        tmp = tempfile.NamedTemporaryFile(suffix=".srt", delete=False)
        tmp.close()
        output_path = Path(tmp.name)

        progress2 = QProgressDialog(self.tr("Extracting subtitles…"), self.tr("Cancel"), 0, 100, self)
        progress2.setWindowTitle(self.tr("Extracting"))
        progress2.setWindowModality(Qt.WindowModal)
        progress2.setMinimumDuration(0)
        progress2.setValue(0)
        progress2.show()
        QApplication.processEvents()

        loop = __import__('PySide6.QtCore', fromlist=['QEventLoop']).QEventLoop(self)
        extract_ok = [False]
        extract_err = [None]

        # Store worker on self to prevent premature GC (QThread crash)
        self._extract_worker = _SubtitleExtractWorker(video_path, track, output_path, duration, self)
        self._extract_worker.progress.connect(progress2.setValue)
        self._extract_worker.finished.connect(lambda: (extract_ok.__setitem__(0, True), loop.quit()))
        self._extract_worker.error.connect(lambda msg: (extract_err.__setitem__(0, msg), loop.quit()))
        progress2.canceled.connect(self._extract_worker.cancel)
        progress2.canceled.connect(loop.quit)

        self._extract_worker.start()
        loop.exec()
        self._extract_worker.wait()
        # Disconnect signals before dropping reference to avoid dangling connections
        self._extract_worker.progress.disconnect()
        self._extract_worker.finished.disconnect()
        self._extract_worker.error.disconnect()
        self._extract_worker.deleteLater()
        self._extract_worker = None
        progress2.close()

        if extract_err[0]:
            QMessageBox.critical(self, self.tr("Extraction Failed"), extract_err[0])
            return
        if not extract_ok[0]:
            return  # cancelled

        # Bug 2e: If a file is already open, ask to save/close first
        if self._file_data and self._modified:
            answer = QMessageBox.question(
                self, self.tr("Save Current File?"),
                self.tr("A translation file is currently open with unsaved changes.\n"
                         "Save before loading extracted subtitles?"),
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save,
            )
            if answer == QMessageBox.Cancel:
                return
            if answer == QMessageBox.Save:
                self._on_save()
        elif self._file_data:
            answer = QMessageBox.question(
                self, self.tr("Close Current File?"),
                self.tr("Close the current file and load extracted subtitles?"),
                QMessageBox.Yes | QMessageBox.Cancel,
                QMessageBox.Yes,
            )
            if answer == QMessageBox.Cancel:
                return

        # Build a suggested save path: video_name.lang.srt next to the video
        lang_tag = track.language if track.language and track.language != "und" else ""
        stem = video_path.stem
        if lang_tag:
            suggested_name = f"{stem}.{lang_tag}.srt"
        else:
            suggested_name = f"{stem}.srt"
        self._video_extract_suggested_path = str(video_path.parent / suggested_name)

        # Load the extracted subtitle file
        self._load_file(str(output_path))

        # Copy source text to translation and mark as fuzzy (needs review)
        if self._file_data and self._file_type == "subtitles":
            for entry in self._file_data.entries:
                entry.translation = entry.text
                entry.fuzzy = True
            self._modified = True
            self._populate_list()

        # Also open video dock for preview
        self._ensure_video_dock()
        self._video_dock.open_video(video_path)
        self._sync_subtitle_entries_to_video()

    def _update_compile_icon(self, success: bool):
        """Update compile action icon: green check = OK, red X = error."""
        if not hasattr(self, '_compile_action'):
            return
        from PySide6.QtGui import QPixmap, QPainter
        px = QPixmap(32, 32)
        px.fill(QColor(0, 0, 0, 0))
        painter = QPainter(px)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if success:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#2ecc71"))
            painter.drawEllipse(2, 2, 28, 28)
            painter.setPen(QColor("white"))
            font = painter.font()
            font.setPixelSize(20)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, "✓")
        else:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#e74c3c"))
            painter.drawEllipse(2, 2, 28, 28)
            painter.setPen(QColor("white"))
            font = painter.font()
            font.setPixelSize(20)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, "✗")
        painter.end()
        self._compile_action.setIcon(QIcon(px))
        self._compile_status = success

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
                self._update_compile_icon(True)
            except ImportError:
                # Fallback to msgfmt
                if shutil.which("msgfmt"):
                    result = subprocess.run(
                        ["msgfmt", "-o", str(mo_path), str(path)],
                        capture_output=True, text=True
                    )
                    if result.returncode == 0:
                        self._show_toast(self.tr("Compiled: %s") % str(mo_path))
                        self._update_compile_icon(True)
                    else:
                        self._show_toast(self.tr("msgfmt error: %s") % result.stderr.strip())
                        self._update_compile_icon(False)
                else:
                    self._show_toast(self.tr("Cannot compile: install 'polib' or 'gettext' (msgfmt)"))
                    self._update_compile_icon(False)
            except Exception as e:
                self._show_toast(self.tr("Compile error: %s") % str(e))
                self._update_compile_icon(False)

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
                    self._update_compile_icon(True)
                else:
                    self._show_toast(self.tr("lrelease error: %s") % result.stderr.strip())
                    self._update_compile_icon(False)
            except Exception as e:
                self._show_toast(self.tr("Compile error: %s") % str(e))
                self._update_compile_icon(False)
        else:
            self._show_toast(self.tr("Compile not supported for %s files") % self._file_type)
            self._update_compile_icon(False)

    # ── New Features Methods ─────────────────────────────────────

    def _show_search_replace_dialog(self):
        """Show the search and replace dialog."""
        if not self._search_replace_dialog:
            self._search_replace_dialog = SearchReplaceDialog(self)
            self._search_replace_dialog.highlight_requested.connect(self._handle_search_highlight)
            self._search_replace_dialog.replace_requested.connect(self._handle_replace_request)
            
        self._search_replace_dialog.show()
        self._search_replace_dialog.raise_()
        self._search_replace_dialog.focus_find_field()
        
    def _handle_search_highlight(self, pattern: str, case_sensitive: bool, is_regex: bool, scope: str):
        """Handle search highlighting request."""
        # Implement search highlighting in the entry list
        # For now, just apply filter to show matching entries
        if pattern:
            self._search_entry.setText(pattern)
            self._apply_filter()
            
    def _handle_replace_request(self, find_text: str, replace_text: str, case_sensitive: bool, is_regex: bool, scope: str, replace_all: bool):
        """Handle replace request."""
        if not self._file_data:
            return
            
        if replace_all:
            count = 0
            entries = self._get_entries()
            for i, (msgid, msgstr, is_fuzzy) in enumerate(entries):
                if scope == "source" and find_text.lower() in msgid.lower():
                    continue  # Can't replace in source
                elif scope == "translation" or scope == "both":
                    if find_text.lower() in msgstr.lower():
                        new_text = msgstr.replace(find_text, replace_text)
                        self._set_entry_translation(i, new_text)
                        count += 1
                        
            if count > 0:
                self._modified = True
                self._populate_list()
                self._show_toast(self.tr("Replaced in %d entries") % count)
        else:
            # Replace current
            if self._current_index >= 0:
                text = self._trans_view.toPlainText()
                new_text = text.replace(find_text, replace_text, 1)
                if new_text != text:
                    self._trans_view.setPlainText(new_text)

    def _show_batch_edit_dialog(self):
        """Show the batch edit dialog."""
        if not self._file_data:
            self._show_toast(self.tr("No file loaded"))
            return
            
        # Prepare entries for batch editing
        entries = []
        for i, (msgid, msgstr, is_fuzzy) in enumerate(self._get_entries()):
            entries.append({
                "index": i,
                "msgid": msgid,
                "msgstr": msgstr,
                "is_fuzzy": is_fuzzy
            })
            
        dialog = BatchEditDialog(self, entries)
        dialog.apply_changes.connect(self._apply_batch_changes)
        dialog.exec()
        
    def _apply_batch_changes(self, modified_entries):
        """Apply batch changes to entries."""
        for entry in modified_entries:
            idx = entry["index"]
            
            if "new_msgstr" in entry:
                self._set_entry_translation(idx, entry["new_msgstr"])
                
            if "new_is_fuzzy" in entry:
                self._set_entry_fuzzy(idx, entry["new_is_fuzzy"])
                
        self._modified = True
        self._populate_list()
        self._update_stats()
        self._show_toast(self.tr("Applied changes to %d entries") % len(modified_entries))

    def _show_concordance_dialog(self):
        """Show the concordance search dialog."""
        # Pre-fill with selected text if any
        initial = ""
        if hasattr(self, '_source_view') and self._source_view.textCursor().hasSelection():
            initial = self._source_view.textCursor().selectedText()
        dlg = ConcordanceDialog(
            parent=self,
            initial_query=initial,
            source_lang=self._app_settings.get_value("source_language", ""),
            target_lang=self._app_settings.get_value("target_language", ""),
        )
        dlg.exec()

    def _show_glossary_dialog(self):
        """Show the glossary management dialog.""" 
        dialog = GlossaryDialog(self)
        dialog.glossary_changed.connect(self._on_glossary_changed)
        dialog.exec()
        
    def _on_glossary_changed(self):
        """Handle glossary changes."""
        # Re-run linting to check for new glossary violations
        if self._file_data:
            entries = self._get_entries()
            lint_input = []
            for i, (msgid, msgstr, is_fuzzy) in enumerate(entries):
                flags = ["fuzzy"] if is_fuzzy else []
                lint_input.append({"index": i, "msgid": msgid, "msgstr": msgstr, "flags": flags})
            if lint_input:
                result = lint_entries(lint_input)
                self._lint_cache.clear()
                for issue in result.issues:
                    self._lint_cache.setdefault(issue.entry_index, []).append(issue)
                self._populate_list()

    def _show_statistics_dialog(self):
        """Show the statistics dialog."""
        if not self._file_data:
            self._show_toast(self.tr("No file loaded"))
            return
            
        # Prepare entries for statistics
        entries = []
        for i, (msgid, msgstr, is_fuzzy) in enumerate(self._get_entries()):
            entries.append({
                "msgid": msgid,
                "msgstr": msgstr,
                "is_fuzzy": is_fuzzy
            })
            
        file_name = Path(str(self._file_data.path)).name if self._file_data else ""
        dialog = StatisticsDialog(self, entries, file_name)
        dialog.exec()

    def _show_header_dialog(self):
        """Show the header editor dialog."""
        if not self._file_data:
            self._show_toast(self.tr("No file loaded"))
            return
            
        dialog = HeaderDialog(self, self._file_type, self._file_data)
        if dialog.exec() == QDialog.Accepted:
            self._modified = True
            self._show_toast(self.tr("Header updated"))

    def _show_diff_dialog(self):
        """Show the file comparison dialog."""
        dialog = DiffDialog(self)
        dialog.exec()

    def _show_git_diff_dialog(self):
        """Compare current file with a previous git commit."""
        if not self._file_data:
            self._show_toast(self.tr("No file loaded"))
            return
        entries = self._get_entries()
        dialog = GitDiffDialog(
            self,
            file_path=str(self._file_data.path),
            file_type=self._file_type,
            current_entries=entries,
        )
        dialog.exec()

    def _show_dashboard(self):
        """Show the project dashboard."""
        if not self._file_data:
            self._show_toast(self.tr("No file loaded"))
            return
        # Gather all open tabs as "languages"
        project_files = []
        for tab_idx, td in self._tabs.items():
            if td.file_data:
                label = Path(td.file_path).name if td.file_path else f"Tab {tab_idx}"
                # Temporarily get entries from this tab
                old_data, old_type = self._file_data, self._file_type
                self._file_data, self._file_type = td.file_data, td.file_type
                entries = self._get_entries()
                self._file_data, self._file_type = old_data, old_type
                project_files.append((label, entries))
        if not project_files:
            # Just use current file
            entries = self._get_entries()
            name = Path(str(self._file_data.path)).name
            project_files = [(name, entries)]
        dialog = DashboardDialog(self, project_files=project_files)
        dialog.exec()

    def _show_batch_translate_dialog(self):
        """Show the batch machine translate dialog."""
        if not self._file_data:
            self._show_toast(self.tr("No file loaded"))
            return
        entries = self._get_entries()
        extra = self._build_engine_kwargs()
        dialog = BatchTranslateDialog(
            self,
            entries=entries,
            default_engine=self._trans_engine,
            source_lang=self._trans_source,
            target_lang=self._trans_target,
            extra_kwargs=extra,
        )
        dialog.translations_accepted.connect(self._apply_batch_translations)
        dialog.exec()

    def _apply_batch_translations(self, results: list):
        """Apply batch translation results: [(index, text, mark_fuzzy), ...]."""
        for idx, text, mark_fuzzy in results:
            self._set_entry_translation(idx, text)
            if mark_fuzzy:
                self._set_entry_fuzzy(idx, True)
        self._modified = True
        self._populate_list()
        self._update_stats()
        self._show_toast(self.tr("%d translations applied") % len(results))

    def _show_project_dock(self):
        """Show or create the project dock widget."""
        if not self._project_dock:
            self._project_dock = ProjectDockWidget(self)
            self._project_dock.file_open_requested.connect(self._load_file)
            self.addDockWidget(Qt.LeftDockWidgetArea, self._project_dock)
        else:
            self._project_dock.show()
            self._project_dock.raise_()

    # ── Enhanced report with bilingual export ────────────────────

    def _on_generate_report(self):
        """Generate translation report with bilingual option."""
        if not self._file_data:
            self._show_toast(self.tr("No file loaded"))
            return

        from PySide6.QtWidgets import QCheckBox, QVBoxLayout, QDialog, QDialogButtonBox, QGroupBox
        
        # Custom dialog for report options
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr("Generate Report"))
        dialog.setMinimumSize(300, 200)
        
        layout = QVBoxLayout(dialog)
        
        options_group = QGroupBox(self.tr("Report Options"))
        options_layout = QVBoxLayout(options_group)
        
        bilingual_cb = QCheckBox(self.tr("Bilingual export (source + translation)"))
        options_layout.addWidget(bilingual_cb)
        
        include_fuzzy_cb = QCheckBox(self.tr("Include fuzzy entries"))
        include_fuzzy_cb.setChecked(True)
        options_layout.addWidget(include_fuzzy_cb)
        
        layout.addWidget(options_group)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        if dialog.exec() != QDialog.Accepted:
            return
            
        # Generate report
        entries = self._get_entries()
        bilingual = bilingual_cb.isChecked()
        include_fuzzy = include_fuzzy_cb.isChecked()
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Save Report"),
            f"{Path(str(self._file_data.path)).stem}_report.html",
            self.tr("HTML files (*.html);;PDF files (*.pdf)")
        , options=self._file_dialog_options())
        QApplication.processEvents()
        
        if not file_path:
            return
            
        try:
            self._generate_custom_report(entries, file_path, bilingual, include_fuzzy)
            self._show_toast(self.tr("Report saved: %s") % file_path)
        except Exception as e:
            self._show_toast(self.tr("Report error: %s") % str(e))

    def _generate_custom_report(self, entries, file_path: str, bilingual: bool, include_fuzzy: bool):
        """Generate custom HTML report."""
        html_content = []
        html_content.append("<!DOCTYPE html>")
        html_content.append("<html><head>")
        html_content.append("<meta charset='utf-8'>")
        html_content.append("<title>Translation Report</title>")
        html_content.append("<style>")
        html_content.append("body { font-family: Arial, sans-serif; margin: 20px; }")
        html_content.append("table { border-collapse: collapse; width: 100%; }")
        html_content.append("th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }")
        html_content.append("th { background-color: #f2f2f2; }")
        html_content.append(".fuzzy { background-color: #fff3cd; }")
        html_content.append(".untranslated { background-color: #f8d7da; }")
        html_content.append(".translated { background-color: #d4edda; }")
        html_content.append("</style>")
        html_content.append("</head><body>")
        
        # Header
        file_name = Path(str(self._file_data.path)).name if self._file_data else "Unknown"
        html_content.append(f"<h1>Translation Report: {file_name}</h1>")
        
        # Statistics
        total = len(entries)
        translated = sum(1 for _, msgstr, is_fuzzy in entries if msgstr and not is_fuzzy)
        fuzzy = sum(1 for _, _, is_fuzzy in entries if is_fuzzy)
        untranslated = total - translated - fuzzy
        
        html_content.append("<h2>" + self.tr("Statistics") + "</h2>")
        html_content.append("<p>" + self.tr("Total entries:") + f" {total}</p>")
        html_content.append("<p>" + self.tr("Translated:") + f" {translated} ({translated/total*100:.1f}%)</p>")
        html_content.append("<p>" + self.tr("Fuzzy:") + f" {fuzzy} ({fuzzy/total*100:.1f}%)</p>")
        html_content.append("<p>" + self.tr("Untranslated:") + f" {untranslated} ({untranslated/total*100:.1f}%)</p>")
        
        # Table
        html_content.append("<h2>Entries</h2>")
        html_content.append("<table>")
        
        if bilingual:
            html_content.append("<tr><th>#</th><th>Source</th><th>Translation</th><th>Status</th></tr>")
        else:
            html_content.append("<tr><th>#</th><th>Text</th><th>Status</th></tr>")
            
        for i, (msgid, msgstr, is_fuzzy) in enumerate(entries):
            if not include_fuzzy and is_fuzzy:
                continue
                
            # Determine status and CSS class
            if not msgstr:
                status = "Untranslated"
                css_class = "untranslated"
            elif is_fuzzy:
                status = "Fuzzy"
                css_class = "fuzzy"
            else:
                status = "Translated"
                css_class = "translated"
                
            html_content.append(f"<tr class='{css_class}'>")
            html_content.append(f"<td>{i+1}</td>")
            
            if bilingual:
                # Escape HTML
                source_html = msgid.replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br>')
                translation_html = msgstr.replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br>')
                html_content.append(f"<td>{source_html}</td>")
                html_content.append(f"<td>{translation_html}</td>")
            else:
                text_html = (msgstr or msgid).replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br>')
                html_content.append(f"<td>{text_html}</td>")
                
            html_content.append(f"<td>{status}</td>")
            html_content.append("</tr>")
            
        html_content.append("</table>")
        html_content.append("</body></html>")
        
        # Write file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(html_content))

    # ── Helpers ───────────────────────────────────────────────────

    def _show_toast(self, message: str):
        self.statusBar().showMessage(message, 3000)

    def _show_dialog(self, title: str, body: str):
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(body)
        msg.exec()

    # ══════════════════════════════════════════════════════════════
    #  NEW FEATURES (0.10.0)
    # ══════════════════════════════════════════════════════════════

    # ── Feature 1: AI Review ─────────────────────────────────────

    def _show_ai_review(self):
        """Visar AI Review dialog för aktuell översättning."""
        if not self._file_data or self._current_index < 0:
            self._show_toast(self.tr("No translation selected"))
            return
        
        entry = self._file_data.entries[self._current_index]
        source = getattr(entry, 'msgid', None) or getattr(entry, 'source', '') or ""
        translation = getattr(entry, 'msgstr', None) or getattr(entry, 'translation', '') or ""
        
        if not source.strip():
            self._show_toast(self.tr("No source text to review"))
            return
        
        dialog = AIReviewDialog(source, translation, self)
        if dialog.exec():
            # Hämta eventuell uppdaterad översättning
            new_translation = dialog.get_translation()
            if new_translation != translation:
                # Uppdatera översättning
                self._update_translation_text(new_translation)
                self._show_toast(self.tr("Translation updated from AI review"))

    # ── Feature 6: Bokmärken ─────────────────────────────────────

    def _toggle_bookmark(self):
        """Togglear bokmärke för aktuell rad."""
        if self._current_index < 0:
            return
        
        if self._current_index in self._bookmarks:
            self._bookmarks.remove(self._current_index)
            self._show_toast(self.tr("Bookmark removed"))
        else:
            self._bookmarks.add(self._current_index)
            self._show_toast(self.tr("Bookmark added"))
        
        self._save_bookmarks()
        self._refresh_tree()

    def _toggle_bookmarked_filter(self):
        """Togglear visning av endast bokmärkta rader."""
        self._show_bookmarked_only = not self._show_bookmarked_only
        
        if self._show_bookmarked_only:
            self._show_toast(self.tr("Showing only bookmarked entries"))
        else:
            self._show_toast(self.tr("Showing all entries"))
        
        self._refresh_tree()

    def _navigate_bookmarks(self, direction: int):
        """Navigerar till nästa/föregående bokmärke."""
        if not self._bookmarks:
            self._show_toast(self.tr("No bookmarks set"))
            return
        
        sorted_bookmarks = sorted(self._bookmarks)
        
        if direction > 0:  # Nästa bokmärke
            next_bookmarks = [b for b in sorted_bookmarks if b > self._current_index]
            if next_bookmarks:
                self._go_to_entry(next_bookmarks[0])
            else:
                self._go_to_entry(sorted_bookmarks[0])  # Wrap around
        else:  # Föregående bokmärke
            prev_bookmarks = [b for b in sorted_bookmarks if b < self._current_index]
            if prev_bookmarks:
                self._go_to_entry(prev_bookmarks[-1])
            else:
                self._go_to_entry(sorted_bookmarks[-1])  # Wrap around

    def _save_bookmarks(self):
        """Sparar bokmärken till fil."""
        if not self._file_data:
            return
        
        try:
            self._bookmarks_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Ladda befintlig data
            bookmarks_data = {}
            if self._bookmarks_file.exists():
                try:
                    bookmarks_data = json.loads(self._bookmarks_file.read_text("utf-8"))
                except (json.JSONDecodeError, OSError):
                    pass
            
            # Uppdatera för aktuell fil
            file_key = str(Path(self._file_data.file_path).resolve())
            bookmarks_data[file_key] = list(self._bookmarks)
            
            # Spara
            self._bookmarks_file.write_text(json.dumps(bookmarks_data, ensure_ascii=False, indent=2), "utf-8")
            
        except Exception as e:
            print(f"Failed to save bookmarks: {e}")

    def _load_bookmarks(self):
        """Laddar bokmärken från fil."""
        if not self._file_data:
            self._bookmarks.clear()
            return
        
        try:
            if not self._bookmarks_file.exists():
                self._bookmarks.clear()
                return
            
            bookmarks_data = json.loads(self._bookmarks_file.read_text("utf-8"))
            file_key = str(Path(self._file_data.file_path).resolve())
            
            self._bookmarks = set(bookmarks_data.get(file_key, []))
            
        except Exception as e:
            print(f"Failed to load bookmarks: {e}")
            self._bookmarks.clear()
    
    # ── Feature 11: Pinned Entries ──────────────────────────────
    
    def _toggle_pin(self):
        """Toggle pin status för aktuell entry."""
        if self._current_index < 0 or not self._file_data:
            return
        
        if self._current_index in self._pinned_entries:
            self._pinned_entries.remove(self._current_index)
            self._show_toast(self.tr("Entry unpinned"))
        else:
            self._pinned_entries.add(self._current_index)
            self._show_toast(self.tr("Entry pinned"))
        
        self._save_pinned()
        self._populate_list()
    
    def _toggle_pinned_first(self):
        """Toggle om pinnade entries ska visas först."""
        self._show_pinned_first = not self._show_pinned_first
        
        if self._show_pinned_first:
            self._show_toast(self.tr("Showing pinned entries first"))
        else:
            self._show_toast(self.tr("Normal sorting order"))
        
        self._populate_list()
    
    def _save_pinned(self):
        """Sparar pinnade entries till fil."""
        if not self._file_data:
            return
            
        try:
            self._pinned_file.parent.mkdir(parents=True, exist_ok=True)
            file_key = str(Path(self._file_data.path).resolve()) if hasattr(self._file_data, 'path') else str(self._file_data.file_path)
            
            # Ladda befintlig data
            pinned_data = {}
            if self._pinned_file.exists():
                try:
                    pinned_data = json.loads(self._pinned_file.read_text("utf-8"))
                except json.JSONDecodeError:
                    pinned_data = {}
            
            # Uppdatera för denna fil
            pinned_data[file_key] = list(self._pinned_entries)
            
            # Spara
            self._pinned_file.write_text(json.dumps(pinned_data, ensure_ascii=False, indent=2), "utf-8")
            
        except Exception as e:
            print(f"Failed to save pinned: {e}")
    
    def _load_pinned(self):
        """Laddar pinnade entries från fil."""
        if not self._file_data:
            self._pinned_entries.clear()
            return
        
        try:
            if not self._pinned_file.exists():
                self._pinned_entries.clear()
                return
            
            pinned_data = json.loads(self._pinned_file.read_text("utf-8"))
            file_key = str(Path(self._file_data.path).resolve()) if hasattr(self._file_data, 'path') else str(self._file_data.file_path)
            
            self._pinned_entries = set(pinned_data.get(file_key, []))
            
        except Exception as e:
            print(f"Failed to load pinned: {e}")
            self._pinned_entries.clear()
    
    # ── Feature 12: Drag & Drop ─────────────────────────────────
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        """Hantera drag enter event."""
        if event.mimeData().hasUrls():
            # Kolla om det finns translation files
            urls = event.mimeData().urls()
            for url in urls:
                if url.isLocalFile():
                    path = Path(url.toLocalFile())
                    if path.suffix.lower() in {'.po', '.pot', '.ts', '.json', '.xliff', '.xlf', '.xml', 
                                             '.arb', '.php', '.yml', '.yaml', '.csv', '.tres', 
                                             '.properties', '.srt', '.vtt'}:
                        event.acceptProposedAction()
                        return
        event.ignore()
    
    def dropEvent(self, event: QDropEvent):
        """Hantera file drop."""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            for url in urls:
                if url.isLocalFile():
                    file_path = url.toLocalFile()
                    path = Path(file_path)
                    
                    # Validera filtyp
                    if path.suffix.lower() in {'.po', '.pot', '.ts', '.json', '.xliff', '.xlf', '.xml', 
                                             '.arb', '.php', '.yml', '.yaml', '.csv', '.tres', 
                                             '.properties', '.srt', '.vtt'}:
                        try:
                            self._load_file(file_path)
                            self._show_toast(self.tr(f"Loaded: {path.name}"))
                            event.acceptProposedAction()
                            break
                        except Exception as e:
                            self._show_toast(self.tr(f"Error loading {path.name}: {e}"))
                            event.ignore()
                    else:
                        event.ignore()
        else:
            event.ignore()
    
    # ── Feature 13: Quick Actions ───────────────────────────────
    
    def _show_quick_actions(self):
        """Visa quick actions popup."""
        if self._current_index < 0 or not self._file_data:
            return
        
        entries = self._get_entries()
        if self._current_index >= len(entries):
            return
        
        source_text, current_text, _ = entries[self._current_index]
        
        # Få cursor position från translation editor
        cursor_rect = self._trans_view.cursorRect()
        global_pos = self._trans_view.mapToGlobal(cursor_rect.bottomLeft())
        
        # Visa quick actions menu
        if self._quick_actions_menu.show_for_context(source_text, current_text, global_pos):
            self._connect_quick_actions()
    
    def _connect_quick_actions(self):
        """Koppla quick actions signaler."""
        if hasattr(self._quick_actions_menu, '_connected'):
            return
        
        self._quick_actions_menu.copy_source_requested.connect(self._copy_source_to_target)
        self._quick_actions_menu.apply_tm_requested.connect(self._apply_quick_tm)
        self._quick_actions_menu.apply_glossary_requested.connect(self._apply_quick_glossary)
        self._quick_actions_menu.fix_case_requested.connect(self._fix_quick_case)
        self._quick_actions_menu.add_punctuation_requested.connect(self._add_quick_punctuation)
        
        self._quick_actions_menu._connected = True
    
    def _apply_quick_tm(self, text: str):
        """Applicera TM-förslag från quick actions."""
        self._trans_view.setPlainText(text)
        self._fuzzy_check.setChecked(True)
    
    def _apply_quick_glossary(self, text: str):
        """Applicera glossary term från quick actions."""
        current_text = self._trans_view.toPlainText()
        if current_text.strip():
            # Lägg till i slutet
            self._trans_view.setPlainText(current_text + " " + text)
        else:
            # Ersätt tomt fält
            self._trans_view.setPlainText(text)
    
    def _fix_quick_case(self):
        """Fixa case från quick actions."""
        current_text = self._trans_view.toPlainText()
        if not current_text.strip():
            return
        
        entries = self._get_entries()
        if self._current_index >= len(entries):
            return
        
        source_text = entries[self._current_index][0]
        if not source_text.strip():
            return
        
        source_first = source_text.strip()[0]
        if source_first.isalpha():
            if source_first.isupper():
                # Capitalize first letter
                fixed_text = current_text[0].upper() + current_text[1:]
            else:
                # Lowercase first letter  
                fixed_text = current_text[0].lower() + current_text[1:]
            
            self._trans_view.setPlainText(fixed_text)
    
    def _add_quick_punctuation(self, punct: str):
        """Lägg till interpunktion från quick actions."""
        current_text = self._trans_view.toPlainText()
        self._trans_view.setPlainText(current_text + punct)
    
    # ── Feature 15: Watch Mode ──────────────────────────────────
    
    def _toggle_watch_mode(self):
        """Toggle file watching mode."""
        if self._watch_mode_enabled:
            self._disable_watch_mode()
        else:
            self._enable_watch_mode()
    
    def _enable_watch_mode(self):
        """Enable file watching."""
        if not self._file_data or not hasattr(self._file_data, 'path'):
            self._show_toast(self.tr("No file loaded"))
            return
        
        if self._file_watcher is None:
            self._file_watcher = QFileSystemWatcher(self)
            self._file_watcher.fileChanged.connect(self._on_file_changed)
        
        file_path = str(self._file_data.path)
        if file_path not in self._file_watcher.files():
            self._file_watcher.addPath(file_path)
        
        self._watch_mode_enabled = True
        self._show_toast(self.tr("Watch mode enabled - file changes will be detected"))
    
    def _disable_watch_mode(self):
        """Disable file watching."""
        if self._file_watcher:
            self._file_watcher.removePaths(self._file_watcher.files())
        
        self._watch_mode_enabled = False
        self._show_toast(self.tr("Watch mode disabled"))
    
    def _on_file_changed(self, path: str):
        """Hantera när fil ändras externt."""
        if not self._file_data or str(self._file_data.path) != path:
            return
        
        # Kolla om auto-reload är aktiverat
        auto_reload = getattr(self._app_settings, 'auto_reload_on_change', False)
        
        if auto_reload:
            self._reload_current_file()
            self._show_toast(self.tr("File reloaded (external change detected)"))
        else:
            # Visa dialog
            reply = QMessageBox.question(
                self, 
                self.tr("File Changed"),
                self.tr("The file has been changed externally. Reload?"),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            
            if reply == QMessageBox.Yes:
                self._reload_current_file()
    
    def _setup_file_monitor(self, file_path: Path):
        """Setup file monitoring för en fil."""
        if self._watch_mode_enabled:
            if self._file_watcher is None:
                self._file_watcher = QFileSystemWatcher(self)
                self._file_watcher.fileChanged.connect(self._on_file_changed)
            
            # Remove old paths and add new one
            self._file_watcher.removePaths(self._file_watcher.files())
            self._file_watcher.addPath(str(file_path))

    # ── Feature 7: Taggar/Filter ─────────────────────────────────

    def _add_tag(self):
        """Lägger till tagg för aktuell rad."""
        if self._current_index < 0:
            return
        
        from PySide6.QtWidgets import QInputDialog
        
        # Fördefinierade taggar
        predefined_tags = ["UI", "error", "tooltip", "menu", "dialog", "help"]
        existing_tags = self._tags.get(self._current_index, [])
        
        # Visa input dialog
        tag, ok = QInputDialog.getItem(
            self, self.tr("Add Tag"), 
            self.tr("Select or enter tag:"),
            predefined_tags, editable=True
        )
        
        if ok and tag.strip():
            tag = tag.strip()
            if self._current_index not in self._tags:
                self._tags[self._current_index] = []
            
            if tag not in self._tags[self._current_index]:
                self._tags[self._current_index].append(tag)
                self._save_tags()
                self._refresh_tree()
                self._show_toast(self.tr(f"Tag '{tag}' added"))

    def _remove_tag(self, tag: str):
        """Tar bort tagg från aktuell rad."""
        if self._current_index < 0 or self._current_index not in self._tags:
            return
        
        if tag in self._tags[self._current_index]:
            self._tags[self._current_index].remove(tag)
            if not self._tags[self._current_index]:
                del self._tags[self._current_index]
            
            self._save_tags()
            self._refresh_tree()
            self._show_toast(self.tr(f"Tag '{tag}' removed"))

    def _filter_by_tag(self, tag: str):
        """Filtrerar listan baserat på tagg."""
        if self._active_tag_filter == tag:
            self._active_tag_filter = None
            self._show_toast(self.tr("Tag filter removed"))
        else:
            self._active_tag_filter = tag
            self._show_toast(self.tr(f"Filtering by tag: {tag}"))
        
        self._refresh_tree()

    def _save_tags(self):
        """Sparar taggar till fil."""
        if not self._file_data:
            return
        
        try:
            self._tags_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Ladda befintlig data
            tags_data = {}
            if self._tags_file.exists():
                try:
                    tags_data = json.loads(self._tags_file.read_text("utf-8"))
                except (json.JSONDecodeError, OSError):
                    pass
            
            # Uppdatera för aktuell fil
            file_key = str(Path(self._file_data.file_path).resolve())
            tags_data[file_key] = {str(k): v for k, v in self._tags.items()}
            
            # Spara
            self._tags_file.write_text(json.dumps(tags_data, ensure_ascii=False, indent=2), "utf-8")
            
        except Exception as e:
            print(f"Failed to save tags: {e}")

    def _load_tags(self):
        """Laddar taggar från fil."""
        if not self._file_data:
            self._tags.clear()
            return
        
        try:
            if not self._tags_file.exists():
                self._tags.clear()
                return
            
            tags_data = json.loads(self._tags_file.read_text("utf-8"))
            file_key = str(Path(self._file_data.file_path).resolve())
            
            raw_tags = tags_data.get(file_key, {})
            self._tags = {int(k): v for k, v in raw_tags.items()}
            
        except Exception as e:
            print(f"Failed to load tags: {e}")
            self._tags.clear()

    # ── Feature 8: Review Mode ───────────────────────────────────

    def _toggle_review_mode(self):
        """Togglear review mode."""
        self._review_mode = not self._review_mode
        
        if self._review_mode:
            self._show_toast(self.tr("Review mode enabled"))
        else:
            self._show_toast(self.tr("Review mode disabled"))
        
        self._refresh_tree()
        self._update_editor_for_review_mode()

    def _update_editor_for_review_mode(self):
        """Uppdaterar editorn för review mode."""
        if not hasattr(self, '_trans_view'):
            return
        
        # Här skulle vi lägga till review-knappar i editorn
        # För nu, bara en enkel implementering
        pass

    def _set_review_status(self, status: str, comment: str = ""):
        """Sätter review-status för aktuell rad."""
        if self._current_index < 0:
            return
        
        self._review_status[self._current_index] = status
        if comment:
            self._review_comments[self._current_index] = comment
        
        self._refresh_tree()
        self._show_toast(self.tr(f"Status set to: {status}"))

    # ── Feature 9: Email Translation ─────────────────────────────

    def _email_translation(self):
        """Skickar översättning via e-post."""
        if not self._file_data:
            self._show_toast(self.tr("No file loaded"))
            return
        
        from PySide6.QtWidgets import QDialog, QFormLayout, QLineEdit, QTextEdit, QCheckBox
        
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr("Email Translation"))
        dialog.setModal(True)
        dialog.resize(400, 300)
        
        layout = QFormLayout(dialog)
        
        # To
        to_edit = QLineEdit()
        # Auto-fill med TP robot om det är en PO-fil
        if hasattr(self._file_data, 'headers'):
            language = self._file_data.headers.get('Language', '')
            if language:
                to_edit.setText(f"{language}@translationproject.org")
        layout.addRow(self.tr("To:"), to_edit)
        
        # Subject
        subject_edit = QLineEdit()
        filename = Path(self._file_data.file_path).name
        subject_edit.setText(f"Translation: {filename}")
        layout.addRow(self.tr("Subject:"), subject_edit)
        
        # Body
        body_edit = QTextEdit()
        body_edit.setPlainText(f"Please find attached the translation file: {filename}")
        layout.addRow(self.tr("Message:"), body_edit)
        
        # Attach current file
        attach_check = QCheckBox(self.tr("Attach current file"))
        attach_check.setChecked(True)
        layout.addWidget(attach_check)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        if dialog.exec():
            # Öppna e-postklient via mailto: URL
            import urllib.parse
            
            to = to_edit.text().strip()
            subject = subject_edit.text().strip() 
            body = body_edit.toPlainText().strip()
            
            if to:
                mailto_url = f"mailto:{to}?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"
                QDesktopServices.openUrl(QUrl(mailto_url))
                self._show_toast(self.tr("Email client opened"))
            else:
                self._show_toast(self.tr("Please enter recipient email"))

    # ── Feature 13: Focus Mode ───────────────────────────────────

    def _toggle_focus_mode(self):
        """Togglear focus mode."""
        self._focus_mode = not self._focus_mode
        
        if self._focus_mode:
            self._show_toast(self.tr("Focus mode enabled - hiding completed translations"))
        else:
            self._show_toast(self.tr("Focus mode disabled"))
        
        self._refresh_tree()
        self._update_progress_for_focus()

    def _update_progress_for_focus(self):
        """Uppdaterar progressbar för focus mode."""
        if not self._file_data or not self._focus_mode:
            return
        
        # Räkna återstående strängar i focus mode
        remaining = 0
        total = len(self._file_data.entries)
        
        for entry in self._file_data.entries:
            if not entry.msgstr or 'fuzzy' in (entry.flags or []):
                remaining += 1
        
        if hasattr(self, '_stats_label'):
            self._stats_label.setText(self.tr(f"{remaining}/{total} remaining"))

    # ── Utility methods ──────────────────────────────────────────

    def _update_translation_text(self, text: str):
        """Uppdaterar översättningstext (helper method)."""
        if hasattr(self, '_trans_view'):
            self._trans_view.setPlainText(text)
            # Trigga save
            self._on_trans_buffer_changed()

    def _go_to_entry(self, index: int):
        """Navigerar till specifik entry (helper method)."""
        if 0 <= index < len(self._file_data.entries):
            # Hitta motsvarande tree item
            for i in range(self._tree.topLevelItemCount()):
                item = self._tree.topLevelItem(i)
                if item and item.data(0, Qt.UserRole) == index:
                    self._tree.setCurrentItem(item)
                    break

    def _show_tree_context_menu(self, position):
        """Visar context menu för tree widget."""
        item = self._tree.itemAt(position)
        if not item:
            return
        
        index = item.data(0, Qt.UserRole)
        if index is None:
            return
        
        menu = QMenu(self)
        
        # Bokmärke
        if index in self._bookmarks:
            menu.addAction(self.tr("Remove Bookmark"), lambda: self._toggle_bookmark())
        else:
            menu.addAction(self.tr("Add Bookmark"), lambda: self._toggle_bookmark())
        
        # Pin entry
        if index in self._pinned_entries:
            menu.addAction(self.tr("📌 Unpin Entry"), lambda: self._toggle_pin())
        else:
            menu.addAction(self.tr("📌 Pin Entry"), lambda: self._toggle_pin())
        
        menu.addSeparator()
        
        # Taggar
        tag_menu = menu.addMenu(self.tr("Tags"))
        
        # Befintliga taggar för denna entry
        current_tags = self._tags.get(index, [])
        if current_tags:
            for tag in current_tags:
                action = tag_menu.addAction(f"✓ {tag}")
                action.triggered.connect(lambda checked, t=tag: self._remove_tag(t))
        
        tag_menu.addSeparator()
        tag_menu.addAction(self.tr("Add Tag..."), self._add_tag)
        
        # Review status (om review mode är aktivt)
        if self._review_mode:
            menu.addSeparator()
            review_menu = menu.addMenu(self.tr("Review"))
            
            review_menu.addAction(self.tr("Approve"), 
                                lambda: self._set_review_status("approved"))
            review_menu.addAction(self.tr("Reject"), 
                                lambda: self._set_review_status("rejected"))
            review_menu.addAction(self.tr("Needs Review"), 
                                lambda: self._set_review_status("needs_review"))
        
        menu.exec(self._tree.mapToGlobal(position))
    
    def _update_preview(self):
        """Uppdaterar preview panel med aktuell översättning."""
        if not hasattr(self, '_preview_label') or self._current_index < 0:
            return
        
        if not self._file_data:
            self._preview_label.setText(self.tr("No file loaded"))
            return
        
        entry = self._file_data.entries[self._current_index]
        source = entry.msgid or "" if hasattr(entry, 'msgid') else getattr(entry, 'source', "")
        translation = entry.msgstr or "" if hasattr(entry, 'msgstr') else getattr(entry, 'translation', "")
        
        if not translation:
            self._preview_label.setText(self.tr("No translation to preview"))
            return
        
        max_width = self._preview_width_spin.value()
        
        # Enkla beräkningar för text-rendering
        char_width = 8  # Ungefärlig bredd per tecken
        chars_per_line = max_width // char_width
        
        # Simulera radbrytning
        words = translation.split()
        lines = []
        current_line = ""
        
        for word in words:
            if len(current_line + " " + word) <= chars_per_line:
                current_line += (" " if current_line else "") + word
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        
        if current_line:
            lines.append(current_line)
        
        preview_text = "\n".join(lines)
        
        # Kontrollera längd jämfört med källa
        source_length = len(source)
        trans_length = len(translation)
        
        if source_length > 0:
            ratio = trans_length / source_length
            if ratio > 1.5:
                warning = f"\n\n⚠️ Warning: Translation is {ratio:.1f}x longer than source"
                preview_text += warning
        
        # Kontrollera HTML-innehåll
        if "<" in translation and ">" in translation:
            preview_text += f"\n\nHTML detected: {translation}"
        
        self._preview_label.setText(preview_text)
    
    # ══════════════════════════════════════════════════════════════
    # NEW FEATURES IMPLEMENTATION
    # ══════════════════════════════════════════════════════════════
    
    # Feature 2: Plugin Management
    def _show_plugin_dialog(self):
        """Show plugin management dialog."""
        dialog = PluginDialog(self)
        dialog.exec()
    
    # Feature 3: TMX Import/Export
    def _on_import_tmx(self):
        """Import TMX file into translation memory."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, self.tr("Import TMX"), "", self.tr("TMX Files (*.tmx)")
        , options=self._file_dialog_options())
        QApplication.processEvents()
        
        if not file_path:
            return
        
        try:
            from pathlib import Path
            imported_count, errors = TMXService.import_from_tmx(Path(file_path))
            
            message = self.tr("Imported {} translation units").format(imported_count)
            if errors:
                message += self.tr("\n\nErrors:\n{}").format("\n".join(errors))
            
            QMessageBox.information(self, self.tr("TMX Import"), message)
            
        except Exception as e:
            QMessageBox.critical(
                self, self.tr("Import Error"),
                self.tr("Failed to import TMX file: {}").format(str(e))
            )
    
    def _on_export_tmx(self):
        """Export translation memory to TMX file."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, self.tr("Export TMX"), "translation_memory.tmx",
            self.tr("TMX Files (*.tmx)")
        , options=self._file_dialog_options())
        QApplication.processEvents()
        
        if not file_path:
            return
        
        try:
            from pathlib import Path
            source_lang = self._app_settings.get("source_language", "en")
            target_lang = self._app_settings.get("target_language", "sv")
            
            exported_count = TMXService.export_to_tmx(
                Path(file_path), source_lang, target_lang
            )
            
            QMessageBox.information(
                self, self.tr("TMX Export"),
                self.tr("Exported {} translation units to {}").format(
                    exported_count, file_path
                )
            )
            
        except Exception as e:
            QMessageBox.critical(
                self, self.tr("Export Error"),
                self.tr("Failed to export TMX file: {}").format(str(e))
            )
    
    # Feature 4: Segmentation
    def _on_split_entry(self):
        """Split the current entry using an interactive dialog."""
        if self._current_index < 0 or not self._file_data:
            return

        entry = self._file_data.entries[self._current_index]
        source = entry.msgid if hasattr(entry, 'msgid') else getattr(entry, 'text', getattr(entry, 'source', ''))
        target = entry.msgstr if hasattr(entry, 'msgstr') else getattr(entry, 'translation', '')

        if not source.strip():
            self._show_toast(self.tr("Cannot split empty entry"))
            return

        dlg = SplitDialog(source, target, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return

        result = dlg.get_result()
        if result is None:
            return

        (src1, tgt1), (src2, tgt2) = result
        idx = self._current_index

        # Update the current entry with first segment
        if hasattr(entry, 'msgid'):
            entry.msgid = src1
            entry.msgstr = tgt1
        else:
            entry.source = src1
            entry.translation = tgt1

        # Create a new entry for the second segment and insert after current
        new_entry = type(entry)()
        if hasattr(new_entry, 'msgid'):
            new_entry.msgid = src2
            new_entry.msgstr = tgt2
            if hasattr(new_entry, 'fuzzy'):
                new_entry.fuzzy = True
        else:
            new_entry.source = src2
            new_entry.translation = tgt2

        self._file_data.entries.insert(idx + 1, new_entry)

        self._modified = True
        self._populate_list()
        self._show_toast(self.tr("Entry split into 2 segments"))
    
    def _on_merge_entries(self):
        """Merge selected entries into one with a preview dialog."""
        selected_indices = list(self._selected_indices)
        if len(selected_indices) < 2:
            self._show_toast(self.tr("Select at least 2 entries to merge"))
            return

        selected_indices.sort()

        # Collect entries to merge
        entries_to_merge = []
        for idx in selected_indices:
            if idx < len(self._file_data.entries):
                entry = self._file_data.entries[idx]
                source = entry.msgid if hasattr(entry, 'msgid') else getattr(entry, 'text', getattr(entry, 'source', ''))
                target = entry.msgstr if hasattr(entry, 'msgstr') else getattr(entry, 'translation', '')
                entries_to_merge.append((source, target))

        if len(entries_to_merge) < 2:
            return

        # Show preview dialog
        dlg = MergePreviewDialog(entries_to_merge, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return

        merged_source, merged_target = dlg.get_result()

        # Update first entry
        first_idx = selected_indices[0]
        first_entry = self._file_data.entries[first_idx]
        if hasattr(first_entry, 'msgid'):
            first_entry.msgid = merged_source
            first_entry.msgstr = merged_target
        else:
            first_entry.source = merged_source
            first_entry.translation = merged_target

        # Remove other entries (in reverse order)
        for idx in reversed(selected_indices[1:]):
            del self._file_data.entries[idx]

        self._modified = True
        self._selected_indices.clear()
        self._populate_list()
        self._show_toast(self.tr("Merged {} entries").format(len(selected_indices)))
    
    # Feature 6: Inline Editing (requires QStyledItemDelegate)
    def _enable_inline_editing(self, enabled: bool):
        """Enable or disable inline editing in the entry table."""
        # This would require implementing a custom QStyledItemDelegate
        # For now, just store the setting
        self._inline_editing_enabled = enabled
    
    # Feature 7: Character Counter
    def _setup_character_counter(self):
        """Setup character counter widget."""
        if not hasattr(self, '_char_count_widget') or self._char_count_widget is None:
            self._char_count_widget = QLabel()
            self._char_count_widget.setStyleSheet("padding: 2px 4px; font-size: 10pt;")
            self.statusBar().addPermanentWidget(self._char_count_widget)
    
    def _update_character_count(self):
        """Update character counter display."""
        if not hasattr(self, '_char_count_widget') or self._char_count_widget is None:
            return
        
        if self._current_index < 0 or not self._file_data:
            self._char_count_widget.setText("")
            return
        
        entry = self._file_data.entries[self._current_index]
        source = entry.msgid if hasattr(entry, 'msgid') else getattr(entry, 'text', getattr(entry, 'source', ''))
        target = entry.msgstr if hasattr(entry, 'msgstr') else getattr(entry, 'translation', '')
        
        char_count = len(target)
        word_count = len(target.split()) if target else 0
        source_chars = len(source) if source else 0
        
        text = self.tr("{} chars | {} words | Source: {} chars").format(
            char_count, word_count, source_chars
        )
        
        # Check limit
        if char_count > self._char_count_limit:
            text = f"⚠️ {text}"
            self._char_count_widget.setStyleSheet("color: red; padding: 2px 4px; font-weight: bold;")
        else:
            self._char_count_widget.setStyleSheet("color: gray; padding: 2px 4px;")
        
        self._char_count_widget.setText(text)
    
    # Feature 8: Unicode Inspector
    def _show_unicode_inspector(self):
        """Show Unicode inspector dialog."""
        text = ""
        if self._current_index >= 0 and self._file_data:
            entry = self._file_data.entries[self._current_index]
            text = entry.msgstr if hasattr(entry, 'msgstr') else getattr(entry, 'translation', '')
        
        dialog = UnicodeDialog(text, self)
        dialog.exec()
    
    # Feature 9: Burndown Chart (part of statistics dialog)
    def _get_progress_data_for_chart(self):
        """Get progress data for burndown chart."""
        # This would integrate with the history service to get daily progress
        return self._history_manager.get_statistics().get("daily_changes", [])
    
    # Feature 10: Achievements
    def _show_achievements_dialog(self):
        """Show achievements dialog."""
        dialog = AchievementsDialog(self)
        dialog.exec()
    
    def _record_translation_achievement(self):
        """Record a translation for achievement tracking."""
        if not self._file_data:
            return
        
        # Determine language and format
        language = self._app_settings.get("target_language", "sv")
        format_type = self._file_type or "unknown"
        
        # Check if this was a manual translation (not auto-translated)
        is_manual = True  # Could be determined by checking if auto-translate was used
        
        self._achievement_manager.record_translation(language, format_type, is_manual)
    
    # Feature 11: Git Integration
    def _on_git_commit_dialog(self):
        """Show git commit dialog."""
        if not self._file_data:
            self._show_toast(self.tr("No file loaded"))
            return
        
        # Simple commit dialog
        message, ok = QInputDialog.getMultiLineText(
            self, self.tr("Git Commit"),
            self.tr("Commit message:"),
            self.tr("Updated {} translation").format(
                self._app_settings.get("target_language", "")
            )
        )
        
        if not ok or not message.strip():
            return
        
        try:
            import subprocess
            from pathlib import Path
            
            file_dir = Path(self._file_data.path).parent
            
            # Add current file
            subprocess.run(
                ["git", "add", str(self._file_data.path)],
                cwd=file_dir, check=True
            )
            
            # Commit
            subprocess.run(
                ["git", "commit", "-m", message.strip()],
                cwd=file_dir, check=True
            )
            
            # Ask about push
            reply = QMessageBox.question(
                self, self.tr("Push Changes"),
                self.tr("Commit successful. Push to remote?"),
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
            )
            
            if reply == QMessageBox.Yes:
                subprocess.run(
                    ["git", "push"],
                    cwd=file_dir, check=True
                )
                self._show_toast(self.tr("Changes pushed successfully"))
            else:
                self._show_toast(self.tr("Changes committed locally"))
            
        except subprocess.CalledProcessError as e:
            QMessageBox.warning(
                self, self.tr("Git Error"),
                self.tr("Git operation failed: {}").format(str(e))
            )
        except Exception as e:
            QMessageBox.critical(
                self, self.tr("Error"),
                self.tr("Git operation error: {}").format(str(e))
            )
    
    # Feature 12: TTS Preview
    def _setup_tts_button(self):
        """Setup TTS preview button in editor."""
        if hasattr(self, '_trans_edit') and self._trans_edit:
            # Add TTS button to editor layout
            tts_btn = QPushButton("🔊")
            tts_btn.setMaximumSize(30, 30)
            tts_btn.setToolTip(self.tr("Play Translation"))
            tts_btn.clicked.connect(self._play_tts)
            
            # Would need to add to editor layout
    
    def _play_tts(self):
        """Play TTS for current translation."""
        if self._current_index < 0 or not self._file_data:
            return
        
        entry = self._file_data.entries[self._current_index]
        text = entry.msgstr if hasattr(entry, 'msgstr') else getattr(entry, 'translation', '')
        
        if not text.strip():
            self._show_toast(self.tr("No text to play"))
            return
        
        try:
            import subprocess
            import sys
            import platform
            
            # Stop any existing TTS
            if self._tts_process and self._tts_process.poll() is None:
                self._tts_process.terminate()
            
            # Use system TTS
            if platform.system() == "Darwin":  # macOS
                self._tts_process = subprocess.Popen(
                    ["say", text],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            elif platform.system() == "Linux":
                # Try espeak
                self._tts_process = subprocess.Popen(
                    ["espeak", text],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            elif platform.system() == "Windows":
                # Use PowerShell
                ps_command = f'Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak("{text}")'
                self._tts_process = subprocess.Popen(
                    ["powershell", "-Command", ps_command],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            
            self._show_toast(self.tr("Playing translation..."))
            
        except Exception as e:
            QMessageBox.warning(
                self, self.tr("TTS Error"),
                self.tr("Text-to-speech failed: {}").format(str(e))
            )
    
    # ══════════════════════════════════════════════════════════════
    #  SPLIT VIEW (side-by-side source/translation)
    # ══════════════════════════════════════════════════════════════

    def _toggle_split_view(self):
        """Toggle between vertical (stacked) and horizontal (side-by-side) editor layout."""
        self._horizontal_split = not self._horizontal_split
        self._app_settings.set_value("horizontal_split", self._horizontal_split)
        self._app_settings.save()
        self._apply_split_orientation()

    def _apply_split_orientation(self):
        """Apply current split orientation to editor area."""
        if self._horizontal_split:
            # Side-by-side: source left, translation right
            self._v_splitter.setOrientation(Qt.Horizontal)
            self._source_view.setMaximumHeight(16777215)  # Remove height limit
            self._split_view_action.setText(self.tr("Stacked View"))
        else:
            # Stacked: source on top, translation below (default)
            self._v_splitter.setOrientation(Qt.Vertical)
            self._source_view.setMaximumHeight(90)
            self._split_view_action.setText(self.tr("Side-by-Side View"))

    # ══════════════════════════════════════════════════════════════
    #  STICKY CONTEXT PANEL
    # ══════════════════════════════════════════════════════════════

    def _toggle_context_panel(self):
        """Toggle the Context Panel dock widget."""
        if self._context_panel is None:
            self._context_panel = ContextPanel(self)
            self._context_panel.set_engine_settings(
                self._trans_engine, self._trans_source, self._trans_target
            )
            self._context_panel.apply_tm_requested.connect(self._apply_tm_match)
            self._context_panel.apply_mt_requested.connect(self._apply_tm_match)
            self._context_panel.apply_glossary_requested.connect(
                lambda t: self._trans_view.insertPlainText(t)
            )
            self.addDockWidget(Qt.RightDockWidgetArea, self._context_panel)
            # Populate with current entry
            if self._current_index >= 0:
                entries = self._get_entries()
                if self._current_index < len(entries):
                    self._context_panel.update_for_entry(entries[self._current_index][0])
        else:
            visible = self._context_panel.isVisible()
            self._context_panel.setVisible(not visible)

    def _update_context_panel(self, source_text: str):
        """Update context panel if it exists and is visible."""
        if self._context_panel and self._context_panel.isVisible():
            self._context_panel.set_engine_settings(
                self._trans_engine, self._trans_source, self._trans_target
            )
            self._context_panel.update_for_entry(source_text)

    # ══════════════════════════════════════════════════════════════
    #  QUICK ACTIONS TOOLBAR HELPERS
    # ══════════════════════════════════════════════════════════════

    def _qa_apply_best_tm(self):
        """Apply the best TM match from the context panel."""
        if self._context_panel:
            text = self._context_panel.get_best_tm_target()
            if text:
                self._trans_view.setPlainText(text)
                self._fuzzy_check.setChecked(True)
                return
        # Fallback: use existing TM lookup
        if self._current_index >= 0 and self._file_data:
            entries = self._get_entries()
            if self._current_index < len(entries):
                matches = lookup_tm(entries[self._current_index][0], threshold=0.6, max_results=1)
                if matches:
                    self._trans_view.setPlainText(matches[0].target)
                    self._fuzzy_check.setChecked(True)

    def _qa_apply_mt(self):
        """Apply the MT suggestion from the context panel.
        
        Machine-translated entries are always marked fuzzy until
        the user manually clears the flag.
        """
        text = None
        if self._context_panel:
            text = self._context_panel.get_mt_text()
        if not text and self._current_index >= 0 and self._file_data:
            entries = self._get_entries()
            if self._current_index < len(entries):
                try:
                    text = translate(
                        entries[self._current_index][0],
                        engine=self._trans_engine,
                        source=self._trans_source,
                        target=self._trans_target,
                    )
                except Exception:
                    self._show_toast(self.tr("MT translation failed"))
                    return
        if text:
            self._trans_view.setPlainText(text)
            # Always mark machine-translated entries as fuzzy
            self._fuzzy_check.setChecked(True)

    def _update_quick_toolbar_state(self):
        """Enable/disable quick toolbar buttons based on current context."""
        has_entry = self._current_index >= 0 and self._file_data is not None
        self._qa_copy_src_btn.setEnabled(has_entry)
        self._qa_mark_reviewed_btn.setEnabled(has_entry)
        self._qa_toggle_fuzzy_btn.setEnabled(has_entry)

        # TM button: enabled if context panel has a TM match
        has_tm = False
        if self._context_panel and self._context_panel.get_best_tm_target():
            has_tm = True
        elif has_entry:
            entries = self._get_entries()
            if self._current_index < len(entries):
                matches = lookup_tm(entries[self._current_index][0], threshold=0.6, max_results=1)
                has_tm = bool(matches)
        self._qa_apply_tm_btn.setEnabled(has_tm)

        # MT button: enabled if context panel has MT or entry exists
        has_mt = False
        if self._context_panel and self._context_panel.get_mt_text():
            has_mt = True
        elif has_entry:
            has_mt = True  # Can always attempt MT
        self._qa_apply_mt_btn.setEnabled(has_mt)

    # Feature 13: Fullscreen Mode
    def _toggle_fullscreen(self):
        """Toggle fullscreen mode."""
        if self._is_fullscreen:
            self._exit_fullscreen()
        else:
            self._enter_fullscreen()
    
    def _enter_fullscreen(self):
        """Enter fullscreen mode."""
        if self._is_fullscreen:
            return
        
        # Store current state
        self._pre_fullscreen_state = {
            'menu_visible': not self.menuBar().isHidden(),
            'toolbar_visible': self._toolbar.isVisible() if hasattr(self, '_toolbar') else True,
            'statusbar_visible': not self.statusBar().isHidden(),
            'geometry': self.geometry()
        }
        
        # Hide UI elements
        self.menuBar().hide()
        if hasattr(self, '_toolbar'):
            self._toolbar.hide()
        self.statusBar().hide()
        
        # Hide docks
        for dock in self.findChildren(QDockWidget):
            if dock.isVisible():
                dock.hide()
        
        # Enter fullscreen
        self.showFullScreen()
        self._is_fullscreen = True
        
        self._show_toast(self.tr("Fullscreen mode - Press Escape to exit"))
    
    def _exit_fullscreen(self):
        """Exit fullscreen mode."""
        if not self._is_fullscreen:
            return
        
        # Exit fullscreen
        self.showNormal()
        
        # Restore UI elements
        if self._pre_fullscreen_state:
            if self._pre_fullscreen_state['menu_visible']:
                self.menuBar().show()
            
            if self._pre_fullscreen_state['toolbar_visible'] and hasattr(self, '_toolbar'):
                self._toolbar.show()
            
            if self._pre_fullscreen_state['statusbar_visible']:
                self.statusBar().show()
            
            # Restore geometry
            self.setGeometry(self._pre_fullscreen_state['geometry'])
        
        self._is_fullscreen = False
        self._pre_fullscreen_state = None
    
    def _on_escape_pressed(self):
        """Handle Escape: exit zen mode first, then fullscreen."""
        if self._zen_mode_active:
            self._exit_zen_mode()
            return
        if self._is_fullscreen:
            self._exit_fullscreen()

    def _exit_fullscreen_if_active(self):
        """Exit fullscreen if currently in fullscreen mode."""
        if self._is_fullscreen:
            self._exit_fullscreen()
    
    # Feature 14: Macros
    def _show_macro_dialog(self):
        """Show macro management dialog."""
        dialog = MacroDialog(self)
        dialog.exec()
    
    def _on_record_macro(self):
        """Start recording a macro."""
        if self._macro_manager.is_recording:
            self._show_toast(self.tr("Already recording a macro"))
            return
        
        # Get macro name
        name, ok = QInputDialog.getText(
            self, self.tr("Record Macro"),
            self.tr("Enter macro name:")
        )
        
        if not ok or not name.strip():
            return
        
        name = name.strip()
        if self._macro_manager.get_macro(name):
            QMessageBox.warning(
                self, self.tr("Macro Exists"),
                self.tr("A macro with this name already exists.")
            )
            return
        
        # Start recording
        self._macro_manager.start_recording()
        self._recording_macro_name = name
        self._show_toast(self.tr("Recording macro '{}'...").format(name))
    
    def _on_play_macro(self):
        """Show macro selection and play."""
        macros = self._macro_manager.get_all_macros()
        if not macros:
            self._show_toast(self.tr("No macros available"))
            return
        
        macro_names = [name for name, macro in macros.items() if macro.enabled]
        if not macro_names:
            self._show_toast(self.tr("No enabled macros"))
            return
        
        name, ok = QInputDialog.getItem(
            self, self.tr("Play Macro"),
            self.tr("Select macro to play:"),
            macro_names, 0, False
        )
        
        if ok and name:
            success = self._macro_manager.play_macro(name, self)
            if not success:
                self._show_toast(self.tr("Failed to play macro"))
    
    def _record_macro_action(self, action_type: MacroActionType, **parameters):
        """Record an action for macro recording."""
        if self._macro_manager.is_recording:
            self._macro_manager.recorder.record_action(action_type, **parameters)
    
    # Translation History Integration
    def _save_entry_with_history(self, entry_index: int, old_value: str, new_value: str, field: str = "target"):
        """Save entry change to history."""
        if not self._file_data:
            return
        
        # Record history
        self._history_manager.add_change(
            str(self._file_data.path), 
            entry_index, 
            field, 
            old_value, 
            new_value,
            self._app_settings.get("translator_name", "")
        )
        
        # Record achievement
        if field == "target" and new_value.strip() and not old_value.strip():
            self._record_translation_achievement()
    
    def _show_translation_history(self):
        """Show translation history for current entry."""
        if self._current_index < 0 or not self._file_data:
            return
        
        dialog = HistoryDialog(str(self._file_data.path), self._current_index, self)
        dialog.rollback_requested.connect(self._rollback_translation)
        dialog.exec()
    
    def _rollback_translation(self, old_value: str):
        """Rollback translation to previous value."""
        if self._current_index < 0 or not self._file_data:
            return
        
        entry = self._file_data.entries[self._current_index]
        if hasattr(entry, 'msgstr'):
            entry.msgstr = old_value
        else:
            entry.translation = old_value
        
        self._modified = True
        self._update_translation_text(old_value)
        self._show_toast(self.tr("Translation rolled back"))
    
    # Enhanced Compile with Auto-compile
    def _on_compile_enhanced(self):
        """Enhanced compile that also handles auto-compile setting."""
        self._on_compile()
        
        # Check if we should auto-compile
        if self._app_settings.get("auto_compile_on_save", False):
            self._show_toast(self.tr("Auto-compile enabled"))
    
    # Plugin Integration
    def _run_plugin_lint(self, source: str, target: str) -> list:
        """Run linting through plugins."""
        return self._plugin_manager.lint_with_plugins(source, target)
    
    def _get_plugin_suggestions(self, source: str, lang: str) -> list:
        """Get suggestions from plugins."""
        return self._plugin_manager.get_suggestions_from_plugins(source, lang)
    
    # Context Menu Enhancement
    def _show_enhanced_context_menu(self, position):
        """Enhanced context menu with new features."""
        # Call original context menu
        self._show_tree_context_menu(position)
        
        # Add separator and new items to the menu that was created
        current_row = self._tree.currentItem()
        if current_row:
            menu = QMenu(self)
            
            # Feature 5: Translation History
            if self._history_manager.has_history(str(self._file_data.path), self._current_index):
                menu.addAction(self.tr("Translation History…"), self._show_translation_history)
            
            # Feature 12: TTS
            menu.addAction(self.tr("🔊 Play Translation"), self._play_tts)
            
            menu.exec(self._tree.mapToGlobal(position))

    # ── New Features Implementation ──────────────────────────────────────────

    def _show_regex_tester(self):
        """Show Regex Tester dialog."""
        current_text = ""
        if hasattr(self, '_translation_editor') and self._translation_editor:
            current_text = self._translation_editor.toPlainText()
        
        dialog = RegexTesterDialog(self, current_text)
        dialog.exec()

    def _show_layout_simulator(self):
        """Show Layout Simulator dialog."""
        source_text = ""
        target_text = ""
        
        # Get current entry texts
        if self._current_index >= 0 and self._file_data:
            entries = self._get_entries()
            if self._current_index < len(entries):
                source_text = entries[self._current_index][0]
                target_text = entries[self._current_index][1]
        
        dialog = LayoutSimulatorDialog(self, source_text, target_text)
        dialog.exec()

    def _show_locale_map_dialog(self):
        """Show Locale Map dialog."""
        project_path = ""
        if hasattr(self, '_current_file') and self._current_file:
            project_path = str(Path(self._current_file).parent)
        
        dialog = LocaleMapDialog(self, project_path)
        dialog.exec()

    def _show_ocr_dialog(self):
        """Show OCR dialog."""
        dialog = OCRDialog(self)
        dialog.strings_extracted.connect(self._on_ocr_strings_extracted)
        dialog.exec()

    def _on_ocr_strings_extracted(self, strings: list):
        """Handle extracted strings from OCR."""
        if strings:
            # Could open the created PO file or show a notification
            self._show_toast(self.tr("OCR extraction completed. {} strings extracted.").format(len(strings)))

    def _crowdin_pull_latest(self):
        """Pull latest translations from Crowdin OTA."""
        QMessageBox.information(
            self, 
            self.tr("Crowdin OTA"),
            self.tr("Crowdin Over-The-Air functionality not yet implemented.\n"
                   "This would pull latest translations using distribution hash.")
        )

    def _msgmerge_with_pot(self):
        """Merge current PO file with POT file using msgmerge."""
        if not hasattr(self, '_current_file') or not self._current_file:
            QMessageBox.warning(self, self.tr("No File"), self.tr("Please open a PO file first."))
            return
        
        if not self._current_file.endswith('.po'):
            QMessageBox.warning(self, self.tr("Wrong File Type"), self.tr("This feature only works with PO files."))
            return
        
        # Browse for POT file
        pot_file, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Select POT File"),
            str(Path(self._current_file).parent),
            self.tr("POT Files (*.pot)")
        , options=self._file_dialog_options())
        QApplication.processEvents()
        
        if not pot_file:
            return
        
        try:
            # Run msgmerge
            import subprocess
            cmd = ["msgmerge", "--update", self._current_file, pot_file]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                QMessageBox.information(
                    self, 
                    self.tr("Success"),
                    self.tr("PO file merged successfully with POT file.\nPlease reload the file to see changes.")
                )
                # Reload the file
                self._reload_current_file()
            else:
                QMessageBox.warning(
                    self,
                    self.tr("Msgmerge Error"),
                    self.tr("msgmerge failed:\n{}").format(result.stderr or result.stdout)
                )
                
        except FileNotFoundError:
            QMessageBox.warning(
                self,
                self.tr("Msgmerge Not Found"),
                self.tr("msgmerge command not found. Please install gettext tools.")
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                self.tr("Error"),
                self.tr("Failed to run msgmerge:\n{}").format(str(e))
            )

    def _reload_current_file(self):
        """Reload the current file."""
        if hasattr(self, '_current_file') and self._current_file:
            self._load_file(self._current_file)
    
    # ── Feature 10: Minimap ──────────────────────────────────────
    
    def _toggle_minimap(self):
        """Toggle minimap visibility."""
        is_visible = self._minimap.isVisible()
        self._minimap.setVisible(not is_visible)
        
        if not is_visible:
            self._update_minimap()
    
    def _update_minimap(self):
        """Update minimap with current entries."""
        if not hasattr(self, '_minimap'):
            return
            
        entries = self._get_entries()
        self._minimap.set_entries(entries)
        self._minimap.set_current_index(self._current_index)
    
    def _on_minimap_jump(self, entry_index: int):
        """Jump to entry from minimap click."""
        entries = self._get_entries()
        if 0 <= entry_index < len(entries):
            self._select_entry(entry_index)

    # ══════════════════════════════════════════════════════════════
    #  UX IMPROVEMENTS
    # ══════════════════════════════════════════════════════════════

    # ── 1. Alternative horizontal layout ─────────────────────────

    def _toggle_editor_layout(self):
        """Switch between vertical (editor below) and horizontal (editor right) layout."""
        self._editor_on_right = not self._editor_on_right
        self._app_settings.set_value("editor_on_right", self._editor_on_right)
        self._apply_editor_layout()
        label = self.tr("Editor Below") if self._editor_on_right else self.tr("Editor on Right")
        self._layout_toggle_action.setText(label)

    def _apply_editor_layout(self):
        """Apply the current layout preference."""
        # Remove widgets from current splitter
        # We need to re-parent them
        if self._editor_on_right:
            self._v_splitter.setOrientation(Qt.Horizontal)
            self._v_splitter.setSizes([450, 550])
        else:
            self._v_splitter.setOrientation(Qt.Vertical)
            self._v_splitter.setSizes([400, 350])

    # ── 2. Zen Translation Mode ──────────────────────────────────

    def _toggle_simple_mode(self):
        """Toggle Simple Mode — a clean, minimal translation interface.

        Hides sidebar, toolbar, status bar, context panel, minimap,
        and other non-essential UI. Shows only the file list, source/target
        editor, and glossary/TM panels.
        """
        self._simple_mode = not self._simple_mode
        self._simple_mode_action.setChecked(self._simple_mode)
        hide = self._simple_mode

        # Hide sidebar
        self._sidebar.setVisible(not hide)

        # Hide status bar extras (keep progress)
        if hasattr(self, '_sb_fuzzy'):
            self._sb_fuzzy.setVisible(not hide)

        # Hide context dock if shown
        if self._context_dock:
            self._context_dock.setVisible(not hide)

        # Hide preview dock
        if self._preview_dock:
            self._preview_dock.setVisible(not hide)

        # Hide minimap
        if hasattr(self, '_minimap_widget') and self._minimap_widget:
            self._minimap_widget.setVisible(not hide)

        # Hide quick actions toolbar
        if hasattr(self, '_quick_actions_toolbar') and self._quick_actions_toolbar:
            self._quick_actions_toolbar.setVisible(not hide)

        # Simplify tree columns — hide bookmark, tags in simple mode
        header = self._tree.header()
        if hide:
            header.hideSection(1)  # bookmark
            header.hideSection(4)  # tags
        else:
            header.showSection(1)
            header.showSection(4)

        mode_name = self.tr("Simple Mode") if hide else self.tr("Normal Mode")
        self._show_toast(mode_name)

    def _toggle_zen_mode(self):
        """Enter or exit Zen translation mode."""
        if self._zen_mode_active:
            self._exit_zen_mode()
        else:
            self._enter_zen_mode()

    def _enter_zen_mode(self):
        if not self._file_data:
            self._show_toast(self.tr("No file loaded"))
            return

        self._zen_mode_active = True

        # Create zen widget
        self._zen_widget = ZenModeWidget(self)
        self._zen_widget.exit_requested.connect(self._exit_zen_mode)
        self._zen_widget.save_and_next.connect(self._zen_save_and_next_untranslated)
        self._zen_widget.save_and_next_entry.connect(self._zen_save_and_next)
        self._zen_widget.save_and_prev_entry.connect(self._zen_save_and_prev)
        self._zen_widget.entry_changed.connect(self._zen_on_text_changed)

        # Hide normal UI elements
        self.menuBar().setVisible(False)
        self._toolbar = self.findChild(QToolBar)
        if self._toolbar:
            self._toolbar.setVisible(False)
        self.statusBar().setVisible(False)
        self._sidebar.setVisible(False)
        self._outer_splitter.setVisible(False)
        self._tab_widget.setVisible(False)

        # Add zen widget to central layout
        central_layout = self.centralWidget().layout()
        central_layout.addWidget(self._zen_widget, 1)

        # Load current entry
        self._zen_load_current_entry()

    def _exit_zen_mode(self):
        if not self._zen_mode_active:
            return
        self._zen_mode_active = False

        # Save current zen translation
        if self._zen_widget and self._file_data and self._current_index >= 0:
            self._trans_view.setPlainText(self._zen_widget.get_translation())
            self._save_current_entry()

        # Remove zen widget
        if self._zen_widget:
            self._zen_widget.setParent(None)
            self._zen_widget.deleteLater()
            self._zen_widget = None

        # Restore UI
        self.menuBar().setVisible(True)
        if self._toolbar:
            self._toolbar.setVisible(True)
        self.statusBar().setVisible(True)
        self._sidebar.setVisible(True)
        self._outer_splitter.setVisible(True)
        self._tab_widget.setVisible(True)

    def _zen_load_current_entry(self):
        if not self._zen_widget or not self._file_data:
            return
        entries = self._get_entries()
        if self._current_index < 0 or self._current_index >= len(entries):
            return
        msgid, msgstr, is_fuzzy = entries[self._current_index]
        total = len(entries)
        translated = sum(1 for _, ms, f in entries if ms and not f)

        if not msgstr:
            status = "untranslated"
        elif is_fuzzy:
            status = "fuzzy"
        else:
            status = "translated"

        self._zen_widget.set_entry(msgid, msgstr, self._current_index, total, translated, status)

    def _zen_save_and_next_untranslated(self):
        if self._zen_widget:
            self._trans_view.setPlainText(self._zen_widget.get_translation())
            self._save_current_entry()
            self._navigate_untranslated(1)
            self._zen_load_current_entry()

    def _zen_save_and_next(self):
        if self._zen_widget:
            self._trans_view.setPlainText(self._zen_widget.get_translation())
            self._save_current_entry()
            self._navigate(1)
            self._zen_load_current_entry()

    def _zen_save_and_prev(self):
        if self._zen_widget:
            self._trans_view.setPlainText(self._zen_widget.get_translation())
            self._save_current_entry()
            self._navigate(-1)
            self._zen_load_current_entry()

    def _zen_on_text_changed(self, text: str):
        """Update the main translation buffer from zen mode edits."""
        pass  # We sync on save, not on every keystroke

    # ── 5. Tab/Enter navigation flow ─────────────────────────────

    def _save_and_flash(self):
        """Save current entry and show a brief green flash."""
        self._save_current_entry()
        self._trans_view.setStyleSheet("QPlainTextEdit { border: 2px solid #4caf50; }")
        self._saved_flash_timer.start()

    def _clear_saved_flash(self):
        self._trans_view.setStyleSheet("")

    def _tab_save_next(self):
        """Tab: save + next entry."""
        self._save_and_flash()
        self._navigate(1)

    def _shift_tab_save_prev(self):
        """Shift+Tab: save + previous entry."""
        self._save_and_flash()
        self._navigate(-1)

    def _ctrl_enter_save_next_untranslated(self):
        """Ctrl+Enter: save + next untranslated."""
        self._save_and_flash()
        self._navigate_untranslated(1)

    # ── 6. Context-aware toolbar ─────────────────────────────────

    def _update_toolbar_visibility(self):
        """Hide quality/tools actions when no file is loaded."""
        has_file = self._file_data is not None
        # The sidebar has quality/tools actions that should be hidden
        for i in range(self._sidebar.layout().count() if self._sidebar.layout() else 0):
            pass  # Sidebar actions are always visible for now

    def _show_toolbar_customizer(self):
        """Show toolbar customization dialog."""
        actions = []
        for action in self._sidebar.actions():
            if action.isSeparator():
                continue
            actions.append({
                "name": action.text(),
                "group": self.tr("Sidebar"),
                "visible": action.isVisible(),
                "action": action,
            })
        dlg = ToolbarCustomizeDialog(actions, self)
        if dlg.exec():
            visibility = dlg.get_visibility()
            for action in self._sidebar.actions():
                if action.text() in visibility:
                    action.setVisible(visibility[action.text()])

    def _on_toolbar_context_menu(self, pos):
        """Show context menu for toolbar customization."""
        menu = QMenu(self)
        menu.addAction(self.tr("Customize Toolbar…"), self._show_toolbar_customizer)
        menu.exec(self._sidebar.mapToGlobal(pos))

    # ── Unsaved changes dialog ────────────────────────────────────

    def _ask_save_changes(self) -> bool:
        """Ask the user to save unsaved changes.

        Returns True if the caller may proceed (saved or discarded),
        False if the user chose Cancel.
        """
        if not self._modified:
            return True
        ret = QMessageBox.question(
            self,
            self.tr("Unsaved Changes"),
            self.tr("The current file has unsaved changes.\nDo you want to save before continuing?"),
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save,
        )
        if ret == QMessageBox.Save:
            self._on_save()
            return True
        elif ret == QMessageBox.Discard:
            return True
        else:  # Cancel
            return False

    def closeEvent(self, event):
        """Prompt to save and persist window geometry before closing."""
        if not self._ask_save_changes():
            event.ignore()
            return
        # Save geometry and splitter state
        settings = QSettings("LinguaEdit", "LinguaEdit")
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState())
        settings.setValue("outerSplitter", self._outer_splitter.saveState())
        settings.setValue("vSplitter", self._v_splitter.saveState())
        super().closeEvent(event)
