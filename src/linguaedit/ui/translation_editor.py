"""Translation Editor med Autocomplete — Förbättrad translation editor.

Utökar QPlainTextEdit med autocomplete-funktionalitet baserat på
Translation Memory-databasen och andra källor.
"""

from __future__ import annotations

from typing import List, Optional
from PySide6.QtWidgets import (
    QPlainTextEdit, QCompleter, QAbstractItemView, QWidget
)
from PySide6.QtCore import Qt, Signal, QStringListModel, QTimer
from PySide6.QtGui import QKeyEvent, QTextCursor

from linguaedit.services.tm import lookup_tm
from linguaedit.services.settings import Settings
from linguaedit.ui.syntax_highlighting import TranslationHighlighter


class TranslationEditor(QPlainTextEdit):
    """Utökad translation editor med autocomplete."""
    
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
        
        # Setup autocomplete
        self._setup_completer()
        
        # Setup syntax highlighting
        self._syntax_highlighter = TranslationHighlighter(self.document())
        self._highlighting_enabled = True
        
        # Koppla signaler
        self.textChanged.connect(self._on_text_changed)
        self.textChanged.connect(self.translation_changed.emit)
    
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
            tm_results = lookup_tm(partial_text, limit=10)
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