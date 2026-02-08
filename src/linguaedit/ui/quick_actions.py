"""Quick Actions popup — kontextmenyer för snabba åtgärder."""

from __future__ import annotations

from PySide6.QtWidgets import QMenu, QWidget
from PySide6.QtCore import QPoint, Signal
from PySide6.QtGui import QKeySequence, QAction

from linguaedit.services.tm import lookup_tm
from linguaedit.services.glossary import get_terms


class QuickActionsMenu(QMenu):
    """Popup-meny med snabba åtgärder baserat på kontext."""
    
    # Signaler
    copy_source_requested = Signal()
    apply_tm_requested = Signal(str)  # TM suggestion text
    apply_glossary_requested = Signal(str)  # Glossary term
    fix_case_requested = Signal()
    add_punctuation_requested = Signal(str)  # Punctuation to add
    
    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setTitle(self.tr("Quick Actions"))
        
    def show_for_context(self, source_text: str, current_text: str, cursor_pos: QPoint):
        """Visa quick actions baserat på kontext."""
        self.clear()
        
        actions_added = False
        
        # Action 1: Copy source om tomt
        if not current_text.strip():
            action = QAction(self.tr("📋 Copy source"), self)
            action.triggered.connect(self.copy_source_requested.emit)
            self.addAction(action)
            actions_added = True
        
        # Action 2: Apply TM suggestion
        if source_text.strip():
            tm_matches = lookup_tm(source_text, threshold=0.8, max_results=3)
            if tm_matches:
                if actions_added:
                    self.addSeparator()
                
                tm_menu = self.addMenu(self.tr("🧠 Apply TM suggestion"))
                for match in tm_matches:
                    action = QAction(f"{match.similarity:.0%}: {match.target[:50]}...", self)
                    action.triggered.connect(lambda checked, text=match.target: self.apply_tm_requested.emit(text))
                    tm_menu.addAction(action)
                actions_added = True
        
        # Action 3: Apply glossary term
        if source_text.strip():
            # Hitta ord i source som finns i glossary
            words = source_text.lower().split()
            glossary_terms = []
            
            try:
                all_terms = get_terms()
                for term in all_terms:
                    source_term = term.source.lower()
                    if any(source_term in word or word in source_term for word in words):
                        glossary_terms.append(term)
            except:
                pass
            
            if glossary_terms:
                if actions_added:
                    self.addSeparator()
                
                glossary_menu = self.addMenu(self.tr("📚 Apply glossary term"))
                for term in glossary_terms[:5]:  # Max 5
                    action = QAction(f"{term.source} → {term.target}", self)
                    action.triggered.connect(lambda checked, text=term.target: self.apply_glossary_requested.emit(text))
                    glossary_menu.addAction(action)
                actions_added = True
        
        # Action 4: Fix case
        if source_text.strip() and current_text.strip():
            source_first = source_text.strip()[0]
            current_first = current_text.strip()[0]
            
            if (source_first.isalpha() and current_first.isalpha() and 
                source_first.isupper() != current_first.isupper()):
                
                if actions_added:
                    self.addSeparator()
                
                if source_first.isupper():
                    action = QAction(self.tr("🔤 Capitalize first letter"), self)
                else:
                    action = QAction(self.tr("🔤 Lowercase first letter"), self)
                action.triggered.connect(self.fix_case_requested.emit)
                self.addAction(action)
                actions_added = True
        
        # Action 5: Add missing punctuation
        if source_text.strip() and current_text.strip():
            source_punct = self._get_ending_punctuation(source_text)
            current_punct = self._get_ending_punctuation(current_text)
            
            if source_punct and not current_punct:
                if actions_added:
                    self.addSeparator()
                
                action = QAction(self.tr(f"➕ Add '{source_punct}'"), self)
                action.triggered.connect(lambda checked, punct=source_punct: self.add_punctuation_requested.emit(punct))
                self.addAction(action)
                actions_added = True
        
        # Visa menyn om vi har actions
        if actions_added:
            self.popup(cursor_pos)
        
        return actions_added
    
    def _get_ending_punctuation(self, text: str) -> str:
        """Hämta avslutande interpunktion."""
        text = text.strip()
        if not text:
            return ""
        
        last_char = text[-1]
        if last_char in '.!?:;':
            return last_char
        
        return ""