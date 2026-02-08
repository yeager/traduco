"""Syntax highlighting for translation editor."""

from __future__ import annotations

import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont


class TranslationHighlighter(QSyntaxHighlighter):
    """Highlights format strings, HTML tags, and escape sequences."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rules: list[tuple[re.Pattern, QTextCharFormat]] = []
        self._build_rules()

    def _build_rules(self):
        # HTML tags - blue
        fmt_html = QTextCharFormat()
        fmt_html.setForeground(QColor("#6CA0DC"))
        self._rules.append((re.compile(r'<[^>]+>'), fmt_html))

        # Printf format strings - orange
        fmt_printf = QTextCharFormat()
        fmt_printf.setForeground(QColor("#E8A838"))
        fmt_printf.setFontWeight(QFont.Bold)
        self._rules.append((re.compile(r'%[\d$]*[sdiufxXoecpg%]'), fmt_printf))

        # Python format strings - orange
        fmt_python = QTextCharFormat()
        fmt_python.setForeground(QColor("#E8A838"))
        fmt_python.setFontWeight(QFont.Bold)
        self._rules.append((re.compile(r'\{[^}]*\}'), fmt_python))

        # Qt accelerator keys - magenta
        fmt_accel = QTextCharFormat()
        fmt_accel.setForeground(QColor("#C678DD"))
        fmt_accel.setFontWeight(QFont.Bold)
        self._rules.append((re.compile(r'&[A-Za-z]'), fmt_accel))

        # Escape sequences - gray
        fmt_escape = QTextCharFormat()
        fmt_escape.setForeground(QColor("#888888"))
        self._rules.append((re.compile(r'\\[nrt\\"\']'), fmt_escape))

    def highlightBlock(self, text: str):
        for pattern, fmt in self._rules:
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), fmt)
