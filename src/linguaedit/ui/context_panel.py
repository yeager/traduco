"""Sticky Context Panel — live TM, glossary, and MT suggestions for current entry.

Copyright © 2025 Daniel Nylander <daniel@danielnylander.se>
SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QLabel, QPushButton,
    QGroupBox, QScrollArea, QFrame, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, Slot

from linguaedit.services.tm import lookup_tm
from linguaedit.services.glossary import get_terms
from linguaedit.services.translator import translate, ENGINES, TranslationError


class _CollapsibleSection(QGroupBox):
    """A QGroupBox that can be collapsed by clicking the title."""

    def __init__(self, title: str, parent: QWidget = None):
        super().__init__(title, parent)
        self.setCheckable(True)
        self.setChecked(True)
        self._content = QVBoxLayout()
        self._content.setContentsMargins(4, 4, 4, 4)
        self._content.setSpacing(2)
        super().setLayout(self._content)
        self.toggled.connect(self._on_toggled)

    def content_layout(self) -> QVBoxLayout:
        return self._content

    def _on_toggled(self, checked: bool):
        # Hide/show all child widgets
        for i in range(self._content.count()):
            item = self._content.itemAt(i)
            if item.widget():
                item.widget().setVisible(checked)

    def clear_content(self):
        while self._content.count():
            item = self._content.takeAt(0)
            if item.widget():
                item.widget().deleteLater()


class ContextPanel(QDockWidget):
    """Dock widget showing live TM, glossary, and MT suggestions."""

    apply_tm_requested = Signal(str)
    apply_mt_requested = Signal(str)
    apply_glossary_requested = Signal(str)

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Context"))
        self.setFeatures(
            QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable
        )
        self.setMinimumWidth(220)

        self._source_text = ""
        self._trans_engine = "lingva"
        self._trans_source = "en"
        self._trans_target = "sv"
        self._last_tm_matches = []
        self._last_mt_text = ""

        # Build UI
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # TM section
        self._tm_section = _CollapsibleSection(self.tr("Translation Memory"))
        self._tm_empty = QLabel(self.tr("<i>No matches</i>"))
        self._tm_empty.setStyleSheet("color: gray;")
        self._tm_section.content_layout().addWidget(self._tm_empty)
        layout.addWidget(self._tm_section)

        # Glossary section
        self._glossary_section = _CollapsibleSection(self.tr("Glossary"))
        self._glossary_empty = QLabel(self.tr("<i>No matching terms</i>"))
        self._glossary_empty.setStyleSheet("color: gray;")
        self._glossary_section.content_layout().addWidget(self._glossary_empty)
        layout.addWidget(self._glossary_section)

        # MT section
        self._mt_section = _CollapsibleSection(self.tr("Machine Translation"))
        self._mt_empty = QLabel(self.tr("<i>No suggestion</i>"))
        self._mt_empty.setStyleSheet("color: gray;")
        self._mt_section.content_layout().addWidget(self._mt_empty)
        layout.addWidget(self._mt_section)

        layout.addStretch()
        scroll.setWidget(container)
        self.setWidget(scroll)

    # ── Public API ────────────────────────────────────────────────

    def set_engine_settings(self, engine: str, source: str, target: str):
        self._trans_engine = engine
        self._trans_source = source
        self._trans_target = target

    @Slot(str)
    def update_for_entry(self, source_text: str):
        """Refresh all sections for the given source text."""
        self._source_text = source_text
        self._update_tm(source_text)
        self._update_glossary(source_text)
        self._update_mt(source_text)

    def get_best_tm_target(self) -> str | None:
        """Return the best TM match target text, or None."""
        if self._last_tm_matches:
            return self._last_tm_matches[0].target
        return None

    def get_mt_text(self) -> str:
        return self._last_mt_text

    # ── Internal ──────────────────────────────────────────────────

    def _update_tm(self, source: str):
        self._tm_section.clear_content()
        self._last_tm_matches = []

        if not source.strip():
            self._tm_empty = QLabel(self.tr("<i>No matches</i>"))
            self._tm_empty.setStyleSheet("color: gray;")
            self._tm_section.content_layout().addWidget(self._tm_empty)
            return

        matches = lookup_tm(source, threshold=0.6, max_results=5)
        self._last_tm_matches = matches

        if not matches:
            lbl = QLabel(self.tr("<i>No matches</i>"))
            lbl.setStyleSheet("color: gray;")
            self._tm_section.content_layout().addWidget(lbl)
            return

        for i, m in enumerate(matches):
            btn = QPushButton(f"[{m.similarity:.0%}] {m.target[:70]}{'…' if len(m.target) > 70 else ''}")
            btn.setToolTip(f"Source: {m.source}\nTarget: {m.target}")
            btn.setStyleSheet("text-align: left; padding: 3px;")
            btn.clicked.connect(lambda checked, t=m.target: self.apply_tm_requested.emit(t))
            self._tm_section.content_layout().addWidget(btn)

    def _update_glossary(self, source: str):
        self._glossary_section.clear_content()

        if not source.strip():
            lbl = QLabel(self.tr("<i>No matching terms</i>"))
            lbl.setStyleSheet("color: gray;")
            self._glossary_section.content_layout().addWidget(lbl)
            return

        words = source.lower().split()
        found = []
        try:
            all_terms = get_terms()
            for term in all_terms:
                src = term.source.lower()
                if any(src in w or w in src for w in words):
                    found.append(term)
        except Exception:
            pass

        if not found:
            lbl = QLabel(self.tr("<i>No matching terms</i>"))
            lbl.setStyleSheet("color: gray;")
            self._glossary_section.content_layout().addWidget(lbl)
            return

        for term in found[:10]:
            btn = QPushButton(f"{term.source} → {term.target}")
            btn.setStyleSheet("text-align: left; padding: 3px;")
            btn.clicked.connect(
                lambda checked, t=term.target: self.apply_glossary_requested.emit(t)
            )
            self._glossary_section.content_layout().addWidget(btn)

    def _update_mt(self, source: str):
        self._mt_section.clear_content()
        self._last_mt_text = ""

        if not source.strip():
            lbl = QLabel(self.tr("<i>No suggestion</i>"))
            lbl.setStyleSheet("color: gray;")
            self._mt_section.content_layout().addWidget(lbl)
            return

        try:
            result = translate(
                source,
                engine=self._trans_engine,
                source=self._trans_source,
                target=self._trans_target,
            )
            self._last_mt_text = result
        except (TranslationError, Exception):
            lbl = QLabel(self.tr("<i>MT unavailable</i>"))
            lbl.setStyleSheet("color: gray;")
            self._mt_section.content_layout().addWidget(lbl)
            return

        btn = QPushButton(result[:100] + ("…" if len(result) > 100 else ""))
        btn.setToolTip(result)
        btn.setStyleSheet("text-align: left; padding: 3px;")
        btn.clicked.connect(lambda checked, t=result: self.apply_mt_requested.emit(t))
        self._mt_section.content_layout().addWidget(btn)
