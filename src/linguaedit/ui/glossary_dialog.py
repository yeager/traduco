"""Glossary Management Dialog for LinguaEdit."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import List, Dict, Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QFileDialog, QDialogButtonBox,
    QGroupBox, QTextEdit, QComboBox, QProgressBar,
    QAbstractItemView, QMenu, QFrame
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QAction, QIcon, QKeySequence, QShortcut

from linguaedit.services.glossary import (
    get_terms, add_term, remove_term, GlossaryTerm,
    _load_glossary, _save_glossary
)


class GlossaryImportThread(QThread):
    """Thread for importing glossary from CSV."""
    
    progress_updated = Signal(int, str)  # progress, status
    import_completed = Signal(dict)  # results
    
    def __init__(self, file_path: str, language: str = ""):
        super().__init__()
        self.file_path = file_path
        self.language = language
        
    def run(self):
        """Import glossary terms from CSV."""
        results = {"imported": 0, "errors": 0, "details": []}
        
        try:
            with open(self.file_path, 'r', encoding='utf-8') as csvfile:
                # Try to detect if file has header
                sample = csvfile.read(1024)
                csvfile.seek(0)
                has_header = csv.Sniffer().has_header(sample)
                
                reader = csv.reader(csvfile)
                if has_header:
                    next(reader)  # Skip header
                
                total_rows = sum(1 for _ in reader)
                csvfile.seek(0)
                if has_header:
                    next(reader)
                    
                for i, row in enumerate(reader):
                    self.progress_updated.emit(
                        int(i * 100 / total_rows) if total_rows > 0 else 100,
                        f"Importing term {i+1}/{total_rows}"
                    )
                    
                    try:
                        if len(row) >= 2:
                            source = row[0].strip()
                            target = row[1].strip()
                            notes = row[2].strip() if len(row) > 2 else ""
                            domain = row[3].strip() if len(row) > 3 else ""
                            
                            if source and target:
                                add_term(source, target, notes, domain)
                                results["imported"] += 1
                                
                    except Exception as e:
                        results["errors"] += 1
                        results["details"].append(f"Row {i+1}: {str(e)}")
                        
        except Exception as e:
            results["errors"] += 1
            results["details"] = [f"File error: {str(e)}"]
            
        self.import_completed.emit(results)


class GlossaryDialog(QDialog):
    """Glossary management dialog."""
    
    # Signal emitted when glossary is modified
    glossary_changed = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Glossary Management"))
        self.setMinimumSize(800, 600)
        
        self._terms: List[GlossaryTerm] = []
        self._filtered_terms: List[GlossaryTerm] = []
        self._import_thread: Optional[GlossaryImportThread] = None
        
        self._build_ui()
        self._setup_connections()
        self._load_terms()
        self._setup_shortcuts()
        
    def _build_ui(self):
        layout = QVBoxLayout(self)
        
        # Search and filter bar
        search_group = QGroupBox(self.tr("Search & Filter"))
        search_layout = QHBoxLayout(search_group)
        
        search_layout.addWidget(QLabel(self.tr("Search:")))
        self._search_entry = QLineEdit()
        self._search_entry.setPlaceholderText(self.tr("Search in source or target..."))
        self._search_entry.setClearButtonEnabled(True)
        search_layout.addWidget(self._search_entry, 1)
        
        search_layout.addWidget(QLabel(self.tr("Domain:")))
        self._domain_filter = QComboBox()
        self._domain_filter.setMinimumWidth(150)
        search_layout.addWidget(self._domain_filter)
        
        layout.addWidget(search_group)
        
        # Glossary table
        table_group = QGroupBox(self.tr("Terms"))
        table_layout = QVBoxLayout(table_group)
        
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels([
            self.tr("Source"), self.tr("Target"), self.tr("Notes"), self.tr("Domain")
        ])
        
        # Table settings
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._table.setSortingEnabled(True)
        
        # Header settings
        header = self._table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        
        table_layout.addWidget(self._table)
        layout.addWidget(table_group)
        
        # Term editing area
        edit_group = QGroupBox(self.tr("Edit Term"))
        edit_layout = QGridLayout(edit_group)
        
        # Source
        edit_layout.addWidget(QLabel(self.tr("Source:")), 0, 0)
        self._source_entry = QLineEdit()
        edit_layout.addWidget(self._source_entry, 0, 1)
        
        # Target
        edit_layout.addWidget(QLabel(self.tr("Target:")), 0, 2)
        self._target_entry = QLineEdit()
        edit_layout.addWidget(self._target_entry, 0, 3)
        
        # Notes
        edit_layout.addWidget(QLabel(self.tr("Notes:")), 1, 0)
        self._notes_entry = QTextEdit()
        self._notes_entry.setMaximumHeight(80)
        edit_layout.addWidget(self._notes_entry, 1, 1, 1, 2)
        
        # Domain
        edit_layout.addWidget(QLabel(self.tr("Domain:")), 1, 3)
        self._domain_entry = QComboBox()
        self._domain_entry.setEditable(True)
        self._domain_entry.setMinimumWidth(120)
        edit_layout.addWidget(self._domain_entry, 1, 4)
        
        layout.addWidget(edit_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        # Edit buttons
        self._add_btn = QPushButton(self.tr("Add"))
        self._update_btn = QPushButton(self.tr("Update"))
        self._delete_btn = QPushButton(self.tr("Delete"))
        self._clear_btn = QPushButton(self.tr("Clear"))
        
        button_layout.addWidget(self._add_btn)
        button_layout.addWidget(self._update_btn)
        button_layout.addWidget(self._delete_btn)
        button_layout.addWidget(self._clear_btn)
        
        button_layout.addWidget(self._create_separator())
        
        # Import/Export buttons
        self._import_btn = QPushButton(self.tr("Import CSV..."))
        self._export_btn = QPushButton(self.tr("Export CSV..."))
        
        button_layout.addWidget(self._import_btn)
        button_layout.addWidget(self._export_btn)
        
        button_layout.addStretch()
        
        # Dialog buttons
        self._button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_layout.addWidget(self._button_box)
        
        layout.addLayout(button_layout)
        
        # Progress bar (hidden by default)
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)
        
        # Status label
        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self._status_label)
        
    def _create_separator(self) -> QFrame:
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setFrameShadow(QFrame.Sunken)
        return separator
        
    def _setup_connections(self):
        """Setup signal connections."""
        # Search and filter
        self._search_entry.textChanged.connect(self._apply_filter)
        self._domain_filter.currentTextChanged.connect(self._apply_filter)
        
        # Table selection
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        self._table.itemDoubleClicked.connect(self._on_item_double_clicked)
        
        # Edit buttons
        self._add_btn.clicked.connect(self._add_term)
        self._update_btn.clicked.connect(self._update_term)
        self._delete_btn.clicked.connect(self._delete_term)
        self._clear_btn.clicked.connect(self._clear_fields)
        
        # Import/Export
        self._import_btn.clicked.connect(self._import_csv)
        self._export_btn.clicked.connect(self._export_csv)
        
        # Dialog
        self._button_box.rejected.connect(self.reject)
        
    def _setup_shortcuts(self):
        """Setup keyboard shortcuts."""
        QShortcut(QKeySequence("Ctrl+N"), self, self._add_term)
        QShortcut(QKeySequence("Del"), self, self._delete_term)
        QShortcut(QKeySequence("Ctrl+F"), self, lambda: self._search_entry.setFocus())
        
    def _load_terms(self):
        """Load all glossary terms."""
        self._terms = get_terms()
        self._filtered_terms = self._terms.copy()
        self._update_table()
        self._update_domain_filter()
        self._update_status()
        
    def _update_table(self):
        """Update the table with current terms."""
        self._table.setRowCount(len(self._filtered_terms))
        
        for row, term in enumerate(self._filtered_terms):
            # Source
            item = QTableWidgetItem(term.source)
            item.setData(Qt.UserRole, term)
            self._table.setItem(row, 0, item)
            
            # Target
            self._table.setItem(row, 1, QTableWidgetItem(term.target))
            
            # Notes
            self._table.setItem(row, 2, QTableWidgetItem(term.notes))
            
            # Domain
            self._table.setItem(row, 3, QTableWidgetItem(term.domain))
            
    def _update_domain_filter(self):
        """Update domain filter combobox."""
        current = self._domain_filter.currentText()
        
        self._domain_filter.clear()
        self._domain_filter.addItem(self.tr("All domains"), "")
        
        domains = set()
        for term in self._terms:
            if term.domain:
                domains.add(term.domain)
                
        for domain in sorted(domains):
            self._domain_filter.addItem(domain, domain)
            
        # Restore selection if possible
        index = self._domain_filter.findText(current)
        if index >= 0:
            self._domain_filter.setCurrentIndex(index)
            
    def _update_status(self):
        """Update status label."""
        if self._filtered_terms != self._terms:
            self._status_label.setText(
                self.tr("Showing %d of %d terms") % (len(self._filtered_terms), len(self._terms))
            )
        else:
            self._status_label.setText(self.tr("%d terms") % len(self._terms))
            
    def _apply_filter(self):
        """Apply search and domain filters."""
        search_text = self._search_entry.text().lower()
        domain_filter = self._domain_filter.currentData()
        
        self._filtered_terms = []
        
        for term in self._terms:
            # Search filter
            if search_text:
                if (search_text not in term.source.lower() and 
                    search_text not in term.target.lower() and
                    search_text not in term.notes.lower()):
                    continue
                    
            # Domain filter
            if domain_filter:
                if term.domain != domain_filter:
                    continue
                    
            self._filtered_terms.append(term)
            
        self._update_table()
        self._update_status()
        
    def _on_selection_changed(self):
        """Handle table selection changes."""
        current_row = self._table.currentRow()
        
        if current_row >= 0 and current_row < len(self._filtered_terms):
            term = self._filtered_terms[current_row]
            self._load_term_to_fields(term)
            self._update_btn.setEnabled(True)
            self._delete_btn.setEnabled(True)
        else:
            self._update_btn.setEnabled(False)
            self._delete_btn.setEnabled(False)
            
    def _on_item_double_clicked(self, item):
        """Handle double-click on table item."""
        if item:
            self._update_term()
            
    def _load_term_to_fields(self, term: GlossaryTerm):
        """Load a term into the edit fields."""
        self._source_entry.setText(term.source)
        self._target_entry.setText(term.target)
        self._notes_entry.setPlainText(term.notes)
        self._domain_entry.setCurrentText(term.domain)
        
    def _clear_fields(self):
        """Clear all edit fields.""" 
        self._source_entry.clear()
        self._target_entry.clear()
        self._notes_entry.clear()
        self._domain_entry.setCurrentText("")
        self._source_entry.setFocus()
        
    def _get_fields_data(self) -> Dict[str, str]:
        """Get data from edit fields."""
        return {
            "source": self._source_entry.text().strip(),
            "target": self._target_entry.text().strip(),
            "notes": self._notes_entry.toPlainText().strip(),
            "domain": self._domain_entry.currentText().strip()
        }
        
    def _add_term(self):
        """Add a new term."""
        data = self._get_fields_data()
        
        if not data["source"]:
            QMessageBox.warning(self, self.tr("Warning"), self.tr("Source text cannot be empty."))
            self._source_entry.setFocus()
            return
            
        if not data["target"]:
            QMessageBox.warning(self, self.tr("Warning"), self.tr("Target text cannot be empty."))
            self._target_entry.setFocus()
            return
            
        # Check for duplicate
        for term in self._terms:
            if term.source.lower() == data["source"].lower():
                reply = QMessageBox.question(
                    self,
                    self.tr("Duplicate Term"),
                    self.tr("A term with this source text already exists. Update it?"),
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    self._update_existing_term(data)
                return
                
        # Add new term
        add_term(data["source"], data["target"], data["notes"], data["domain"])
        self._load_terms()
        self._clear_fields()
        self.glossary_changed.emit()
        
    def _update_term(self):
        """Update the selected term."""
        current_row = self._table.currentRow()
        if current_row < 0 or current_row >= len(self._filtered_terms):
            return
            
        data = self._get_fields_data()
        
        if not data["source"]:
            QMessageBox.warning(self, self.tr("Warning"), self.tr("Source text cannot be empty."))
            return
            
        if not data["target"]:
            QMessageBox.warning(self, self.tr("Warning"), self.tr("Target text cannot be empty."))
            return
            
        self._update_existing_term(data)
        
    def _update_existing_term(self, data: Dict[str, str]):
        """Update an existing term with new data."""
        add_term(data["source"], data["target"], data["notes"], data["domain"])
        self._load_terms()
        self._clear_fields()
        self.glossary_changed.emit()
        
    def _delete_term(self):
        """Delete the selected term."""
        current_row = self._table.currentRow()
        if current_row < 0 or current_row >= len(self._filtered_terms):
            return
            
        term = self._filtered_terms[current_row]
        
        reply = QMessageBox.question(
            self,
            self.tr("Confirm Delete"),
            self.tr("Delete term '%s' → '%s'?") % (term.source, term.target),
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            remove_term(term.source)
            self._load_terms()
            self._clear_fields()
            self.glossary_changed.emit()
            
    def _show_context_menu(self, position):
        """Show context menu for table."""
        item = self._table.itemAt(position)
        if item is None:
            return
            
        menu = QMenu(self)
        
        edit_action = QAction(self.tr("Edit"), self)
        edit_action.triggered.connect(self._update_term)
        menu.addAction(edit_action)
        
        delete_action = QAction(self.tr("Delete"), self)
        delete_action.triggered.connect(self._delete_term)
        menu.addAction(delete_action)
        
        menu.addSeparator()
        
        copy_source_action = QAction(self.tr("Copy Source"), self)
        copy_source_action.triggered.connect(
            lambda: QApplication.clipboard().setText(self._filtered_terms[item.row()].source)
        )
        menu.addAction(copy_source_action)
        
        copy_target_action = QAction(self.tr("Copy Target"), self)
        copy_target_action.triggered.connect(
            lambda: QApplication.clipboard().setText(self._filtered_terms[item.row()].target)
        )
        menu.addAction(copy_target_action)
        
        menu.exec(self._table.mapToGlobal(position))
        
    def _import_csv(self):
        """Import terms from CSV file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Import Glossary from CSV"),
            "",
            self.tr("CSV files (*.csv);;All files (*)")
        )
        
        if not file_path:
            return
            
        # Show format info
        info = QMessageBox.information(
            self,
            self.tr("CSV Import Format"),
            self.tr("Expected CSV format:\nsource,target,notes,domain\n\n"
                   "First row can be a header (will be automatically detected)."),
            QMessageBox.Ok | QMessageBox.Cancel
        )
        
        if info != QMessageBox.Ok:
            return
            
        # Start import
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(0)
        
        self._import_thread = GlossaryImportThread(file_path)
        self._import_thread.progress_updated.connect(self._on_import_progress)
        self._import_thread.import_completed.connect(self._on_import_completed)
        self._import_thread.start()
        
    def _on_import_progress(self, progress: int, status: str):
        """Handle import progress update."""
        self._progress_bar.setValue(progress)
        self._status_label.setText(status)
        
    def _on_import_completed(self, results: Dict):
        """Handle import completion."""
        self._progress_bar.setVisible(False)
        
        imported = results.get("imported", 0)
        errors = results.get("errors", 0)
        
        if errors > 0:
            details = "\n".join(results.get("details", [])[:10])
            if len(results.get("details", [])) > 10:
                details += f"\n... and {len(results.get('details', [])) - 10} more errors"
                
            QMessageBox.warning(
                self,
                self.tr("Import Completed"),
                self.tr("Imported %d terms with %d errors.\n\nFirst errors:\n%s") % (imported, errors, details)
            )
        else:
            QMessageBox.information(
                self,
                self.tr("Import Completed"),
                self.tr("Successfully imported %d terms.") % imported
            )
            
        if imported > 0:
            self._load_terms()
            self.glossary_changed.emit()
            
    def _export_csv(self):
        """Export terms to CSV file."""
        if not self._terms:
            QMessageBox.warning(self, self.tr("Warning"), self.tr("No terms to export."))
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Export Glossary to CSV"),
            "glossary.csv",
            self.tr("CSV files (*.csv);;All files (*)")
        )
        
        if not file_path:
            return
            
        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write header
                writer.writerow(['source', 'target', 'notes', 'domain'])
                
                # Write terms (use current filter)
                for term in self._filtered_terms:
                    writer.writerow([term.source, term.target, term.notes, term.domain])
                    
            QMessageBox.information(
                self,
                self.tr("Export Completed"),
                self.tr("Exported %d terms to %s") % (len(self._filtered_terms), file_path)
            )
            
        except Exception as e:
            QMessageBox.critical(
                self,
                self.tr("Export Error"),
                self.tr("Failed to export glossary:\n%s") % str(e)
            )