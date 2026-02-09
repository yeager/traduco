"""Color-coded minimap widget for translation entry overview.

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QMouseEvent,
)


class MinimapWidget(QWidget):
    """Vertical strip showing color-coded status for every entry.

    Colors:
      Green  = translated
      Red    = untranslated
      Orange = fuzzy
      Blue   = reviewed

    Clicking a block jumps to that entry.  A semi-transparent overlay
    marks the current viewport region.
    """

    jump_to_entry = Signal(int)

    # Status colors
    COLOR_TRANSLATED = QColor(76, 175, 80)       # green
    COLOR_UNTRANSLATED = QColor(229, 57, 53)      # red
    COLOR_FUZZY = QColor(255, 152, 0)             # orange
    COLOR_REVIEWED = QColor(33, 150, 243)         # blue
    COLOR_BG = QColor(40, 40, 40, 60)
    COLOR_VIEWPORT = QColor(255, 255, 255, 50)
    COLOR_CURRENT = QColor(255, 255, 255, 180)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(24)
        self.setMinimumHeight(60)

        self._entries: list[tuple[str, str, bool]] = []
        self._review_set: set[int] = set()  # indices marked as reviewed
        self._current_index = 0
        self._viewport_start = 0  # first visible row
        self._viewport_count = 20  # visible rows

        self.setToolTip(self.tr("Minimap – click to jump"))
        self.setCursor(Qt.PointingHandCursor)

    # ── Public API ────────────────────────────────────────────────

    def set_entries(self, entries: list[tuple[str, str, bool]]):
        self._entries = entries
        self.update()

    def set_current_index(self, idx: int):
        self._current_index = idx
        self.update()

    def set_review_set(self, reviewed: set[int]):
        self._review_set = reviewed
        self.update()

    def set_viewport(self, start: int, count: int):
        self._viewport_start = start
        self._viewport_count = count
        self.update()

    # ── Paint ─────────────────────────────────────────────────────

    def paintEvent(self, event):  # noqa: N802
        if not self._entries:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)

        w = self.width()
        h = self.height()
        n = len(self._entries)

        # Background
        painter.fillRect(self.rect(), QBrush(self.COLOR_BG))

        # Block height (float for precision)
        bh = max(1.0, h / n)

        for i, (source, target, is_fuzzy) in enumerate(self._entries):
            if i in self._review_set:
                color = self.COLOR_REVIEWED
            elif not target.strip():
                color = self.COLOR_UNTRANSLATED
            elif is_fuzzy:
                color = self.COLOR_FUZZY
            else:
                color = self.COLOR_TRANSLATED

            y = int(i * bh)
            block_h = max(1, int(bh))
            painter.fillRect(2, y, w - 4, block_h, color)

        # Viewport indicator
        if n > 0:
            vy = int(self._viewport_start * bh)
            vh = max(4, int(self._viewport_count * bh))
            painter.fillRect(0, vy, w, vh, QBrush(self.COLOR_VIEWPORT))

        # Current entry marker
        if 0 <= self._current_index < n:
            cy = int(self._current_index * bh)
            painter.setPen(QPen(self.COLOR_CURRENT, 2))
            painter.drawLine(0, cy, w, cy)

        painter.end()

    # ── Mouse ─────────────────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton and self._entries:
            n = len(self._entries)
            bh = self.height() / n if n else 1
            idx = int(event.position().y() / bh)
            idx = max(0, min(idx, n - 1))
            self.jump_to_entry.emit(idx)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() & Qt.LeftButton and self._entries:
            n = len(self._entries)
            bh = self.height() / n if n else 1
            idx = int(event.position().y() / bh)
            idx = max(0, min(idx, n - 1))
            self.jump_to_entry.emit(idx)
