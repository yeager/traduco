"""Regex Tester Dialog - Test format strings with sample values."""

from __future__ import annotations

import re
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QLineEdit, QFormLayout, QGroupBox, QMessageBox,
    QScrollArea, QWidget, QListWidget, QListWidgetItem, QSplitter
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QClipboard


class RegexTesterDialog(QDialog):
    """Dialog for testing format strings with sample values."""
    
    def __init__(self, parent=None, text: str = ""):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Regex Tester"))
        self.setModal(True)
        self.resize(800, 600)
        
        self._current_text = text
        self._format_specs = []
        
        self._setup_ui()
        self._analyze_format_strings()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Input text
        input_group = QGroupBox(self.tr("Input Text"))
        input_layout = QVBoxLayout(input_group)
        
        self._text_edit = QTextEdit()
        self._text_edit.setPlainText(self._current_text)
        self._text_edit.textChanged.connect(self._on_text_changed)
        input_layout.addWidget(self._text_edit)
        
        layout.addWidget(input_group)
        
        # Splitter for format specs and test values
        splitter = QSplitter(Qt.Horizontal)
        
        # Format strings found
        format_group = QGroupBox(self.tr("Format Strings Found"))
        format_layout = QVBoxLayout(format_group)
        
        self._format_list = QListWidget()
        self._format_list.currentItemChanged.connect(self._on_format_selected)
        format_layout.addWidget(self._format_list)
        
        splitter.addWidget(format_group)
        
        # Test values
        values_group = QGroupBox(self.tr("Test Values"))
        values_layout = QVBoxLayout(values_group)
        
        # Scroll area for dynamic form
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._values_widget = QWidget()
        self._values_layout = QFormLayout(self._values_widget)
        scroll.setWidget(self._values_widget)
        values_layout.addWidget(scroll)
        
        splitter.addWidget(values_group)
        layout.addWidget(splitter)
        
        # Preview
        preview_group = QGroupBox(self.tr("Live Preview"))
        preview_layout = QVBoxLayout(preview_group)
        
        self._preview_edit = QTextEdit()
        self._preview_edit.setReadOnly(True)
        self._preview_edit.setMaximumHeight(100)
        font = QFont("Consolas", 10)
        font.setFamily("Menlo")
        self._preview_edit.setFont(font)
        preview_layout.addWidget(self._preview_edit)
        
        layout.addWidget(preview_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        copy_btn = QPushButton(self.tr("Copy Result"))
        copy_btn.clicked.connect(self._copy_result)
        button_layout.addWidget(copy_btn)
        
        button_layout.addStretch()
        
        close_btn = QPushButton(self.tr("Close"))
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
    def _analyze_format_strings(self):
        """Find all format strings in the text."""
        text = self._text_edit.toPlainText()
        
        # Different format string patterns
        patterns = [
            (r'%[sd%]', 'C-style (%s, %d)'),
            (r'{\d+}', 'Positional ({0}, {1})'),
            (r'{\w+}', 'Named ({name})'),
            (r'\$\{\w+\}', 'Variable (${var})'),
            (r'@\w+@', 'Token (@TOKEN@)'),
        ]
        
        self._format_specs.clear()
        self._format_list.clear()
        
        for pattern, description in patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                format_str = match.group()
                if format_str not in [spec['format'] for spec in self._format_specs]:
                    self._format_specs.append({
                        'format': format_str,
                        'type': description,
                        'value': ''
                    })
                    
                    item = QListWidgetItem(f"{format_str} ({description})")
                    item.setData(Qt.UserRole, format_str)
                    self._format_list.addItem(item)
        
        self._setup_value_inputs()
        self._update_preview()
        
    def _setup_value_inputs(self):
        """Create input fields for each format string."""
        # Clear existing inputs
        for i in reversed(range(self._values_layout.count())):
            child = self._values_layout.itemAt(i).widget()
            if child:
                child.deleteLater()
        
        self._value_inputs = {}
        
        for spec in self._format_specs:
            format_str = spec['format']
            
            # Suggest default value based on format type
            if '%s' in format_str:
                default = self.tr("Sample text")
            elif '%d' in format_str:
                default = "42"
            elif '{' in format_str and '}' in format_str:
                default = self.tr("Test value")
            else:
                default = self.tr("Value")
            
            line_edit = QLineEdit()
            line_edit.setText(default)
            line_edit.textChanged.connect(self._on_value_changed)
            
            self._values_layout.addRow(format_str + ":", line_edit)
            self._value_inputs[format_str] = line_edit
    
    def _on_text_changed(self):
        """Handle text change in main edit."""
        self._current_text = self._text_edit.toPlainText()
        self._analyze_format_strings()
    
    def _on_format_selected(self, current, previous):
        """Handle format string selection."""
        if current:
            format_str = current.data(Qt.UserRole)
            # Could highlight the format string in text editor
            
    def _on_value_changed(self):
        """Handle test value change."""
        self._update_preview()
    
    def _update_preview(self):
        """Update the live preview with current values."""
        text = self._current_text
        
        try:
            # Apply substitutions based on format type
            for format_str, input_widget in self._value_inputs.items():
                value = input_widget.text()
                
                if '%s' in format_str:
                    text = text.replace(format_str, value)
                elif '%d' in format_str:
                    try:
                        num_value = str(int(value)) if value.isdigit() else value
                        text = text.replace(format_str, num_value)
                    except ValueError:
                        text = text.replace(format_str, f"[INVALID: {value}]")
                elif '{' in format_str and '}' in format_str:
                    # For {0}, {1}, etc.
                    if format_str.count('{') == 1:
                        text = text.replace(format_str, value)
                else:
                    text = text.replace(format_str, value)
            
            self._preview_edit.setPlainText(text)
            
        except Exception as e:
            self._preview_edit.setPlainText(f"Error: {str(e)}")
    
    def _copy_result(self):
        """Copy the preview result to clipboard."""
        result = self._preview_edit.toPlainText()
        clipboard = self.parent().parent().app.clipboard() if hasattr(self.parent().parent(), 'app') else None
        
        try:
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText(result)
            QMessageBox.information(self, self.tr("Copied"), 
                                  self.tr("Result copied to clipboard."))
        except Exception:
            QMessageBox.warning(self, self.tr("Error"), 
                              self.tr("Could not copy to clipboard."))