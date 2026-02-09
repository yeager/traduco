# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2024-2026 LinguaEdit contributors
"""Custom delegate for painting colored status borders in the entry list."""

from __future__ import annotations

from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QTreeWidgetItem
from PySide6.QtCore import Qt, QRect, QModelIndex
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QIcon


# Border colors
_BORDER_UNTRANSLATED = QColor(220, 50, 50)
_BORDER_FUZZY = QColor(255, 152, 0)
_BORDER_TRANSLATED = QColor(76, 175, 80)
_BORDER_WARNING = QColor(255, 152, 0)

# Background colors
_BG_UNTRANSLATED = QColor(255, 235, 235)
_BG_FUZZY = QColor(255, 248, 225)
_BG_TRANSLATED = QColor(255, 255, 255, 0)  # transparent / default

# Dark theme variants
_DARK_BG_UNTRANSLATED = QColor(80, 30, 30)
_DARK_BG_FUZZY = QColor(80, 65, 20)
_DARK_BG_TRANSLATED = QColor(0, 0, 0, 0)


class EntryItemDelegate(QStyledItemDelegate):
    """Paints colored left borders and status-aware backgrounds on entry rows."""

    # Status constants stored in UserRole+1
    STATUS_TRANSLATED = 0
    STATUS_UNTRANSLATED = 1
    STATUS_FUZZY = 2
    STATUS_WARNING = 3

    def __init__(self, parent=None, dark_mode=False):
        super().__init__(parent)
        self._dark_mode = dark_mode

    def set_dark_mode(self, dark: bool):
        self._dark_mode = dark

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        # Get status from item data
        status = index.data(Qt.UserRole + 1)
        if status is None:
            status = self.STATUS_TRANSLATED

        # Determine colors
        if status == self.STATUS_UNTRANSLATED:
            border_color = _BORDER_UNTRANSLATED
            bg_color = _DARK_BG_UNTRANSLATED if self._dark_mode else _BG_UNTRANSLATED
            border_width = 4
        elif status == self.STATUS_FUZZY:
            border_color = _BORDER_FUZZY
            bg_color = _DARK_BG_FUZZY if self._dark_mode else _BG_FUZZY
            border_width = 3
        elif status == self.STATUS_WARNING:
            border_color = _BORDER_WARNING
            bg_color = _DARK_BG_FUZZY if self._dark_mode else _BG_FUZZY
            border_width = 3
        else:
            border_color = _BORDER_TRANSLATED
            bg_color = _DARK_BG_TRANSLATED if self._dark_mode else _BG_TRANSLATED
            border_width = 2

        painter.save()

        # Draw background
        if bg_color.alpha() > 0:
            painter.fillRect(option.rect, QBrush(bg_color))

        # Draw left border (only on first column)
        if index.column() == 0:
            border_rect = QRect(option.rect.left(), option.rect.top(),
                                border_width, option.rect.height())
            painter.fillRect(border_rect, QBrush(border_color))

        # Draw warning icon for entries with warnings
        if status == self.STATUS_WARNING and index.column() == 0:
            icon_rect = QRect(option.rect.left() + border_width + 2,
                              option.rect.top() + (option.rect.height() - 12) // 2,
                              12, 12)
            painter.setPen(QPen(_BORDER_WARNING, 1.5))
            # Simple triangle warning
            painter.drawText(icon_rect, Qt.AlignCenter, "⚠")

        painter.restore()

        # Draw the rest with the default painter
        super().paint(painter, option, index)
