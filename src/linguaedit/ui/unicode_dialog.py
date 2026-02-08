"""Unicode inspector dialog — analyze characters in text."""

from __future__ import annotations

import unicodedata
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QTextEdit, QLineEdit, QGroupBox,
    QHeaderView, QAbstractItemView, QCheckBox, QSplitter
)
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QFont, QColor


class UnicodeDialog(QDialog):
    """Dialog for inspecting Unicode characters in text."""
    
    # Invisible/suspicious characters to highlight
    INVISIBLE_CHARS = {
        '\u200B',  # Zero Width Space
        '\u200C',  # Zero Width Non-Joiner
        '\u200D',  # Zero Width Joiner
        '\u200E',  # Left-to-Right Mark
        '\u200F',  # Right-to-Left Mark
        '\u202A',  # Left-to-Right Embedding
        '\u202B',  # Right-to-Left Embedding
        '\u202C',  # Pop Directional Formatting
        '\u202D',  # Left-to-Right Override
        '\u202E',  # Right-to-Left Override
        '\u2060',  # Word Joiner
        '\u2061',  # Function Application
        '\u2062',  # Invisible Times
        '\u2063',  # Invisible Separator
        '\u2064',  # Invisible Plus
        '\u00AD',  # Soft Hyphen
        '\uFEFF',  # Zero Width No-Break Space (BOM)
    }
    
    SUSPICIOUS_RANGES = [
        (0x2000, 0x206F),  # General Punctuation
        (0xFE00, 0xFE0F),  # Variation Selectors
        (0xE000, 0xF8FF),  # Private Use Area
        (0x1D100, 0x1D1FF),  # Musical Symbols
    ]
    
    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Unicode Inspector"))
        self.setModal(True)
        self.resize(800, 600)
        
        self._build_ui()
        if text:
            self.set_text(text)
    
    def _build_ui(self):
        """Build the dialog UI."""
        layout = QVBoxLayout(self)
        
        # Input section
        input_group = QGroupBox(self.tr("Text to Analyze"))
        input_layout = QVBoxLayout(input_group)
        
        self._text_edit = QTextEdit()
        self._text_edit.setMaximumHeight(100)
        self._text_edit.setPlaceholderText(self.tr("Enter or paste text to analyze..."))
        self._text_edit.textChanged.connect(self._on_text_changed)
        input_layout.addWidget(self._text_edit)
        
        input_controls = QHBoxLayout()
        
        self._analyze_btn = QPushButton(self.tr("Analyze"))
        self._analyze_btn.clicked.connect(self._analyze_text)
        input_controls.addWidget(self._analyze_btn)
        
        self._clear_btn = QPushButton(self.tr("Clear"))
        self._clear_btn.clicked.connect(self._clear_analysis)
        input_controls.addWidget(self._clear_btn)
        
        input_controls.addStretch()
        
        self._highlight_suspicious = QCheckBox(self.tr("Highlight suspicious characters"))
        self._highlight_suspicious.setChecked(True)
        self._highlight_suspicious.toggled.connect(self._analyze_text)
        input_controls.addWidget(self._highlight_suspicious)
        
        input_layout.addLayout(input_controls)
        layout.addWidget(input_group)
        
        # Results section
        results_splitter = QSplitter(Qt.Horizontal)
        
        # Character table
        table_group = QGroupBox(self.tr("Character Analysis"))
        table_layout = QVBoxLayout(table_group)
        
        self._char_table = QTableWidget()
        self._char_table.setColumnCount(6)
        self._char_table.setHorizontalHeaderLabels([
            self.tr("Pos"), self.tr("Char"), self.tr("Code Point"), 
            self.tr("Name"), self.tr("Category"), self.tr("Block")
        ])
        
        header = self._char_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents) 
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        
        self._char_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._char_table.itemSelectionChanged.connect(self._on_char_selected)
        
        table_layout.addWidget(self._char_table)
        results_splitter.addWidget(table_group)
        
        # Details panel
        details_group = QGroupBox(self.tr("Character Details"))
        details_layout = QVBoxLayout(details_group)
        
        self._char_display = QLabel("")
        char_font = QFont()
        char_font.setPointSize(24)
        self._char_display.setFont(char_font)
        self._char_display.setAlignment(Qt.AlignCenter)
        self._char_display.setMinimumHeight(60)
        self._char_display.setStyleSheet("border: 1px solid gray; background: white;")
        details_layout.addWidget(self._char_display)
        
        self._char_info = QTextEdit()
        self._char_info.setReadOnly(True)
        self._char_info.setMaximumHeight(200)
        details_layout.addWidget(self._char_info)
        
        # Summary
        self._summary_label = QLabel("")
        self._summary_label.setWordWrap(True)
        self._summary_label.setStyleSheet("color: gray; font-size: 10pt;")
        details_layout.addWidget(self._summary_label)
        
        details_layout.addStretch()
        results_splitter.addWidget(details_group)
        
        layout.addWidget(results_splitter)
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        
        self._copy_analysis_btn = QPushButton(self.tr("Copy Analysis"))
        self._copy_analysis_btn.clicked.connect(self._copy_analysis)
        self._copy_analysis_btn.setEnabled(False)
        button_layout.addWidget(self._copy_analysis_btn)
        
        button_layout.addStretch()
        
        close_btn = QPushButton(self.tr("Close"))
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        # Initial state
        self._clear_analysis()
    
    def set_text(self, text: str):
        """Set the text to analyze."""
        self._text_edit.setPlainText(text)
        self._analyze_text()
    
    @Slot()
    def _on_text_changed(self):
        """Handle text change."""
        # Auto-analyze for short texts
        text = self._text_edit.toPlainText()
        if len(text) <= 100:
            self._analyze_text()
    
    @Slot()
    def _analyze_text(self):
        """Analyze the current text."""
        text = self._text_edit.toPlainText()
        if not text:
            self._clear_analysis()
            return
        
        self._char_table.setRowCount(len(text))
        
        suspicious_count = 0
        invisible_count = 0
        
        for i, char in enumerate(text):
            codepoint = ord(char)
            
            # Position
            pos_item = QTableWidgetItem(str(i))
            self._char_table.setItem(i, 0, pos_item)
            
            # Character (with special handling for invisible chars)
            char_display = char
            if char in self.INVISIBLE_CHARS or char.isspace() and char != ' ':
                char_display = f"[{char!r}]"
                invisible_count += 1
            elif not char.isprintable():
                char_display = f"[U+{codepoint:04X}]"
            
            char_item = QTableWidgetItem(char_display)
            
            # Highlight suspicious characters
            is_suspicious = self._is_suspicious_char(char)
            if is_suspicious and self._highlight_suspicious.isChecked():
                char_item.setBackground(QColor(255, 200, 200))  # Light red
                suspicious_count += 1
            elif char in self.INVISIBLE_CHARS:
                char_item.setBackground(QColor(255, 255, 200))  # Light yellow
            
            self._char_table.setItem(i, 1, char_item)
            
            # Code point
            codepoint_item = QTableWidgetItem(f"U+{codepoint:04X}")
            self._char_table.setItem(i, 2, codepoint_item)
            
            # Unicode name
            try:
                name = unicodedata.name(char, f"<unnamed {codepoint:04X}>")
            except ValueError:
                name = f"<private use {codepoint:04X}>"
            
            name_item = QTableWidgetItem(name)
            self._char_table.setItem(i, 3, name_item)
            
            # Category
            category = unicodedata.category(char)
            category_item = QTableWidgetItem(category)
            self._char_table.setItem(i, 4, category_item)
            
            # Unicode block
            block = self._get_unicode_block(codepoint)
            block_item = QTableWidgetItem(block)
            self._char_table.setItem(i, 5, block_item)
        
        # Update summary
        total_chars = len(text)
        summary = self.tr(
            "Total: {0} characters | Invisible: {1} | Suspicious: {2}"
        ).format(total_chars, invisible_count, suspicious_count)
        
        if suspicious_count > 0 or invisible_count > 0:
            summary += self.tr(" | ⚠️ Check highlighted characters")
        
        self._summary_label.setText(summary)
        self._copy_analysis_btn.setEnabled(True)
    
    def _is_suspicious_char(self, char: str) -> bool:
        """Check if a character is suspicious."""
        codepoint = ord(char)
        
        # Check invisible characters
        if char in self.INVISIBLE_CHARS:
            return True
        
        # Check suspicious ranges
        for start, end in self.SUSPICIOUS_RANGES:
            if start <= codepoint <= end:
                return True
        
        # Check for lookalike characters (basic check)
        # This could be expanded with a comprehensive lookalike database
        ascii_lookalikes = {
            'а': 'a',  # Cyrillic vs Latin
            'е': 'e',
            'о': 'o',
            'р': 'p',
            'с': 'c',
            'х': 'x',
            'А': 'A',
            'В': 'B',
            'Е': 'E',
            'К': 'K',
            'М': 'M',
            'Н': 'H',
            'О': 'O',
            'Р': 'P',
            'С': 'C',
            'Т': 'T',
            'Х': 'X',
        }
        
        return char in ascii_lookalikes
    
    def _get_unicode_block(self, codepoint: int) -> str:
        """Get the Unicode block name for a codepoint."""
        # Basic Unicode blocks (could be expanded)
        blocks = [
            (0x0000, 0x007F, "Basic Latin"),
            (0x0080, 0x00FF, "Latin-1 Supplement"),
            (0x0100, 0x017F, "Latin Extended-A"),
            (0x0180, 0x024F, "Latin Extended-B"),
            (0x0250, 0x02AF, "IPA Extensions"),
            (0x02B0, 0x02FF, "Spacing Modifier Letters"),
            (0x0300, 0x036F, "Combining Diacritical Marks"),
            (0x0370, 0x03FF, "Greek and Coptic"),
            (0x0400, 0x04FF, "Cyrillic"),
            (0x0500, 0x052F, "Cyrillic Supplement"),
            (0x1E00, 0x1EFF, "Latin Extended Additional"),
            (0x2000, 0x206F, "General Punctuation"),
            (0x2070, 0x209F, "Superscripts and Subscripts"),
            (0x20A0, 0x20CF, "Currency Symbols"),
            (0x2100, 0x214F, "Letterlike Symbols"),
            (0x2190, 0x21FF, "Arrows"),
            (0x2200, 0x22FF, "Mathematical Operators"),
            (0x2300, 0x23FF, "Miscellaneous Technical"),
            (0x2600, 0x26FF, "Miscellaneous Symbols"),
            (0x2700, 0x27BF, "Dingbats"),
            (0x3000, 0x303F, "CJK Symbols and Punctuation"),
            (0x3040, 0x309F, "Hiragana"),
            (0x30A0, 0x30FF, "Katakana"),
            (0x4E00, 0x9FFF, "CJK Unified Ideographs"),
            (0xE000, 0xF8FF, "Private Use Area"),
            (0xFE00, 0xFE0F, "Variation Selectors"),
            (0xFE20, 0xFE2F, "Combining Half Marks"),
            (0xFE30, 0xFE4F, "CJK Compatibility Forms"),
            (0xFE50, 0xFE6F, "Small Form Variants"),
            (0xFE70, 0xFEFF, "Arabic Presentation Forms-B"),
            (0xFF00, 0xFFEF, "Halfwidth and Fullwidth Forms"),
            (0xFFF0, 0xFFFF, "Specials"),
        ]
        
        for start, end, name in blocks:
            if start <= codepoint <= end:
                return name
        
        return "Unknown Block"
    
    @Slot()
    def _clear_analysis(self):
        """Clear the analysis."""
        self._char_table.setRowCount(0)
        self._char_display.setText("")
        self._char_info.clear()
        self._summary_label.setText(self.tr("Enter text to analyze Unicode characters"))
        self._copy_analysis_btn.setEnabled(False)
    
    @Slot()
    def _on_char_selected(self):
        """Handle character selection in table."""
        current_row = self._char_table.currentRow()
        if current_row < 0:
            return
        
        text = self._text_edit.toPlainText()
        if current_row >= len(text):
            return
        
        char = text[current_row]
        codepoint = ord(char)
        
        # Update character display
        if char in self.INVISIBLE_CHARS or not char.isprintable():
            self._char_display.setText(f"U+{codepoint:04X}")
        else:
            self._char_display.setText(char)
        
        # Update character info
        info_parts = []
        
        # Basic info
        info_parts.append(f"Character: {char!r}")
        info_parts.append(f"Code Point: U+{codepoint:04X} ({codepoint})")
        
        try:
            name = unicodedata.name(char)
            info_parts.append(f"Name: {name}")
        except ValueError:
            info_parts.append("Name: <no name>")
        
        # Category and properties
        category = unicodedata.category(char)
        info_parts.append(f"Category: {category}")
        
        block = self._get_unicode_block(codepoint)
        info_parts.append(f"Block: {block}")
        
        # Numeric value
        numeric = unicodedata.numeric(char, None)
        if numeric is not None:
            info_parts.append(f"Numeric Value: {numeric}")
        
        # Decomposition
        decomp = unicodedata.decomposition(char)
        if decomp:
            info_parts.append(f"Decomposition: {decomp}")
        
        # Combining class
        combining = unicodedata.combining(char)
        if combining:
            info_parts.append(f"Combining Class: {combining}")
        
        # Bidirectional info
        bidi = unicodedata.bidirectional(char)
        if bidi:
            info_parts.append(f"Bidirectional: {bidi}")
        
        # Warnings
        if char in self.INVISIBLE_CHARS:
            info_parts.append("")
            info_parts.append("⚠️ INVISIBLE CHARACTER")
            info_parts.append("This character is not normally visible but may affect text layout.")
        
        if self._is_suspicious_char(char):
            info_parts.append("")
            info_parts.append("⚠️ POTENTIALLY SUSPICIOUS")
            info_parts.append("This character may be used in spoofing attacks or cause confusion.")
        
        self._char_info.setPlainText("\n".join(info_parts))
    
    @Slot()
    def _copy_analysis(self):
        """Copy the analysis to clipboard."""
        text = self._text_edit.toPlainText()
        if not text:
            return
        
        analysis_parts = []
        analysis_parts.append("Unicode Character Analysis")
        analysis_parts.append("=" * 30)
        analysis_parts.append(f"Text: {text!r}")
        analysis_parts.append(f"Length: {len(text)} characters")
        analysis_parts.append("")
        
        for i, char in enumerate(text):
            codepoint = ord(char)
            try:
                name = unicodedata.name(char, f"<unnamed {codepoint:04X}>")
            except ValueError:
                name = f"<private use {codepoint:04X}>"
            
            category = unicodedata.category(char)
            block = self._get_unicode_block(codepoint)
            
            char_display = char if char.isprintable() and char not in self.INVISIBLE_CHARS else f"[{char!r}]"
            
            analysis_parts.append(
                f"{i:3d}: {char_display} | U+{codepoint:04X} | {name} | {category} | {block}"
            )
        
        analysis_text = "\n".join(analysis_parts)
        
        from PySide6.QtGui import QGuiApplication
        QGuiApplication.clipboard().setText(analysis_text)