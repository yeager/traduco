"""Animated circular progress ring widget (Apple Watch Activity Ring style).

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import (
    Qt, Property, QPropertyAnimation, QEasingCurve, QRectF, QPointF,
)
from PySide6.QtGui import (
    QPainter, QConicalGradient, QPen, QColor, QFont, QFontMetrics,
)


class ProgressRing(QWidget):
    """Circular progress indicator with animated transitions and gradient arc."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0.0        # 0–100
        self._display_value = 0.0  # animated value
        self._label_text = ""
        self._ring_width = 8
        self._bg_color = QColor(60, 60, 60, 80)
        self._start_color = QColor(76, 175, 80)    # green
        self._end_color = QColor(33, 150, 243)      # blue

        self._anim = QPropertyAnimation(self, b"displayValue")
        self._anim.setDuration(350)
        self._anim.setEasingCurve(QEasingCurve.InOutCubic)

        self.setMinimumSize(48, 48)
        self.setMaximumSize(120, 120)

    # ── Qt Property for animation ─────────────────────────────────

    def _get_display_value(self) -> float:
        return self._display_value

    def _set_display_value(self, v: float):
        self._display_value = v
        self.update()

    displayValue = Property(float, _get_display_value, _set_display_value)

    # ── Public API ────────────────────────────────────────────────

    def set_value(self, pct: float, label: str = ""):
        """Set progress (0–100) with smooth animation."""
        pct = max(0.0, min(100.0, pct))
        self._value = pct
        if label:
            self._label_text = label

        self._anim.stop()
        self._anim.setStartValue(self._display_value)
        self._anim.setEndValue(pct)
        self._anim.start()

    def set_colors(self, start: QColor, end: QColor):
        self._start_color = start
        self._end_color = end
        self.update()

    def set_ring_width(self, w: int):
        self._ring_width = w
        self.update()

    # ── Paint ─────────────────────────────────────────────────────

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        side = min(self.width(), self.height())
        margin = self._ring_width / 2 + 2
        rect = QRectF(margin, margin, side - 2 * margin, side - 2 * margin)
        center = QPointF(side / 2, side / 2)

        # Background ring
        bg_pen = QPen(self._bg_color, self._ring_width, Qt.SolidLine, Qt.RoundCap)
        painter.setPen(bg_pen)
        painter.drawEllipse(rect)

        # Gradient arc
        if self._display_value > 0:
            grad = QConicalGradient(center, 90)
            grad.setColorAt(0.0, self._start_color)
            grad.setColorAt(1.0, self._end_color)

            arc_pen = QPen(grad, self._ring_width, Qt.SolidLine, Qt.RoundCap)
            painter.setPen(arc_pen)

            span = int(-self._display_value / 100.0 * 360 * 16)
            painter.drawArc(rect, 90 * 16, span)

        # Center text
        pct_text = f"{int(self._display_value)}%"
        font = QFont()
        font.setPointSize(max(8, side // 5))
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(self.palette().text().color())
        painter.drawText(QRectF(0, 0, side, side), Qt.AlignCenter, pct_text)

        # Label below percentage
        if self._label_text:
            small_font = QFont()
            small_font.setPointSize(max(6, side // 8))
            painter.setFont(small_font)
            painter.setPen(QColor(160, 160, 160))
            label_rect = QRectF(0, side * 0.55, side, side * 0.3)
            painter.drawText(label_rect, Qt.AlignHCenter | Qt.AlignTop, self._label_text)

        painter.end()
