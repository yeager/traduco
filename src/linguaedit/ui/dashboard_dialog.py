"""Project Dashboard — per-language progress, charts, CSV export.

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QScrollArea, QWidget, QGroupBox,
    QFileDialog, QDialogButtonBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QFrame,
)
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QBrush


# ── Chart widget (QPainter-based) ────────────────────────────────────

class _PieChartWidget(QWidget):
    """Simple pie chart drawn with QPainter."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(220, 220)
        self._slices: list[tuple[str, float, QColor]] = []

    def set_data(self, slices: list[tuple[str, float, QColor]]):
        """Set slices as [(label, value, color), ...]."""
        self._slices = slices
        self.update()

    def paintEvent(self, event):
        if not self._slices:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        size = min(w, h) - 40
        cx, cy = w / 2, h / 2
        rect = QRectF(cx - size / 2, cy - size / 2, size, size)

        total = sum(v for _, v, _ in self._slices)
        if total <= 0:
            painter.end()
            return

        start_angle = 90 * 16  # top
        for label, value, color in self._slices:
            span = int(round(value / total * 360 * 16))
            if span == 0:
                continue
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(color.darker(120), 1))
            painter.drawPie(rect, start_angle, -span)
            start_angle -= span

        # Legend
        lx = 8
        ly = h - len(self._slices) * 18 - 4
        painter.setPen(Qt.black if self.palette().color(self.backgroundRole()).lightness() > 128 else Qt.white)
        font = QFont()
        font.setPointSize(10)
        painter.setFont(font)
        for label, value, color in self._slices:
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(color, 1))
            painter.drawRect(lx, int(ly), 12, 12)
            painter.setPen(Qt.black if self.palette().color(self.backgroundRole()).lightness() > 128 else Qt.white)
            pct = value / total * 100 if total else 0
            painter.drawText(lx + 18, int(ly + 11), f"{label}: {int(value)} ({pct:.1f}%)")
            ly += 18

        painter.end()


