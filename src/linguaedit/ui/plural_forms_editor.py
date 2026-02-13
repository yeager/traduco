"""Plural Forms Editor — Specialiserad editor för plural forms.

Hanterar ngettext/plural forms i PO-filer med separata tabs för varje
pluralform enligt språkets CLDR-regler.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QPlainTextEdit,
    QLabel, QGroupBox, QPushButton, QTextEdit
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from linguaedit.parsers.po_parser import TranslationEntry


class PluralFormsEditor(QWidget):
    """Widget för redigering av plural forms."""
    
    # Signal när plural forms ändras
    plural_changed = Signal(dict)  # {0: "text", 1: "texts", ...}
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        self._entry: Optional[TranslationEntry] = None
        self._language_code = "sv"
        self._plural_forms_count = 2
        self._plural_rule = ""
        
        self._setup_ui()
        self._update_plural_info()
    
    def _setup_ui(self):
        """Skapar användargrässnittet."""
        layout = QVBoxLayout(self)
        
        # Info-ruta om pluralregler
        info_group = QGroupBox(self.tr("Plural rules"))
        info_layout = QVBoxLayout(info_group)
        
        self._rule_label = QLabel()
        self._rule_label.setWordWrap(True)
        self._rule_label.setStyleSheet("QLabel { color: palette(mid); font-style: italic; }")
        info_layout.addWidget(self._rule_label)
        
        layout.addWidget(info_group)
        
        # Tab-widget för plural forms
        self._tab_widget = QTabWidget()
        self._editors: Dict[int, QPlainTextEdit] = {}
        
        layout.addWidget(self._tab_widget)
        
        # Kontrollknappar
        controls = QHBoxLayout()
        
        self._sync_button = QPushButton(self.tr("Sync from singular"))
        self._sync_button.clicked.connect(self._sync_from_singular)
        controls.addWidget(self._sync_button)
        
        controls.addStretch()
        
        self._clear_button = QPushButton(self.tr("Clear all"))
        self._clear_button.clicked.connect(self._clear_all)
        controls.addWidget(self._clear_button)
        
        layout.addLayout(controls)
    
    def set_language(self, language_code: str):
        """Ställer in språk och uppdaterar plural-reglerna."""
        self._language_code = language_code
        self._update_plural_info()
        self._rebuild_tabs()
    
    def set_entry(self, entry: Optional[TranslationEntry]):
        """Ställer in translation entry att redigera."""
        self._entry = entry
        self._update_from_entry()
    
    def _update_plural_info(self):
        """Uppdaterar information om pluralregler för språket."""
        plural_rules = self._get_plural_rules(self._language_code)
        self._plural_forms_count = plural_rules["count"]
        self._plural_rule = plural_rules["rule"]
        
        rule_text = f"<b>{self._language_code.upper()}:</b> {self._plural_rule}"
        rule_text += f"<br><small>{plural_rules['description']}</small>"
        
        self._rule_label.setText(rule_text)
    
    def _get_plural_rules(self, lang_code: str) -> Dict:
        """Hämtar CLDR-baserade plural-regler för språket."""
        # Förenklad CLDR-data för några vanliga språk
        rules = {
            "sv": {
                "count": 2,
                "rule": "nplurals=2; plural=(n != 1);",
                "description": "one: n=1 (1 katt), other: n≠1 (0,2,3... katter)"
            },
            "en": {
                "count": 2, 
                "rule": "nplurals=2; plural=(n != 1);",
                "description": "one: n=1 (1 cat), other: n≠1 (0,2,3... cats)"
            },
            "de": {
                "count": 2,
                "rule": "nplurals=2; plural=(n != 1);", 
                "description": "one: n=1 (1 Katze), other: n≠1 (0,2,3... Katzen)"
            },
            "fr": {
                "count": 2,
                "rule": "nplurals=2; plural=(n > 1);",
                "description": "one: n=0,1 (0,1 chat), other: n>1 (2,3... chats)"
            },
            "pl": {
                "count": 3,
                "rule": "nplurals=3; plural=(n==1 ? 0 : n%10>=2 && n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2);",
                "description": "one: n=1, few: n%10=2-4 && n%100≠12-14, other: rest"
            },
            "ru": {
                "count": 3,
                "rule": "nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : n%10>=2 && n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2);",
                "description": "one: ends in 1 but not 11, few: ends in 2-4 but not 12-14, other: rest"
            },
            "cs": {
                "count": 3,
                "rule": "nplurals=3; plural=(n==1) ? 0 : (n>=2 && n<=4) ? 1 : 2;",
                "description": "one: n=1, few: n=2-4, other: rest"
            },
            "ar": {
                "count": 6,
                "rule": "nplurals=6; plural=(n==0 ? 0 : n==1 ? 1 : n==2 ? 2 : n%100>=3 && n%100<=10 ? 3 : n%100>=11 ? 4 : 5);",
                "description": "zero: n=0, one: n=1, two: n=2, few: n%100=3-10, many: n%100=11-99, other: rest"
            }
        }
        
        return rules.get(lang_code, rules["en"])  # Fallback till engelska
    
    def _rebuild_tabs(self):
        """Bygger om tabs baserat på plural-reglerna."""
        # Rensa befintliga tabs
        while self._tab_widget.count() > 0:
            self._tab_widget.removeTab(0)
        self._editors.clear()
        
        # Skapa nya tabs
        for i in range(self._plural_forms_count):
            editor = QPlainTextEdit()
            editor.textChanged.connect(lambda i=i: self._on_plural_text_changed(i))
            
            # Tab-namn baserat på språk och index
            tab_name = self._get_plural_tab_name(i)
            
            self._tab_widget.addTab(editor, tab_name)
            self._editors[i] = editor
    
    def _get_plural_tab_name(self, index: int) -> str:
        """Genererar tab-namn för plural form."""
        # Svenska exempel
        if self._language_code == "sv":
            return ["Singular (1)", "Plural (andra)"][index] if index < 2 else f"Form {index}"
        elif self._language_code == "en":
            return ["Singular (1)", "Plural (other)"][index] if index < 2 else f"Form {index}"
        elif self._language_code == "pl" or self._language_code == "ru":
            names = ["One", "Few", "Many"]
            return names[index] if index < len(names) else f"Form {index}"
        elif self._language_code == "ar":
            names = ["Zero", "One", "Two", "Few", "Many", "Other"]
            return names[index] if index < len(names) else f"Form {index}"
        else:
            return f"Form {index}"
    
    def _update_from_entry(self):
        """Uppdaterar editorn från TranslationEntry."""
        if not self._entry:
            self._clear_all()
            return
        
        # Kolla om det är plural entry
        if not getattr(self._entry, 'msgid_plural', None):
            # Inte en plural entry, dölj editorn
            self.setVisible(False)
            return
        
        self.setVisible(True)
        
        # Fyll i plural forms
        msgstr_plural = getattr(self._entry, 'msgstr_plural', {})
        
        for i, editor in self._editors.items():
            text = msgstr_plural.get(i, "")
            editor.blockSignals(True)
            editor.setPlainText(text)
            editor.blockSignals(False)
    
    def _on_plural_text_changed(self, index: int):
        """Hanterar ändringar i plural form-text."""
        if index not in self._editors:
            return
        
        # Samla alla plural forms
        plural_data = {}
        for i, editor in self._editors.items():
            text = editor.toPlainText()
            if text.strip():  # Bara icke-tomma
                plural_data[i] = text
        
        # Uppdatera entry
        if self._entry:
            if not hasattr(self._entry, 'msgstr_plural'):
                self._entry.msgstr_plural = {}
            self._entry.msgstr_plural[index] = self._editors[index].toPlainText()
        
        # Skicka signal
        self.plural_changed.emit(plural_data)
    
    def _sync_from_singular(self):
        """Synkroniserar pluralformer från singular (index 0)."""
        if 0 not in self._editors:
            return
        
        singular_text = self._editors[0].toPlainText()
        if not singular_text.strip():
            return
        
        # Enkla transformationsregler för svenska
        if self._language_code == "sv":
            plural_text = self._make_swedish_plural(singular_text)
        elif self._language_code == "en":
            plural_text = self._make_english_plural(singular_text)
        else:
            plural_text = singular_text  # Fallback
        
        # Sätt plural-text i index 1
        if 1 in self._editors:
            self._editors[1].setPlainText(plural_text)
    
    def _make_swedish_plural(self, singular: str) -> str:
        """Gör enkla svenska pluraltransformationer."""
        # Mycket förenklad - bara för demonstration
        if singular.endswith("a"):
            return singular + "or"
        elif singular.endswith("e"):
            return singular + "ar"
        elif singular.endswith("d") or singular.endswith("t"):
            return singular + "er"
        else:
            return singular + "ar"  # Mest vanliga
    
    def _make_english_plural(self, singular: str) -> str:
        """Gör enkla engelska pluraltransformationer."""
        if singular.endswith("s") or singular.endswith("x") or singular.endswith("ch") or singular.endswith("sh"):
            return singular + "es"
        elif singular.endswith("y") and len(singular) > 1 and singular[-2] not in "aeiou":
            return singular[:-1] + "ies"
        else:
            return singular + "s"
    
    def _clear_all(self):
        """Rensar alla plural forms."""
        for editor in self._editors.values():
            editor.blockSignals(True)
            editor.clear()
            editor.blockSignals(False)
        
        # Skicka tom signal
        self.plural_changed.emit({})
    
    def get_plural_forms(self) -> Dict[int, str]:
        """Returnerar alla plural forms som dict."""
        result = {}
        for i, editor in self._editors.items():
            text = editor.toPlainText()
            if text.strip():
                result[i] = text
        return result
    
    def has_plural_content(self) -> bool:
        """Returnerar True om det finns plural-innehåll."""
        return bool(self.get_plural_forms())