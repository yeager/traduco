"""Concordance Search dialog — search entire Translation Memory for words/phrases."""

# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import re
from html import escape as html_escape

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel, QApplication,
    QAbstractItemView,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut

from linguaedit.services.tm import concordance_search


class ConcordanceDialog(QDialog):
    """Search the Translation Memory for concordance matches."""

    def __init__(self, parent=None, initial_query: str = "",
                 source_lang: str = "", target_lang: str = ""):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Concordance Search"))
        self.resize(800, 500)
        self._source_lang = source_lang
        self._target_lang = target_lang
        self._last_query = ""

        layout = QVBoxLayout(self)

        # Search bar
        search_layout = QHBoxLayout()
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText(self.tr("Enter word or phrase to search in TM…"))
        self._search_input.returnPressed.connect(self._do_search)
        search_layout.addWidget(self._search_input)

        self._search_btn = QPushButton(self.tr("Search"))
        self._search_btn.clicked.connect(self._do_search)
        search_layout.addWidget(self._search_btn)
        layout.addLayout(search_layout)

        # Status label
        self._status_label = QLabel()
        layout.addWidget(self._status_label)

        # Results table
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels([
            self.tr("Source"), self.tr("Translation"),
            self.tr("File"), self.tr("Score"),
        ])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self._table)

        # Hint
        hint = QLabel(self.tr("Double-click a row to copy translation to clipboard."))
        hint.setStyleSheet("color: gray; font-size: 10pt;")
        layout.addWidget(hint)

        if initial_query:
            self._search_input.setText(initial_query)
            self._do_search()
        else:
            self._search_input.setFocus()

    def _do_search(self):
        query = self._search_input.text().strip()
        if not query:
            return

        self._last_query = query
        results = concordance_search(
            query,
            source_lang=self._source_lang,
            target_lang=self._target_lang,
        )

        self._table.setRowCount(len(results))
        for i, match in enumerate(results):
            src_item = QTableWidgetItem(match.source)
            tgt_item = QTableWidgetItem(match.target)
            file_item = QTableWidgetItem(match.file_path or "")
            score_item = QTableWidgetItem(f"{match.similarity:.0%}")

            # Highlight matching text via tooltip with full text; bold via font
            for item, text in [(src_item, match.source), (tgt_item, match.target)]:
                if query.lower() in text.lower():
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)

            self._table.setItem(i, 0, src_item)
            self._table.setItem(i, 1, tgt_item)
            self._table.setItem(i, 2, file_item)
            self._table.setItem(i, 3, score_item)

        self._status_label.setText(
            self.tr('{} results found for "{}"').format(len(results), query)
        )

    def _on_double_click(self, index):
        row = index.row()
        tgt_item = self._table.item(row, 1)
        if tgt_item:
            QApplication.clipboard().setText(tgt_item.text())
            self._status_label.setText(self.tr("Translation copied to clipboard."))
