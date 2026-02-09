"""Segment Split/Merge dialogs for interactive entry manipulation."""

# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QDialogButtonBox, QMessageBox, QPlainTextEdit,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor


class SplitDialog(QDialog):
    """Interactive dialog for splitting a translation entry.

    The user clicks in the source text to place a split cursor position.
    """

    def __init__(self, source: str, target: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Split Entry"))
        self.resize(600, 400)
        self._source = source
        self._target = target
        self._split_pos: int | None = None

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(self.tr(
            "Click in the source text where you want to split, then press OK."
        )))

        # Source text (editable only for cursor placement)
        layout.addWidget(QLabel(self.tr("Source:")))
        self._source_edit = QPlainTextEdit(source)
        self._source_edit.setReadOnly(False)
        self._source_edit.setMaximumHeight(120)
        self._source_edit.cursorPositionChanged.connect(self._on_cursor_moved)
        # Prevent actual editing — revert changes
        self._source_edit.textChanged.connect(self._revert_text)
        layout.addWidget(self._source_edit)

        layout.addWidget(QLabel(self.tr("Target:")))
        self._target_edit = QPlainTextEdit(target)
        self._target_edit.setReadOnly(True)
        self._target_edit.setMaximumHeight(120)
        layout.addWidget(self._target_edit)

        # Preview
        self._preview_label = QLabel()
        self._preview_label.setWordWrap(True)
        self._preview_label.setStyleSheet("color: gray; font-size: 10pt;")
        layout.addWidget(self._preview_label)

        # Buttons
        self._buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self._buttons.accepted.connect(self._on_accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

        self._reverting = False

    def _revert_text(self):
        if self._reverting:
            return
        current = self._source_edit.toPlainText()
        if current != self._source:
            self._reverting = True
            cursor = self._source_edit.textCursor()
            pos = cursor.position()
            self._source_edit.setPlainText(self._source)
            cursor = self._source_edit.textCursor()
            cursor.setPosition(min(pos, len(self._source)))
            self._source_edit.setTextCursor(cursor)
            self._reverting = False

    def _on_cursor_moved(self):
        pos = self._source_edit.textCursor().position()
        if 0 < pos < len(self._source):
            self._split_pos = pos
            part1 = self._source[:pos].strip()
            part2 = self._source[pos:].strip()
            self._preview_label.setText(
                self.tr("Segment 1: \u201c{}\u201d  |  Segment 2: \u201c{}\u201d").format(
                    part1[:60] + ("…" if len(part1) > 60 else ""),
                    part2[:60] + ("…" if len(part2) > 60 else ""),
                )
            )
        else:
            self._split_pos = None
            self._preview_label.setText("")

    def _on_accept(self):
        if self._split_pos is None or self._split_pos <= 0 or self._split_pos >= len(self._source):
            QMessageBox.warning(
                self, self.tr("Split Entry"),
                self.tr("Place the cursor inside the source text to mark the split point."),
            )
            return
        self.accept()

    def get_result(self) -> tuple[tuple[str, str], tuple[str, str]] | None:
        """Return two (source, target) pairs, or None if cancelled."""
        if self._split_pos is None:
            return None
        pos = self._split_pos
        src1 = self._source[:pos].strip()
        src2 = self._source[pos:].strip()
        # Best-effort target split at same relative position
        ratio = pos / max(len(self._source), 1)
        tgt_pos = int(len(self._target) * ratio)
        # Try to find a nearby space/sentence boundary
        best = tgt_pos
        for offset in range(min(20, len(self._target))):
            for candidate in [tgt_pos + offset, tgt_pos - offset]:
                if 0 < candidate < len(self._target) and self._target[candidate] == ' ':
                    best = candidate
                    break
            else:
                continue
            break
        tgt1 = self._target[:best].strip()
        tgt2 = self._target[best:].strip()
        return (src1, tgt1), (src2, tgt2)


class MergePreviewDialog(QDialog):
    """Preview and confirm merging of multiple entries."""

    def __init__(self, entries: list[tuple[str, str]], parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Merge Entries"))
        self.resize(600, 400)
        self._entries = entries

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(self.tr("Preview of merged entry ({} segments):").format(len(entries))))

        merged_src = " ".join(src for src, _ in entries if src.strip())
        merged_tgt = " ".join(tgt for _, tgt in entries if tgt.strip())
        self._merged_source = merged_src
        self._merged_target = merged_tgt

        layout.addWidget(QLabel(self.tr("Source:")))
        src_edit = QPlainTextEdit(merged_src)
        src_edit.setReadOnly(True)
        src_edit.setMaximumHeight(100)
        layout.addWidget(src_edit)

        layout.addWidget(QLabel(self.tr("Translation:")))
        tgt_edit = QPlainTextEdit(merged_tgt)
        tgt_edit.setReadOnly(True)
        tgt_edit.setMaximumHeight(100)
        layout.addWidget(tgt_edit)

        # Original segments
        layout.addWidget(QLabel(self.tr("Original segments:")))
        for i, (s, t) in enumerate(entries, 1):
            lbl = QLabel(f"  {i}. {s[:80]}{'…' if len(s) > 80 else ''}")
            lbl.setStyleSheet("color: gray;")
            layout.addWidget(lbl)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_result(self) -> tuple[str, str] | None:
        return (self._merged_source, self._merged_target)
