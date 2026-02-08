"""Batch Edit Dialog for LinguaEdit."""

from __future__ import annotations

import re
from typing import List, Tuple, Dict, Any

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QCheckBox, QPushButton, QComboBox,
    QTextEdit, QTabWidget, QWidget, QGroupBox, QRadioButton,
    QButtonGroup, QTreeWidget, QTreeWidgetItem, QHeaderView,
    QDialogButtonBox, QProgressBar, QMessageBox, QFrame
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QFont, QBrush, QColor


class BatchOperationThread(QThread):
    """Thread for performing batch operations."""
    
    progress_updated = Signal(int, str)  # progress, status
    operation_completed = Signal(dict)  # results
    
    def __init__(self, operation_type: str, entries: List[Dict], params: Dict):
        super().__init__()
        self.operation_type = operation_type
        self.entries = entries
        self.params = params
        
    def run(self):
        """Run the batch operation."""
        results = {"modified": 0, "errors": 0, "details": []}
        
        try:
            if self.operation_type == "search_replace":
                results = self._perform_search_replace()
            elif self.operation_type == "mark_fuzzy":
                results = self._mark_all_fuzzy()
            elif self.operation_type == "clear_fuzzy":
                results = self._clear_all_fuzzy()
            elif self.operation_type == "accept_fuzzy":
                results = self._accept_all_fuzzy()
            elif self.operation_type == "copy_source":
                results = self._copy_source_to_empty()
                
        except Exception as e:
            results["errors"] = len(self.entries)
            results["details"] = [f"Error: {str(e)}"]
            
        self.operation_completed.emit(results)
        
    def _perform_search_replace(self) -> Dict:
        """Perform search and replace operation."""
        find_text = self.params["find"]
        replace_text = self.params["replace"] 
        case_sensitive = self.params.get("case_sensitive", False)
        use_regex = self.params.get("regex", False)
        
        results = {"modified": 0, "errors": 0, "details": []}
        
        flags = 0 if case_sensitive else re.IGNORECASE
        
        for i, entry in enumerate(self.entries):
            self.progress_updated.emit(i * 100 // len(self.entries), f"Processing entry {i+1}/{len(self.entries)}")
            
            try:
                msgstr = entry.get("msgstr", "")
                if not msgstr:
                    continue
                    
                if use_regex:
                    new_text = re.sub(find_text, replace_text, msgstr, flags=flags)
                else:
                    if case_sensitive:
                        new_text = msgstr.replace(find_text, replace_text)
                    else:
                        # Case-insensitive replace
                        pattern = re.escape(find_text)
                        new_text = re.sub(pattern, replace_text, msgstr, flags=re.IGNORECASE)
                        
                if new_text != msgstr:
                    entry["new_msgstr"] = new_text
                    results["modified"] += 1
                    results["details"].append(f"Entry {entry['index']}: '{msgstr[:50]}...' → '{new_text[:50]}...'")
                    
            except Exception as e:
                results["errors"] += 1
                results["details"].append(f"Entry {entry['index']}: Error - {str(e)}")
                
        return results
        
    def _mark_all_fuzzy(self) -> Dict:
        """Mark all entries as fuzzy."""
        results = {"modified": 0, "errors": 0, "details": []}
        
        for i, entry in enumerate(self.entries):
            self.progress_updated.emit(i * 100 // len(self.entries), f"Marking entry {i+1}/{len(self.entries)} as fuzzy")
            
            if not entry.get("is_fuzzy", False):
                entry["new_is_fuzzy"] = True
                results["modified"] += 1
                
        results["details"].append(f"Marked {results['modified']} entries as fuzzy")
        return results
        
    def _clear_all_fuzzy(self) -> Dict:
        """Clear fuzzy flag from all entries."""
        results = {"modified": 0, "errors": 0, "details": []}
        
        for i, entry in enumerate(self.entries):
            self.progress_updated.emit(i * 100 // len(self.entries), f"Clearing fuzzy from entry {i+1}/{len(self.entries)}")
            
            if entry.get("is_fuzzy", False):
                entry["new_is_fuzzy"] = False
                results["modified"] += 1
                
        results["details"].append(f"Cleared fuzzy flag from {results['modified']} entries")
        return results
        
    def _accept_all_fuzzy(self) -> Dict:
        """Accept all fuzzy entries (remove fuzzy flag)."""
        results = {"modified": 0, "errors": 0, "details": []}
        
        for i, entry in enumerate(self.entries):
            self.progress_updated.emit(i * 100 // len(self.entries), f"Accepting fuzzy entry {i+1}/{len(self.entries)}")
            
            if entry.get("is_fuzzy", False) and entry.get("msgstr", ""):
                entry["new_is_fuzzy"] = False
                results["modified"] += 1
                
        results["details"].append(f"Accepted {results['modified']} fuzzy entries")
        return results
        
    def _copy_source_to_empty(self) -> Dict:
        """Copy source text to empty translations."""
        results = {"modified": 0, "errors": 0, "details": []}
        
        for i, entry in enumerate(self.entries):
            self.progress_updated.emit(i * 100 // len(self.entries), f"Processing entry {i+1}/{len(self.entries)}")
            
            if not entry.get("msgstr", "").strip() and entry.get("msgid", "").strip():
                entry["new_msgstr"] = entry["msgid"]
                results["modified"] += 1
                results["details"].append(f"Entry {entry['index']}: Copied source text")
                
        return results


class BatchEditDialog(QDialog):
    """Batch edit operations dialog."""
    
    # Signal emitted when batch operation should be applied
    apply_changes = Signal(list)  # List of modified entries
    
    def __init__(self, parent=None, entries: List[Dict] = None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Batch Edit"))
        self.setMinimumSize(700, 600)
        
        self._entries = entries or []
        self._modified_entries = []
        self._operation_thread = None
        
        self._build_ui()
        self._setup_connections()
        
    def _build_ui(self):
        layout = QVBoxLayout(self)
        
        # Tab widget for different operations
        self._tab_widget = QTabWidget()
        
        # Search & Replace tab
        self._build_search_replace_tab()
        
        # Fuzzy operations tab
        self._build_fuzzy_operations_tab()
        
        # Source copy tab
        self._build_source_copy_tab()
        
        layout.addWidget(self._tab_widget)
        
        # Preview area
        preview_group = QGroupBox(self.tr("Preview"))
        preview_layout = QVBoxLayout(preview_group)
        
        # Preview tree
        self._preview_tree = QTreeWidget()
        self._preview_tree.setHeaderLabels([
            self.tr("Entry"), self.tr("Operation"), self.tr("Before"), self.tr("After")
        ])
        self._preview_tree.setAlternatingRowColors(True)
        self._preview_tree.setRootIsDecorated(False)
        
        header = self._preview_tree.header()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        
        preview_layout.addWidget(self._preview_tree)
        layout.addWidget(preview_group)
        
        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)
        
        # Status label
        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self._status_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self._preview_btn = QPushButton(self.tr("Preview"))
        self._apply_btn = QPushButton(self.tr("Apply Changes"))
        self._apply_btn.setEnabled(False)
        
        button_layout.addWidget(self._preview_btn)
        button_layout.addStretch()
        
        # Standard dialog buttons
        self._button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_layout.addWidget(self._apply_btn)
        button_layout.addWidget(self._button_box)
        
        layout.addLayout(button_layout)
        
    def _build_search_replace_tab(self):
        """Build the search & replace tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Search fields
        fields_group = QGroupBox(self.tr("Search & Replace"))
        fields_layout = QGridLayout(fields_group)
        
        fields_layout.addWidget(QLabel(self.tr("Find:")), 0, 0)
        self._sr_find_entry = QLineEdit()
        fields_layout.addWidget(self._sr_find_entry, 0, 1)
        
        fields_layout.addWidget(QLabel(self.tr("Replace:")), 1, 0)
        self._sr_replace_entry = QLineEdit()
        fields_layout.addWidget(self._sr_replace_entry, 1, 1)
        
        layout.addWidget(fields_group)
        
        # Options
        options_group = QGroupBox(self.tr("Options"))
        options_layout = QHBoxLayout(options_group)
        
        self._sr_case_sensitive = QCheckBox(self.tr("Case sensitive"))
        self._sr_regex = QCheckBox(self.tr("Regular expression"))
        
        options_layout.addWidget(self._sr_case_sensitive)
        options_layout.addWidget(self._sr_regex)
        options_layout.addStretch()
        
        layout.addWidget(options_group)
        layout.addStretch()
        
        self._tab_widget.addTab(tab, self.tr("Search & Replace"))
        
    def _build_fuzzy_operations_tab(self):
        """Build the fuzzy operations tab.""" 
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        fuzzy_group = QGroupBox(self.tr("Fuzzy Operations"))
        fuzzy_layout = QVBoxLayout(fuzzy_group)
        
        self._mark_fuzzy_btn = QPushButton(self.tr("Mark all translations as fuzzy"))
        self._clear_fuzzy_btn = QPushButton(self.tr("Clear fuzzy flag from all translations"))
        self._accept_fuzzy_btn = QPushButton(self.tr("Accept all fuzzy translations"))
        
        fuzzy_layout.addWidget(self._mark_fuzzy_btn)
        fuzzy_layout.addWidget(self._clear_fuzzy_btn)
        fuzzy_layout.addWidget(self._accept_fuzzy_btn)
        
        layout.addWidget(fuzzy_group)
        layout.addStretch()
        
        self._tab_widget.addTab(tab, self.tr("Fuzzy Operations"))
        
    def _build_source_copy_tab(self):
        """Build the source copy tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        copy_group = QGroupBox(self.tr("Copy Source"))
        copy_layout = QVBoxLayout(copy_group)
        
        info_label = QLabel(self.tr("Copy source text to empty translation fields."))
        info_label.setWordWrap(True)
        copy_layout.addWidget(info_label)
        
        self._copy_source_btn = QPushButton(self.tr("Copy source to empty translations"))
        copy_layout.addWidget(self._copy_source_btn)
        
        layout.addWidget(copy_group)
        layout.addStretch()
        
        self._tab_widget.addTab(tab, self.tr("Source Copy"))
        
    def _setup_connections(self):
        """Setup signal connections."""
        # Tab operation buttons
        self._mark_fuzzy_btn.clicked.connect(lambda: self._preview_operation("mark_fuzzy"))
        self._clear_fuzzy_btn.clicked.connect(lambda: self._preview_operation("clear_fuzzy"))
        self._accept_fuzzy_btn.clicked.connect(lambda: self._preview_operation("accept_fuzzy"))
        self._copy_source_btn.clicked.connect(lambda: self._preview_operation("copy_source"))
        
        # Main buttons
        self._preview_btn.clicked.connect(self._preview_search_replace)
        self._apply_btn.clicked.connect(self._apply_changes)
        self._button_box.rejected.connect(self.reject)
        
    def _preview_operation(self, operation_type: str):
        """Preview a fuzzy or source copy operation.""" 
        if not self._entries:
            return
            
        # Create parameters based on operation type
        params = {"operation": operation_type}
        
        self._start_batch_operation(operation_type, params)
        
    def _preview_search_replace(self):
        """Preview search and replace operation."""
        find_text = self._sr_find_entry.text()
        if not find_text:
            QMessageBox.warning(self, self.tr("Warning"), self.tr("Please enter text to find."))
            return
            
        if not self._entries:
            return
            
        params = {
            "find": find_text,
            "replace": self._sr_replace_entry.text(),
            "case_sensitive": self._sr_case_sensitive.isChecked(),
            "regex": self._sr_regex.isChecked()
        }
        
        self._start_batch_operation("search_replace", params)
        
    def _start_batch_operation(self, operation_type: str, params: Dict):
        """Start a batch operation in a background thread.""" 
        if self._operation_thread and self._operation_thread.isRunning():
            return
            
        self._preview_tree.clear()
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(0)
        self._status_label.setText(self.tr("Processing..."))
        self._apply_btn.setEnabled(False)
        
        # Create a copy of entries to modify
        entries_copy = []
        for entry in self._entries:
            entries_copy.append(entry.copy())
            
        self._operation_thread = BatchOperationThread(operation_type, entries_copy, params)
        self._operation_thread.progress_updated.connect(self._on_progress_updated)
        self._operation_thread.operation_completed.connect(self._on_operation_completed)
        self._operation_thread.start()
        
    def _on_progress_updated(self, progress: int, status: str):
        """Handle progress update."""
        self._progress_bar.setValue(progress)
        self._status_label.setText(status)
        
    def _on_operation_completed(self, results: Dict):
        """Handle operation completion."""
        self._progress_bar.setVisible(False)
        
        modified_count = results.get("modified", 0)
        error_count = results.get("errors", 0)
        
        if error_count > 0:
            self._status_label.setText(self.tr("Completed with %d errors. %d entries modified.") % (error_count, modified_count))
        else:
            self._status_label.setText(self.tr("Completed successfully. %d entries modified.") % modified_count)
            
        # Update preview tree
        self._update_preview_tree(self._operation_thread.entries)
        
        # Enable apply button if there are changes
        self._apply_btn.setEnabled(modified_count > 0)
        
        # Store modified entries
        self._modified_entries = [e for e in self._operation_thread.entries if "new_msgstr" in e or "new_is_fuzzy" in e]
        
    def _update_preview_tree(self, entries: List[Dict]):
        """Update the preview tree with modified entries."""
        self._preview_tree.clear()
        
        for entry in entries:
            if "new_msgstr" in entry or "new_is_fuzzy" in entry:
                item = QTreeWidgetItem()
                
                # Entry number
                item.setText(0, str(entry.get("index", -1) + 1))
                
                # Operation type
                operation = ""
                if "new_msgstr" in entry:
                    operation = self.tr("Text change")
                if "new_is_fuzzy" in entry:
                    if operation:
                        operation += ", "
                    fuzzy_change = entry["new_is_fuzzy"]
                    operation += self.tr("Fuzzy: ") + (self.tr("Yes") if fuzzy_change else self.tr("No"))
                    
                item.setText(1, operation)
                
                # Before 
                before_parts = []
                if "new_msgstr" in entry:
                    before_parts.append(f"Text: {entry.get('msgstr', '')[:50]}")
                if "new_is_fuzzy" in entry:
                    before_parts.append(f"Fuzzy: {self.tr('Yes') if entry.get('is_fuzzy', False) else self.tr('No')}")
                item.setText(2, " | ".join(before_parts))
                
                # After
                after_parts = []
                if "new_msgstr" in entry:
                    after_parts.append(f"Text: {entry['new_msgstr'][:50]}")
                if "new_is_fuzzy" in entry:
                    after_parts.append(f"Fuzzy: {self.tr('Yes') if entry['new_is_fuzzy'] else self.tr('No')}")
                item.setText(3, " | ".join(after_parts))
                
                # Color changed rows
                brush = QBrush(QColor(255, 248, 220))  # Light yellow
                for i in range(4):
                    item.setBackground(i, brush)
                    
                self._preview_tree.addTopLevelItem(item)
                
    def _apply_changes(self):
        """Apply the changes to the entries."""
        if not self._modified_entries:
            return
            
        # Confirm with user
        reply = QMessageBox.question(
            self, 
            self.tr("Confirm Changes"),
            self.tr("Apply changes to %d entries?") % len(self._modified_entries),
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.apply_changes.emit(self._modified_entries)
            self.accept()
            
    def set_entries(self, entries: List[Dict]):
        """Set the entries to work with."""
        self._entries = entries