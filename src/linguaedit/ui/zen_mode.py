# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2024-2026 LinguaEdit contributors
"""Zen Translation Mode — distraction-free translation overlay."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QTextEdit,
    QLabel, QPushButton, QProgressBar, QFrame,
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QKeySequence, QShortcut, QColor


class ZenModeWidget(QWidget):
    """Full-window overlay for distraction-free translation."""

    exit_requested = Signal()
    save_and_next = Signal()            # Tab / Ctrl+Enter → next untranslated
    save_and_next_entry = Signal()      # just next entry
    save_and_prev_entry = Signal()      # Shift+Tab → previous entry
    entry_changed = Signal(str)         # translation text changed

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ZenModeWidget")
        self._build_ui()
        self._setup_shortcuts()

    # ── UI ────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Progress bar (very thin)
        self._progress = QProgressBar()
        self._progress.setMaximumHeight(4)
        self._progress.setTextVisible(False)
        self._progress.setStyleSheet(
            "QProgressBar { border: none; background: #e0e0e0; }"
            "QProgressBar::chunk { background: #4caf50; }"
        )
        layout.addWidget(self._progress)

        # Nav bar
        nav = QFrame()
        nav.setMaximumHeight(36)
        nav.setStyleSheet(
            "QFrame { background: palette(window); border-bottom: 1px solid palette(mid); }"
        )
        nav_layout = QHBoxLayout(nav)
        nav_layout.setContentsMargins(12, 2, 12, 2)
        nav_layout.setSpacing(8)

        self._prev_btn = QPushButton("◀")
        self._prev_btn.setMaximumWidth(32)
        self._prev_btn.setToolTip(self.tr("Previous entry"))
        self._prev_btn.clicked.connect(self.save_and_prev_entry)
        nav_layout.addWidget(self._prev_btn)

        self._counter_label = QLabel("0 / 0")
        self._counter_label.setStyleSheet("font-weight: bold;")
        nav_layout.addWidget(self._counter_label)

        self._next_btn = QPushButton("▶")
        self._next_btn.setMaximumWidth(32)
        self._next_btn.setToolTip(self.tr("Next entry"))
        self._next_btn.clicked.connect(self.save_and_next_entry)
        nav_layout.addWidget(self._next_btn)

        nav_layout.addStretch()

        self._status_label = QLabel()
        nav_layout.addWidget(self._status_label)

        self._skip_btn = QPushButton(self.tr("Next untranslated ▶▶"))
        self._skip_btn.setToolTip(self.tr("Skip to next untranslated (Ctrl+Enter)"))
        self._skip_btn.clicked.connect(self.save_and_next)
        nav_layout.addWidget(self._skip_btn)

        exit_btn = QPushButton(self.tr("Exit Zen"))
        exit_btn.clicked.connect(self.exit_requested)
        nav_layout.addWidget(exit_btn)

        layout.addWidget(nav)

        # Content area
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(48, 24, 48, 24)
        content_layout.setSpacing(12)

        src_label = QLabel(self.tr("<b>Source text</b>"))
        content_layout.addWidget(src_label)

        self._source_view = QTextEdit()
        self._source_view.setReadOnly(True)
        self._source_view.setFrameShape(QFrame.StyledPanel)
        self._source_view.setStyleSheet("QTextEdit { background: palette(alternate-base); }")
        font = QFont()
        font.setPointSize(14)
        self._source_view.setFont(font)
        content_layout.addWidget(self._source_view, 2)

        trans_label = QLabel(self.tr("<b>Translation</b>"))
        content_layout.addWidget(trans_label)

        self._trans_view = QPlainTextEdit()
        self._trans_view.setFrameShape(QFrame.StyledPanel)
        self._trans_view.setFont(font)
        self._trans_view.textChanged.connect(lambda: self.entry_changed.emit(self._trans_view.toPlainText()))
        content_layout.addWidget(self._trans_view, 3)

        layout.addWidget(content, 1)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Escape"), self, self.exit_requested.emit)
        QShortcut(QKeySequence("Ctrl+Return"), self, self.save_and_next.emit)

    # ── Public API ────────────────────────────────────────────────

    def set_entry(self, source: str, translation: str, index: int, total: int,
                  translated_count: int, status: str):
        """Load an entry into the zen view."""
        self._source_view.setPlainText(source)
        self._trans_view.blockSignals(True)
        self._trans_view.setPlainText(translation)
        self._trans_view.blockSignals(False)
        self._counter_label.setText(f"{index + 1} / {total}")
        pct = int(translated_count / total * 100) if total else 0
        self._progress.setValue(pct)
        self._progress.setMaximum(100)

        # Status badge
        colors = {"translated": "#4caf50", "fuzzy": "#ff9800", "untranslated": "#f44336"}
        color = colors.get(status, "#999")
        self._status_label.setText(
            f"<span style='background:{color}; color:white; padding:2px 8px; "
            f"border-radius:3px;'>{status.capitalize()}</span>"
        )
        self._status_label.setTextFormat(Qt.RichText)

        # Focus translation
        self._trans_view.setFocus()
        cursor = self._trans_view.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self._trans_view.setTextCursor(cursor)

    def get_translation(self) -> str:
        return self._trans_view.toPlainText()

    def keyPressEvent(self, event):
        """Handle Tab for save+next untranslated, Shift+Tab for prev."""
        if event.key() == Qt.Key_Tab and not event.modifiers():
            self.save_and_next.emit()
            return
        if event.key() == Qt.Key_Backtab or (event.key() == Qt.Key_Tab and event.modifiers() & Qt.ShiftModifier):
            self.save_and_prev_entry.emit()
            return
        super().keyPressEvent(event)
