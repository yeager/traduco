"""Translation Editor med Autocomplete — Förbättrad translation editor.

Utökar QPlainTextEdit med autocomplete-funktionalitet baserat på
Translation Memory-databasen och andra källor. Includes inline MT
suggestions from DeepL/OpenAI and spell check with red underlines.
"""
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import List, Optional
from PySide6.QtWidgets import (
    QPlainTextEdit, QCompleter, QAbstractItemView, QWidget,
    QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QFrame, QMenu,
    QApplication,
)
from PySide6.QtCore import Qt, Signal, QStringListModel, QTimer, QObject, Slot
from PySide6.QtGui import (
    QKeyEvent, QTextCursor, QTextCharFormat, QColor, QFont,
    QAction, QTextFormat, QPalette,
)

from linguaedit.services.tm import lookup_tm
from linguaedit.services.settings import Settings
from linguaedit.ui.syntax_highlighting import TranslationHighlighter

# i18n helper
def _(s: str) -> str:
    """Mark string for translation."""
    return QApplication.translate("TranslationEditor", s)


# ── MT Suggestion Worker (runs in background thread) ──────────────────

class _MTWorker(QObject):
    """Background worker for fetching MT suggestions."""
    finished = Signal(list)  # list of (engine_name, translation) tuples

    def __init__(self, text: str, source: str, target: str, engines: list[str]):
        super().__init__()
        self._text = text
        self._source = source
        self._target = target
        self._engines = engines

    @Slot()
    def run(self):
        results = []
        for engine in self._engines:
            try:
                from linguaedit.services.translator import translate
                result = translate(self._text, engine=engine,
                                   source=self._source, target=self._target)
                if result and result.strip():
                    from linguaedit.services.translator import ENGINES
                    name = ENGINES.get(engine, {}).get("name", engine)
                    results.append((name, result.strip()))
            except Exception:
                pass
        self.finished.emit(results)


# ── Inline MT Suggestion Popup ────────────────────────────────────────

class MTSuggestionWidget(QFrame):
    """Small popup showing MT suggestions from DeepL/OpenAI."""

    suggestion_accepted = Signal(str)  # emitted when user clicks a suggestion

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("""
            MTSuggestionWidget {
                background: palette(base);
                border: 1px solid palette(mid);
                border-radius: 4px;
                padding: 4px;
            }
            MTSuggestionWidget QLabel {
                color: palette(text);
            }
            QLabel#mt-header {
                font-size: 10px;
                color: palette(light);
                padding: 2px 0;
            }
        """)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(6, 4, 6, 4)
        self._layout.setSpacing(2)

        self._header = QLabel(_("MT Suggestions"))
        self._header.setObjectName("mt-header")
        self._layout.addWidget(self._header)

        self._suggestions_layout = QVBoxLayout()
        self._suggestions_layout.setSpacing(1)
        self._layout.addLayout(self._suggestions_layout)

        self._loading_label = QLabel(_("Loading…"))
        self._loading_label.setStyleSheet("color: palette(light); font-style: italic; font-size: 11px;")
        self._layout.addWidget(self._loading_label)

        self.setVisible(False)
        self.setMaximumHeight(200)

    def show_loading(self):
        self._clear_suggestions()
        self._loading_label.setVisible(True)
        self.setVisible(True)

    def show_suggestions(self, suggestions: list[tuple[str, str]]):
        self._clear_suggestions()
        self._loading_label.setVisible(False)

        if not suggestions:
            lbl = QLabel(_("No suggestions available"))
            lbl.setStyleSheet("color: palette(light); font-style: italic; font-size: 11px;")
            self._suggestions_layout.addWidget(lbl)
        else:
            for engine_name, text in suggestions[:3]:
                row = QHBoxLayout()
                row.setSpacing(4)
                engine_lbl = QLabel(f"<b>{engine_name}:</b>")
                engine_lbl.setStyleSheet("font-size: 10px; color: palette(light);")
                engine_lbl.setFixedWidth(80)
                row.addWidget(engine_lbl)

                text_lbl = QLabel(text[:200])
                text_lbl.setWordWrap(True)
                text_lbl.setStyleSheet("font-size: 11px; color: palette(text);")
                row.addWidget(text_lbl, 1)

                use_btn = QPushButton(_("Use"))
                use_btn.setFixedSize(40, 22)
                use_btn.setStyleSheet("font-size: 10px;")
                captured_text = text
                use_btn.clicked.connect(lambda checked, t=captured_text: self.suggestion_accepted.emit(t))
                row.addWidget(use_btn)

                self._suggestions_layout.addLayout(row)

        self.setVisible(True)

    def _clear_suggestions(self):
        while self._suggestions_layout.count():
            item = self._suggestions_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                while item.layout().count():
                    sub = item.layout().takeAt(0)
                    if sub.widget():
                        sub.widget().deleteLater()