class _BarChartWidget(QWidget):
    """Horizontal stacked bar chart per language."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(60)
        self._bars: list[tuple[str, list[tuple[float, QColor]]]] = []

    def set_data(self, bars: list[tuple[str, list[tuple[float, QColor]]]]):
        """bars = [(lang_label, [(value, color), ...]), ...]"""
        self._bars = bars
        self.setMinimumHeight(max(60, len(bars) * 32 + 20))
        self.update()

    def paintEvent(self, event):
        if not self._bars:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        bar_h = 22
        label_w = 100
        margin = 4
        y = margin

        text_color = Qt.black if self.palette().color(self.backgroundRole()).lightness() > 128 else Qt.white
        font = QFont()
        font.setPointSize(10)
        painter.setFont(font)

        for label, segments in self._bars:
            painter.setPen(text_color)
            painter.drawText(0, int(y), label_w, bar_h, Qt.AlignVCenter | Qt.AlignRight, label)

            total = sum(v for v, _ in segments)
            bx = label_w + 8
            bar_w = w - bx - margin
            if total > 0:
                for value, color in segments:
                    seg_w = value / total * bar_w
                    painter.setBrush(QBrush(color))
                    painter.setPen(QPen(color.darker(110), 1))
                    painter.drawRect(int(bx), int(y), int(seg_w), bar_h)
                    bx += seg_w

            y += bar_h + margin

        painter.end()


# ── Dashboard Dialog ─────────────────────────────────────────────────

class DashboardDialog(QDialog):
    """Project dashboard with progress bars and charts."""

    def __init__(self, parent=None, project_files: list[tuple[str, list]] | None = None):
        """
        project_files: [(language_label, entries_list), ...]
            where entries_list = [(msgid, msgstr, is_fuzzy), ...]
        """
        super().__init__(parent)
        self.setWindowTitle(self.tr("Project Dashboard"))
        self.setMinimumSize(750, 550)

        self._project_files = project_files or []
        self._stats: list[dict] = []

        self._compute_stats()
        self._build_ui()

    # ── Stats computation ────────────────────────────────────────

    def _compute_stats(self):
        self._stats = []
        for label, entries in self._project_files:
            total = len(entries)
            translated = sum(1 for _, msgstr, fuzzy in entries if msgstr and not fuzzy)
            fuzzy = sum(1 for _, msgstr, f in entries if f)
            untranslated = total - translated - fuzzy
            pct = translated / total * 100 if total else 0
            self._stats.append({
                "label": label,
                "total": total,
                "translated": translated,
                "fuzzy": fuzzy,
                "untranslated": untranslated,
                "pct": pct,
            })

    # ── UI ────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Summary
        total_strings = sum(s["total"] for s in self._stats)
        total_translated = sum(s["translated"] for s in self._stats)
        total_fuzzy = sum(s["fuzzy"] for s in self._stats)
        total_untranslated = sum(s["untranslated"] for s in self._stats)

        summary = QLabel(self.tr(
            "<h2>Project Overview</h2>"
            "<b>Total strings:</b> %d &nbsp; "
            "<span style='color:green'>Translated: %d</span> &nbsp; "
            "<span style='color:orange'>Fuzzy: %d</span> &nbsp; "
            "<span style='color:red'>Untranslated: %d</span>"
        ) % (total_strings, total_translated, total_fuzzy, total_untranslated))
        summary.setTextFormat(Qt.RichText)
        layout.addWidget(summary)

        # Charts row
        charts_layout = QHBoxLayout()

        # Pie chart
        self._pie = _PieChartWidget()
        self._pie.set_data([
            (self.tr("Translated"), total_translated, QColor(80, 180, 80)),
            (self.tr("Fuzzy"), total_fuzzy, QColor(230, 180, 40)),
            (self.tr("Untranslated"), total_untranslated, QColor(210, 70, 70)),
        ])
        charts_layout.addWidget(self._pie)

        # Bar chart
        self._bar = _BarChartWidget()
        bars = []
        for s in self._stats:
            bars.append((s["label"], [
                (s["translated"], QColor(80, 180, 80)),
                (s["fuzzy"], QColor(230, 180, 40)),
                (s["untranslated"], QColor(210, 70, 70)),
            ]))
        self._bar.set_data(bars)

        bar_scroll = QScrollArea()
        bar_scroll.setWidget(self._bar)
        bar_scroll.setWidgetResizable(True)
        charts_layout.addWidget(bar_scroll, 1)
        layout.addLayout(charts_layout)

        # Per-language progress bars
        progress_group = QGroupBox(self.tr("Per-Language Progress"))
        progress_layout = QVBoxLayout(progress_group)

        prog_scroll_inner = QWidget()
        prog_inner_layout = QVBoxLayout(prog_scroll_inner)
        prog_inner_layout.setSpacing(4)

        for s in self._stats:
            row = QHBoxLayout()
            lbl = QLabel(f"<b>{s['label']}</b>")
            lbl.setMinimumWidth(120)
            row.addWidget(lbl)

            pb = QProgressBar()
            pb.setMinimum(0)
            pb.setMaximum(s["total"] or 1)
            pb.setValue(s["translated"])
            pb.setFormat(f"{s['pct']:.1f}%  ({s['translated']}/{s['total']})")
            pb.setStyleSheet(
                "QProgressBar::chunk { background: qlineargradient("
                "x1:0, y1:0, x2:1, y2:0, stop:0 #4CAF50, stop:1 #66BB6A); }"
            )
            row.addWidget(pb, 1)

            detail = QLabel(
                self.tr("F:%d U:%d") % (s["fuzzy"], s["untranslated"])
            )
            detail.setStyleSheet("color: gray; font-size: 11px;")
            row.addWidget(detail)

            prog_inner_layout.addLayout(row)

        prog_inner_layout.addStretch()
        prog_scroll = QScrollArea()
        prog_scroll.setWidget(prog_scroll_inner)
        prog_scroll.setWidgetResizable(True)
        progress_layout.addWidget(prog_scroll)
        layout.addWidget(progress_group, 1)

        # Buttons
        btn_layout = QHBoxLayout()
        export_btn = QPushButton(self.tr("Export as CSV…"))
        export_btn.clicked.connect(self._export_csv)
        btn_layout.addWidget(export_btn)
        btn_layout.addStretch()
        close_btn = QPushButton(self.tr("Close"))
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    # ── CSV export ───────────────────────────────────────────────

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, self.tr("Export Statistics as CSV"), "project_stats.csv",
            self.tr("CSV files (*.csv)")
        )
        if not path:
            return

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Language", "Total", "Translated", "Fuzzy", "Untranslated", "% Translated"])
            for s in self._stats:
                writer.writerow([
                    s["label"], s["total"], s["translated"],
                    s["fuzzy"], s["untranslated"], f"{s['pct']:.1f}",
                ])

        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(self, self.tr("Export Complete"),
                                self.tr("Statistics exported to %s") % path)
