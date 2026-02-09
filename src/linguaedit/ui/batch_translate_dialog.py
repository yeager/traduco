"""Batch Machine Translate dialog — translate all untranslated entries at once.

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QGroupBox, QComboBox, QCheckBox,
    QDialogButtonBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QFormLayout, QLineEdit,
    QMessageBox, QApplication,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QBrush

from linguaedit.services.translator import translate, ENGINES, TranslationError


# ── Worker thread ────────────────────────────────────────────────────

class _BatchTranslateWorker(QThread):
    """Translate entries in a background thread."""

    progress = Signal(int, int)          # current, total
    entry_done = Signal(int, str, str)   # index, msgid, translation
    entry_error = Signal(int, str, str)  # index, msgid, error_message
    finished_all = Signal()

    def __init__(self, entries: list[tuple[int, str]], engine: str,
                 source: str, target: str, extra_kwargs: dict):
        super().__init__()
        self.entries = entries
        self.engine = engine
        self.source = source
        self.target = target
        self.extra_kwargs = extra_kwargs
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        total = len(self.entries)
        for i, (idx, msgid) in enumerate(self.entries):
            if self._cancel:
                break
            try:
                result = translate(
                    msgid, engine=self.engine,
                    source=self.source, target=self.target,
                    **self.extra_kwargs,
                )
                self.entry_done.emit(idx, msgid, result)
            except Exception as e:
                self.entry_error.emit(idx, msgid, str(e))
            self.progress.emit(i + 1, total)
        self.finished_all.emit()


# ── Dialog ───────────────────────────────────────────────────────────

class BatchTranslateDialog(QDialog):
    """Batch-translate all untranslated entries with preview."""

    # Signal emitted when user accepts: list of (entry_index, translation, mark_fuzzy)
    translations_accepted = Signal(list)

    def __init__(self, parent=None, entries: list[tuple[str, str, bool]] | None = None,
                 default_engine: str = "lingva", source_lang: str = "en",
                 target_lang: str = "sv", extra_kwargs: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Batch Machine Translate"))
        self.setMinimumSize(800, 550)

        self._all_entries = entries or []
        self._default_engine = default_engine
        self._source_lang = source_lang
        self._target_lang = target_lang
        self._extra_kwargs = extra_kwargs or {}
        self._worker: Optional[_BatchTranslateWorker] = None

        # Results: {entry_index: translation_text}
        self._results: dict[int, str] = {}
        self._errors: dict[int, str] = {}

        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Count untranslated
        untranslated = [(i, msgid) for i, (msgid, msgstr, fuzzy) in enumerate(self._all_entries)
                        if not msgstr and msgid]
        self._untranslated = untranslated

        info = QLabel(self.tr(
            "<b>%d</b> untranslated strings out of <b>%d</b> total."
        ) % (len(untranslated), len(self._all_entries)))
        info.setTextFormat(Qt.RichText)
        layout.addWidget(info)

        # Engine settings
        settings_group = QGroupBox(self.tr("Translation Settings"))
        settings_layout = QFormLayout(settings_group)

        self._engine_combo = QComboBox()
        engine_keys = list(ENGINES.keys())
        for k in engine_keys:
            v = ENGINES[k]
            suffix = "" if v["free"] else self.tr(" (API key)")
            self._engine_combo.addItem(f"{v['name']}{suffix}", k)
        try:
            self._engine_combo.setCurrentIndex(engine_keys.index(self._default_engine))
        except ValueError:
            pass
        settings_layout.addRow(self.tr("Engine:"), self._engine_combo)

        self._source_edit = QLineEdit(self._source_lang)
        settings_layout.addRow(self.tr("Source language:"), self._source_edit)

        self._target_edit = QLineEdit(self._target_lang)
        settings_layout.addRow(self.tr("Target language:"), self._target_edit)

        self._fuzzy_check = QCheckBox(self.tr("Mark results as fuzzy / needs work"))
        self._fuzzy_check.setChecked(True)
        settings_layout.addRow(self._fuzzy_check)

        layout.addWidget(settings_group)

        # Progress
        self._progress_bar = QProgressBar()
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFormat(self.tr("%v / %m"))
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)

        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

        # Preview table
        self._table = QTableWidget()
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels([
            self.tr("Source"), self.tr("Translation"), self.tr("Status"),
        ])
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        layout.addWidget(self._table, 1)

        # Buttons
        btn_layout = QHBoxLayout()

        self._translate_btn = QPushButton(self.tr("Translate All"))
        self._translate_btn.clicked.connect(self._start_translation)
        btn_layout.addWidget(self._translate_btn)

        self._cancel_btn = QPushButton(self.tr("Cancel Translation"))
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.clicked.connect(self._cancel_translation)
        btn_layout.addWidget(self._cancel_btn)

        btn_layout.addStretch()

        self._apply_btn = QPushButton(self.tr("Apply Results"))
        self._apply_btn.setEnabled(False)
        self._apply_btn.clicked.connect(self._apply_results)
        btn_layout.addWidget(self._apply_btn)

        close_btn = QPushButton(self.tr("Close"))
        close_btn.clicked.connect(self.reject)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

        # Pre-populate table
        self._populate_table()

    def _populate_table(self):
        self._table.setRowCount(len(self._untranslated))
        for row, (idx, msgid) in enumerate(self._untranslated):
            src = msgid[:200].replace("\n", " ")
            self._table.setItem(row, 0, QTableWidgetItem(src))
            self._table.setItem(row, 1, QTableWidgetItem(""))
            self._table.setItem(row, 2, QTableWidgetItem(self.tr("Pending")))

    # ── Translation ──────────────────────────────────────────────

    def _start_translation(self):
        if not self._untranslated:
            QMessageBox.information(self, self.tr("Nothing to Translate"),
                                    self.tr("All entries are already translated."))
            return

        engine_key = self._engine_combo.currentData()
        source = self._source_edit.text().strip() or "en"
        target = self._target_edit.text().strip() or "sv"

        self._results.clear()
        self._errors.clear()

        self._progress_bar.setVisible(True)
        self._progress_bar.setMaximum(len(self._untranslated))
        self._progress_bar.setValue(0)
        self._translate_btn.setEnabled(False)
        self._cancel_btn.setEnabled(True)
        self._apply_btn.setEnabled(False)
        self._status_label.setText(self.tr("Translating…"))

        self._worker = _BatchTranslateWorker(
            self._untranslated, engine_key, source, target, self._extra_kwargs,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.entry_done.connect(self._on_entry_done)
        self._worker.entry_error.connect(self._on_entry_error)
        self._worker.finished_all.connect(self._on_finished)
        self._worker.start()

    def _cancel_translation(self):
        if self._worker:
            self._worker.cancel()
            self._status_label.setText(self.tr("Cancelling…"))

    def _on_progress(self, current: int, total: int):
        self._progress_bar.setValue(current)

    def _on_entry_done(self, idx: int, msgid: str, translation: str):
        self._results[idx] = translation
        # Find row
        for row, (entry_idx, _) in enumerate(self._untranslated):
            if entry_idx == idx:
                self._table.setItem(row, 1, QTableWidgetItem(translation[:200]))
                status_item = QTableWidgetItem("✓")
                status_item.setForeground(QBrush(QColor(30, 130, 50)))
                self._table.setItem(row, 2, status_item)
                break

    def _on_entry_error(self, idx: int, msgid: str, error: str):
        self._errors[idx] = error
        for row, (entry_idx, _) in enumerate(self._untranslated):
            if entry_idx == idx:
                status_item = QTableWidgetItem(self.tr("Error"))
                status_item.setForeground(QBrush(QColor(200, 50, 50)))
                status_item.setToolTip(error)
                self._table.setItem(row, 2, status_item)
                break

    def _on_finished(self):
        self._translate_btn.setEnabled(True)
        self._cancel_btn.setEnabled(False)
        ok = len(self._results)
        fail = len(self._errors)
        self._status_label.setText(
            self.tr("Done. %d translated, %d errors.") % (ok, fail)
        )
        if ok > 0:
            self._apply_btn.setEnabled(True)

    # ── Apply ────────────────────────────────────────────────────

    def _apply_results(self):
        mark_fuzzy = self._fuzzy_check.isChecked()
        result_list = [
            (idx, text, mark_fuzzy) for idx, text in self._results.items()
        ]
        self.translations_accepted.emit(result_list)
        self.accept()
