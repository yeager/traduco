"""Syntax highlighting för translation editor."""

from __future__ import annotations

import re
from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QSyntaxHighlighter, QTextDocument, QTextCharFormat, QFont, QColor
)


class TranslationHighlighter(QSyntaxHighlighter):
    """Syntax highlighter för översättningstext."""
    
    def __init__(self, document: QTextDocument):
        super().__init__(document)
        self._setup_formats()
        self._setup_patterns()
    
    def _setup_formats(self):
        """Skapar textformat för olika element."""
        # HTML-taggar (blå)
        self.html_format = QTextCharFormat()
        self.html_format.setForeground(QColor(0, 100, 200))  # Blå
        self.html_format.setFontWeight(QFont.Bold)
        
        # Format strings (orange)
        self.format_string_format = QTextCharFormat()
        self.format_string_format.setForeground(QColor(255, 140, 0))  # Orange
        self.format_string_format.setFontWeight(QFont.Bold)
        
        # Escaped characters (grå)
        self.escaped_format = QTextCharFormat()
        self.escaped_format.setForeground(QColor(128, 128, 128))  # Grå
        
        # Placeholders (gul bakgrund)
        self.placeholder_format = QTextCharFormat()
        self.placeholder_format.setForeground(QColor(139, 69, 19))  # Brun
        self.placeholder_format.setBackground(QColor(255, 255, 200))  # Ljusgul bakgrund
        
        # Variabler (lila)
        self.variable_format = QTextCharFormat()
        self.variable_format.setForeground(QColor(128, 0, 128))  # Lila
        self.variable_format.setFontItalic(True)
    
    def _setup_patterns(self):
        """Definierar regex-patterns för highlighting."""
        self.patterns = [
            # HTML-taggar (inkluderar self-closing och med attribut)
            (r'<[^>]+/?>', self.html_format),
            
            # Printf-style format strings
            (r'%[-+0-9]*[sdioxXeEfFgGaAcpn%]', self.format_string_format),
            
            # Python format strings {0}, {name}, {0:d}
            (r'\{[^}]*\}', self.format_string_format),
            
            # .NET format strings {0}, {0:D2}
            (r'\{[0-9]+(?::[^}]*)?\}', self.format_string_format),
            
            # Qt format strings %1, %2, etc.
            (r'%[0-9]+', self.format_string_format),
            
            # ICU MessageFormat {0,number}, {name,date,short}
            (r'\{[^,}]+(?:,[^,}]+(?:,[^}]+)?)?\}', self.format_string_format),
            
            # Escaped characters
            (r'\\[nrtfbav\\"]', self.escaped_format),
            (r'\\x[0-9a-fA-F]{2}', self.escaped_format),
            (r'\\u[0-9a-fA-F]{4}', self.escaped_format),
            (r'\\U[0-9a-fA-F]{8}', self.escaped_format),
            (r'\\[0-9]{1,3}', self.escaped_format),
            
            # Mustache/Handlebars {{variable}}
            (r'\{\{[^}]+\}\}', self.variable_format),
            
            # Angular/Vue {{variable}}
            (r'\{\{\s*[^}]+\s*\}\}', self.variable_format),
            
            # PHP/Twig style {{variable}}
            (r'\$\{[^}]+\}', self.variable_format),
            
            # Environment variables $VAR, ${VAR}
            (r'\$[A-Za-z_][A-Za-z0-9_]*', self.variable_format),
            (r'\$\{[A-Za-z_][A-Za-z0-9_]*\}', self.variable_format),
        ]
    
    def highlightBlock(self, text: str):
        """Highlightar en textblock."""
        if not text:
            return
        
        for pattern, format_obj in self.patterns:
            expression = re.compile(pattern)
            
            for match in expression.finditer(text):
                start = match.start()
                length = match.end() - match.start()
                self.setFormat(start, length, format_obj)
        
        # Special handling för nästlade HTML-taggar
        self._highlight_nested_html(text)
        
        # Highlight mismatched brackets/braces
        self._highlight_mismatched_brackets(text)
    
    def _highlight_nested_html(self, text: str):
        """Highlightar nästlade HTML-taggar med olika intensitet."""
        # Hitta öppnande taggar
        open_tags = []
        tag_pattern = re.compile(r'<(/?)([^>\s]+)[^>]*>')
        
        for match in tag_pattern.finditer(text):
            is_closing = bool(match.group(1))
            tag_name = match.group(2).lower()
            
            if is_closing:
                # Closing tag - matcha med öppnande
                if open_tags and open_tags[-1][1] == tag_name:
                    open_tags.pop()
                else:
                    # Obalanserad closing tag - highlight röd
                    error_format = QTextCharFormat()
                    error_format.setForeground(QColor(255, 0, 0))
                    error_format.setBackground(QColor(255, 200, 200))
                    self.setFormat(match.start(), match.end() - match.start(), error_format)
            else:
                # Self-closing eller opening tag
                if not match.group(0).endswith('/>'):
                    # Inte self-closing
                    if tag_name not in ['br', 'hr', 'img', 'input', 'meta', 'link']:
                        open_tags.append((match.start(), tag_name))
    
    def _highlight_mismatched_brackets(self, text: str):
        """Highlightar obalanserade parenteser/brackets."""
        brackets = {'(': ')', '[': ']', '{': '}'}
        stack = []
        
        for i, char in enumerate(text):
            if char in brackets:
                stack.append((char, i))
            elif char in brackets.values():
                if stack:
                    open_char, open_pos = stack[-1]
                    if brackets.get(open_char) == char:
                        stack.pop()
                    else:
                        # Mismatch
                        error_format = QTextCharFormat()
                        error_format.setForeground(QColor(255, 0, 0))
                        error_format.setBackground(QColor(255, 200, 200))
                        self.setFormat(i, 1, error_format)
                else:
                    # Closing utan opening
                    error_format = QTextCharFormat()
                    error_format.setForeground(QColor(255, 0, 0))
                    error_format.setBackground(QColor(255, 200, 200))
                    self.setFormat(i, 1, error_format)
        
        # Highlight ej stängda brackets
        for open_char, pos in stack:
            error_format = QTextCharFormat()
            error_format.setForeground(QColor(255, 0, 0))
            error_format.setBackground(QColor(255, 200, 200))
            self.setFormat(pos, 1, error_format)
    
    def set_theme(self, theme: str = "light"):
        """Ställer in färgtema."""
        if theme == "dark":
            # Mörkt tema
            self.html_format.setForeground(QColor(100, 149, 237))  # Ljusblå
            self.format_string_format.setForeground(QColor(255, 165, 0))  # Orange
            self.escaped_format.setForeground(QColor(169, 169, 169))  # Ljusgrå
            self.placeholder_format.setForeground(QColor(210, 180, 140))  # Ljusbrun
            self.placeholder_format.setBackground(QColor(60, 60, 40))  # Mörk gul
            self.variable_format.setForeground(QColor(221, 160, 221))  # Ljuslila
        else:
            # Ljust tema (default)
            self._setup_formats()