class TranslationEditor(QPlainTextEdit):
    """Utökad translation editor med autocomplete, MT suggestions, and spell check."""

    # Signal för när översättning ändras
    translation_changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._completer: Optional[QCompleter] = None
        self._completion_enabled = True
        self._min_chars_for_completion = 3
        self._completion_timer = QTimer()
        self._completion_timer.setSingleShot(True)
        self._completion_timer.timeout.connect(self._update_completions)

        # MT suggestion state
        self._mt_widget: Optional[MTSuggestionWidget] = None
        self._mt_generation = 0
        self._mt_source_text: str = ""  # current source text for MT
        self._mt_enabled = True

        # Spell check state
        self._spellcheck_enabled = True
        self._spell_language = "en_US"
        self._user_dictionary: set[str] = set()
        self._spell_issues: list = []
        self._spellcheck_timer = QTimer()
        self._spellcheck_timer.setSingleShot(True)
        self._spellcheck_timer.setInterval(500)
        self._spellcheck_timer.timeout.connect(self._run_spellcheck)

        # Setup autocomplete
        self._setup_completer()

        # Setup syntax highlighting (with spell check support)
        self._syntax_highlighter = TranslationHighlighter(self.document())
        self._highlighting_enabled = True

        # Koppla signaler
        self.textChanged.connect(self._on_text_changed)
        self.textChanged.connect(self.translation_changed.emit)
        self.textChanged.connect(self._schedule_spellcheck)

        # Context menu for spell check
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
    
    def _setup_completer(self):
        """Skapar och konfigurerar QCompleter."""
        self._completer = QCompleter(self)
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchContains)
        self._completer.setMaxVisibleItems(10)
        
        # Popup-beteende
        self._completer.setPopup(self._completer.popup())
        self._completer.popup().setStyleSheet("""
            QListView {
                background-color: palette(base);
                border: 1px solid palette(mid);
                selection-background-color: palette(highlight);
                font-size: 11pt;
            }
        """)
        
        # När användaren väljer ett förslag
        self._completer.activated.connect(self._insert_completion)
        
        # Koppla completer till editor
        self._completer.setWidget(self)
    
    def _on_text_changed(self):
        """Hanterar textändringar för autocomplete."""
        if not self._completion_enabled:
            return
        
        # Starta timer för att undvika för många lookups
        self._completion_timer.stop()
        self._completion_timer.start(300)  # 300ms fördröjning
    
    def _update_completions(self):
        """Uppdaterar autocomplete-förslag baserat på aktuell text."""
        if not self._completion_enabled:
            return
        
        cursor = self.textCursor()
        
        # Hitta aktuellt ord
        current_word = self._get_word_under_cursor(cursor)
        
        if len(current_word) < self._min_chars_for_completion:
            self._completer.popup().hide()
            return
        
        # Hämta förslag från Translation Memory
        suggestions = self._get_completion_suggestions(current_word)
        
        if suggestions:
            # Uppdatera completer-modellen
            model = QStringListModel(suggestions)
            self._completer.setModel(model)
            
            # Visa popup vid cursor-position
            rect = self.cursorRect()
            rect.setWidth(300)  # Bredd på popup
            self._completer.complete(rect)
        else:
            self._completer.popup().hide()
    
    def _get_word_under_cursor(self, cursor: QTextCursor) -> str:
        """Hämtar ordet under cursorn."""
        # Markera aktuellt ord
        cursor.select(QTextCursor.WordUnderCursor)
        return cursor.selectedText()
    
    def _get_completion_suggestions(self, partial_text: str) -> List[str]:
        """Hämtar förslag från TM och andra källor."""
        suggestions = set()
        
        try:
            # Hämta från Translation Memory
            tm_results = lookup_tm(partial_text, max_results=10)
            for result in tm_results:
                target_text = result.get("target", "")
                if target_text and len(target_text.strip()) > 0:
                    # Lägg till hela översättningen
                    suggestions.add(target_text.strip())
                    
                    # Lägg till enskilda ord från översättningen
                    words = target_text.split()
                    for word in words:
                        clean_word = word.strip(".,!?;:()[]{}\"'")
                        if (len(clean_word) >= 2 and 
                            partial_text.lower() in clean_word.lower()):
                            suggestions.add(clean_word)
        except Exception as e:
            print(f"TM lookup error for autocomplete: {e}")
        
        # Filtrera och sortera förslag
        filtered = []
        partial_lower = partial_text.lower()
        
        for suggestion in suggestions:
            if (len(suggestion) > len(partial_text) and
                partial_lower in suggestion.lower()):
                filtered.append(suggestion)
        
        # Sortera: exakta matchningar först, sedan alfabetiskt
        filtered.sort(key=lambda x: (
            not x.lower().startswith(partial_lower),  # Börjar med partial text
            len(x),  # Kortare först
            x.lower()  # Alfabetisk ordning
        ))
        
        return filtered[:10]  # Max 10 förslag
    
    def _insert_completion(self, completion: str):
        """Sätter in valt autocomplete-förslag."""
        if not self._completer:
            return
        
        cursor = self.textCursor()
        
        # Hitta aktuellt ord som ska ersättas
        cursor.select(QTextCursor.WordUnderCursor)
        current_word = cursor.selectedText()
        
        # Ersätt med förslaget
        if current_word:
            cursor.insertText(completion)
        else:
            cursor.insertText(completion)
        
        self.setTextCursor(cursor)
    
    def keyPressEvent(self, event: QKeyEvent):
        """Hanterar tangentbordsnavigering för autocomplete."""
        if self._completer and self._completer.popup().isVisible():
            # Låt completer hantera vissa tangenter
            if event.key() in (Qt.Key_Enter, Qt.Key_Return, Qt.Key_Escape, 
                             Qt.Key_Tab, Qt.Key_Backtab):
                event.ignore()
                return
        
        # Normal textbehandling
        super().keyPressEvent(event)
        
        # Visa autocomplete för vissa tangenter
        if (event.key() not in (Qt.Key_Enter, Qt.Key_Return, Qt.Key_Escape, 
                               Qt.Key_Tab, Qt.Key_Backtab) and 
            event.text() and event.text().isprintable()):
            self._on_text_changed()
    
    def set_completion_enabled(self, enabled: bool):
        """Aktiverar/inaktiverar autocomplete."""
        self._completion_enabled = enabled
        if not enabled and self._completer:
            self._completer.popup().hide()
    
    def is_completion_enabled(self) -> bool:
        """Returnerar om autocomplete är aktiverat."""
        return self._completion_enabled
    
    def set_min_chars_for_completion(self, min_chars: int):
        """Ställer in minsta antal tecken för autocomplete."""
        self._min_chars_for_completion = max(1, min_chars)
    
    def get_min_chars_for_completion(self) -> int:
        """Returnerar minsta antal tecken för autocomplete."""
        return self._min_chars_for_completion
    
    def set_highlighting_enabled(self, enabled: bool):
        """Aktiverar/inaktiverar syntax highlighting."""
        self._highlighting_enabled = enabled
        if enabled:
            if not self._syntax_highlighter:
                self._syntax_highlighter = TranslationHighlighter(self.document())
        else:
            if self._syntax_highlighter:
                self._syntax_highlighter.setDocument(None)
                self._syntax_highlighter = None
    
    def is_highlighting_enabled(self) -> bool:
        """Returnerar om syntax highlighting är aktiverat."""
        return self._highlighting_enabled
    
    def set_highlighting_theme(self, theme: str = "light"):
        """Ställer in syntax highlighting tema."""
        if self._syntax_highlighter:
            self._syntax_highlighter.set_theme(theme)

    # ── MT Suggestion Methods ─────────────────────────────────────

    def get_mt_widget(self) -> MTSuggestionWidget:
        """Return (and lazily create) the MT suggestion widget."""
        if self._mt_widget is None:
            self._mt_widget = MTSuggestionWidget()
            self._mt_widget.suggestion_accepted.connect(self._on_mt_suggestion_accepted)
        return self._mt_widget

    def set_mt_enabled(self, enabled: bool):
        """Enable/disable MT suggestions."""
        self._mt_enabled = enabled
        if not enabled and self._mt_widget:
            self._mt_widget.setVisible(False)

    def set_source_text(self, source_text: str):
        """Set source text and trigger MT suggestion fetch."""
        self._mt_source_text = source_text
        if self._mt_enabled and source_text.strip():
            self._fetch_mt_suggestions(source_text)
        elif self._mt_widget:
            self._mt_widget.setVisible(False)

    def _fetch_mt_suggestions(self, text: str):
        """Fetch MT suggestions in a daemon thread (no QThread — avoids GC crash)."""
        # Bump generation so stale results are discarded
        self._mt_generation = getattr(self, '_mt_generation', 0) + 1
        gen = self._mt_generation

        settings = Settings.get()
        source = settings["source_language"]
        target = settings["target_language"]

        engines = []
        from linguaedit.services.keystore import get_secret
        if get_secret("deepl", "api_key"):
            engines.append("deepl")
        if get_secret("openai", "api_key"):
            engines.append("openai")
        if not engines:
            engines.append("lingva")

        widget = self.get_mt_widget()
        widget.show_loading()

        import threading

        def _do_fetch():
            results = []
            for engine in engines:
                try:
                    from linguaedit.services.translator import translate, ENGINES
                    result = translate(text, engine=engine,
                                       source=source, target=target)
                    if result and result.strip():
                        name = ENGINES.get(engine, {}).get("name", engine)
                        results.append((name, result.strip()))
                except Exception:
                    pass
            # Deliver results to main thread via QTimer.singleShot
            if gen == self._mt_generation:
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, lambda r=results: self._on_mt_results(r))

        t = threading.Thread(target=_do_fetch, daemon=True)
        t.start()

    def _on_mt_results(self, results: list[tuple[str, str]]):
        """Handle MT results from background thread."""
        widget = self.get_mt_widget()
        widget.show_suggestions(results)

    def _on_mt_suggestion_accepted(self, text: str):
        """Insert MT suggestion into the editor."""
        self.setPlainText(text)
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.setTextCursor(cursor)
        self.setFocus()

    # ── Spell Check Methods ───────────────────────────────────────

    def set_spell_language(self, language: str):
        """Set the spell check language."""
        self._spell_language = language
        self._schedule_spellcheck()

    def set_spellcheck_enabled(self, enabled: bool):
        """Enable/disable spell checking."""
        self._spellcheck_enabled = enabled
        if not enabled:
            self._spell_issues = []
            if self._syntax_highlighter:
                self._syntax_highlighter.set_spell_errors([])
                self._syntax_highlighter.rehighlight()

    def _schedule_spellcheck(self):
        """Schedule a spell check after a short delay."""
        if self._spellcheck_enabled:
            self._spellcheck_timer.start()

    def _run_spellcheck(self):
        """Run spell check and update highlighting."""
        if not self._spellcheck_enabled:
            return
        text = self.toPlainText()
        if not text.strip():
            self._spell_issues = []
            if self._syntax_highlighter:
                self._syntax_highlighter.set_spell_errors([])
                self._syntax_highlighter.rehighlight()
            return

        from linguaedit.services.spellcheck import check_text
        issues = check_text(text, language=self._spell_language)
        # Filter out user dictionary words
        self._spell_issues = [
            i for i in issues if i.word.lower() not in self._user_dictionary
        ]
        if self._syntax_highlighter:
            self._syntax_highlighter.set_spell_errors(self._spell_issues)
            self._syntax_highlighter.rehighlight()

    def add_to_dictionary(self, word: str):
        """Add a word to the user dictionary."""
        self._user_dictionary.add(word.lower())
        self._load_save_user_dict(save=True)
        self._run_spellcheck()

    def _load_save_user_dict(self, save: bool = False):
        """Load or save user dictionary."""
        from pathlib import Path
        dict_path = Path.home() / ".config" / "linguaedit" / "user_dictionary.txt"
        if save:
            dict_path.parent.mkdir(parents=True, exist_ok=True)
            dict_path.write_text("\n".join(sorted(self._user_dictionary)), "utf-8")
        elif dict_path.exists():
            words = dict_path.read_text("utf-8").strip().split("\n")
            self._user_dictionary = {w.strip().lower() for w in words if w.strip()}

    def _show_context_menu(self, pos):
        """Show context menu with spell check suggestions."""
        menu = self.createStandardContextMenu()

        # Check if cursor is on a misspelled word
        cursor = self.cursorForPosition(pos)
        cursor.select(QTextCursor.WordUnderCursor)
        word = cursor.selectedText()

        matching_issues = [i for i in self._spell_issues if i.word == word]
        if matching_issues:
            issue = matching_issues[0]
            menu.insertSeparator(menu.actions()[0])

            # Add to dictionary action
            add_action = QAction(_("Add '%s' to dictionary") % word, menu)
            add_action.triggered.connect(lambda: self.add_to_dictionary(word))
            menu.insertAction(menu.actions()[0], add_action)

            # Suggestion actions
            if issue.suggestions:
                for suggestion in issue.suggestions[:5]:
                    action = QAction(suggestion, menu)
                    action.setFont(QFont(action.font().family(), -1, QFont.Bold))
                    captured_suggestion = suggestion
                    captured_cursor = self.textCursor()
                    captured_cursor.setPosition(cursor.selectionStart())
                    captured_cursor.setPosition(cursor.selectionEnd(), QTextCursor.KeepAnchor)
                    action.triggered.connect(
                        lambda checked, s=captured_suggestion, c=cursor:
                        self._replace_word(c, s)
                    )
                    menu.insertAction(menu.actions()[0], action)

                menu.insertSeparator(menu.actions()[0])
                header = QAction(_("Spelling suggestions:"), menu)
                header.setEnabled(False)
                menu.insertAction(menu.actions()[0], header)

        menu.exec(self.mapToGlobal(pos))

    def _replace_word(self, cursor: QTextCursor, replacement: str):
        """Replace word at cursor with replacement."""
        cursor.select(QTextCursor.WordUnderCursor)
        cursor.insertText(replacement)