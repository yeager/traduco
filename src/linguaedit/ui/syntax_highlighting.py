"""Syntax highlighting for translation editor.

Highlights format strings, HTML tags, escape sequences, and
misspelled words (red wavy underline).
"""
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import re

from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QSyntaxHighlighter, QTextCharFormat, QColor, QFont,
    QTextFormat,
)


class TranslationHighlighter(QSyntaxHighlighter):
    """Highlights format strings, HTML tags, escape sequences, and spell errors."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rules: list[tuple[re.Pattern, QTextCharFormat]] = []
        self._spell_errors: list = []  # list of SpellIssue objects
        self._build_rules()

    def set_spell_errors(self, errors: list):
        """Set the list of spell errors (SpellIssue objects with word and offset)."""
        self._spell_errors = errors or []

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
        # Apply syntax rules
        for pattern, fmt in self._rules:
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), fmt)

        # Apply spell check red underline
        if self._spell_errors:
            block_start = self.currentBlock().position()
            block_end = block_start + len(text)

            spell_fmt = QTextCharFormat()
            spell_fmt.setUnderlineColor(QColor(255, 60, 60))
            spell_fmt.setUnderlineStyle(QTextCharFormat.WaveUnderline)

            for issue in self._spell_errors:
                err_start = issue.offset
                err_end = err_start + len(issue.word)
                # Check if this error overlaps with current block
                if err_start < block_end and err_end > block_start:
                    local_start = max(0, err_start - block_start)
                    local_end = min(len(text), err_end - block_start)
                    if local_end > local_start:
                        self.setFormat(local_start, local_end - local_start, spell_fmt)

    def set_theme(self, theme: str = "light"):
        """Update highlighting colors for theme."""
        # Currently rules use fixed colors that work on both themes
        # Could be extended to use theme-specific colors
        pass
