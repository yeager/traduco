"""Diff Dialog for comparing translation files."""

from __future__ import annotations

from difflib import SequenceMatcher, unified_diff
from pathlib import Path
from typing import List, Dict, Tuple, Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFileDialog, QComboBox,
    QTextEdit, QSplitter, QGroupBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QDialogButtonBox,
    QProgressBar, QTabWidget, QWidget, QCheckBox,
    QAbstractItemView, QFrame
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QFont, QColor, QTextCharFormat, QTextCursor, QBrush

# Import parsers (assuming they exist)
from linguaedit.parsers.po_parser import parse_po
from linguaedit.parsers.ts_parser import parse_ts  
from linguaedit.parsers.json_parser import parse_json
from linguaedit.parsers.xliff_parser import parse_xliff


class DiffComparisonThread(QThread):
    """Thread for comparing large files."""
    
    progress_updated = Signal(int, str)  # progress, status
    comparison_completed = Signal(dict)  # results
    
    def __init__(self, file1_entries: List[Dict], file2_entries: List[Dict], options: Dict):
        super().__init__()
        self.file1_entries = file1_entries
        self.file2_entries = file2_entries
        self.options = options
        
    def run(self):
        """Perform the file comparison."""
        results = {
            "added": [],
            "removed": [],
            "modified": [],
            "unchanged": [],
            "stats": {}
        }
        
        try:
            # Create lookup dictionaries
            file1_dict = {entry["msgid"]: entry for entry in self.file1_entries}
            file2_dict = {entry["msgid"]: entry for entry in self.file2_entries}
            
            all_msgids = set(file1_dict.keys()) | set(file2_dict.keys())
            total_entries = len(all_msgids)
            
            for i, msgid in enumerate(all_msgids):
                self.progress_updated.emit(
                    int(i * 100 / total_entries) if total_entries > 0 else 100,
                    f"Comparing entry {i+1}/{total_entries}"
                )
                
                entry1 = file1_dict.get(msgid)
                entry2 = file2_dict.get(msgid)
                
                if entry1 and entry2:
                    # Compare translations
                    if entry1.get("msgstr") != entry2.get("msgstr"):
                        results["modified"].append({
                            "msgid": msgid,
                            "file1": entry1.get("msgstr", ""),
                            "file2": entry2.get("msgstr", ""),
                            "index1": entry1.get("index", -1),
                            "index2": entry2.get("index", -1)
                        })
                    else:
                        results["unchanged"].append(msgid)
                elif entry1 and not entry2:
                    # Removed in file2
                    results["removed"].append({
                        "msgid": msgid,
                        "msgstr": entry1.get("msgstr", ""),
                        "index": entry1.get("index", -1)
                    })
                elif not entry1 and entry2:
                    # Added in file2
                    results["added"].append({
                        "msgid": msgid,
                        "msgstr": entry2.get("msgstr", ""), 
                        "index": entry2.get("index", -1)
                    })
                    
            # Calculate statistics
            results["stats"] = {
                "total": total_entries,
                "added": len(results["added"]),
                "removed": len(results["removed"]),
                "modified": len(results["modified"]),
                "unchanged": len(results["unchanged"])
            }
            
        except Exception as e:
            results["error"] = str(e)
            
        self.comparison_completed.emit(results)


class DiffDialog(QDialog):
    """Dialog for comparing two translation files side by side."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Compare Translation Files"))
        self.setMinimumSize(1000, 700)
        
        self._file1_data = None
        self._file2_data = None
        self._file1_entries = []
        self._file2_entries = []
        self._comparison_results = {}
        self._comparison_thread = None
        
        self._build_ui()
        self._setup_connections()
        
    def _build_ui(self):
        layout = QVBoxLayout(self)
        
        # File selection area
        files_group = QGroupBox(self.tr("Select Files to Compare"))
        files_layout = QGridLayout(files_group)
        
        # File 1
        files_layout.addWidget(QLabel(self.tr("Original File:")), 0, 0)
        self._file1_path = QLabel(self.tr("No file selected"))
        self._file1_path.setStyleSheet("border: 1px solid gray; padding: 4px;")
        files_layout.addWidget(self._file1_path, 0, 1)
        
        self._file1_browse_btn = QPushButton(self.tr("Browse..."))
        files_layout.addWidget(self._file1_browse_btn, 0, 2)
        
        # File 2  
        files_layout.addWidget(QLabel(self.tr("Comparison File:")), 1, 0)
        self._file2_path = QLabel(self.tr("No file selected"))
        self._file2_path.setStyleSheet("border: 1px solid gray; padding: 4px;")
        files_layout.addWidget(self._file2_path, 1, 1)
        
        self._file2_browse_btn = QPushButton(self.tr("Browse..."))
        files_layout.addWidget(self._file2_browse_btn, 1, 2)
        
        layout.addWidget(files_group)
        
        # Comparison options
        options_group = QGroupBox(self.tr("Comparison Options"))
        options_layout = QHBoxLayout(options_group)
        
        self._ignore_case_cb = QCheckBox(self.tr("Ignore case"))
        self._ignore_whitespace_cb = QCheckBox(self.tr("Ignore whitespace"))
        self._show_unchanged_cb = QCheckBox(self.tr("Show unchanged"))
        
        options_layout.addWidget(self._ignore_case_cb)
        options_layout.addWidget(self._ignore_whitespace_cb)
        options_layout.addWidget(self._show_unchanged_cb)
        options_layout.addStretch()
        
        # Compare button
        self._compare_btn = QPushButton(self.tr("Compare Files"))
        self._compare_btn.setEnabled(False)
        options_layout.addWidget(self._compare_btn)
        
        layout.addWidget(options_group)
        
        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)
        
        # Results area - tabbed interface
        self._results_tab = QTabWidget()
        
        # Summary tab
        self._build_summary_tab()
        
        # Side by side tab
        self._build_side_by_side_tab()
        
        # Changes list tab
        self._build_changes_tab()
        
        layout.addWidget(self._results_tab, 1)
        
        # Status bar
        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #666; font-size: 11px; padding: 4px;")
        layout.addWidget(self._status_label)
        
        # Dialog buttons
        self._button_box = QDialogButtonBox(QDialogButtonBox.Close)
        self._button_box.rejected.connect(self.reject)
        layout.addWidget(self._button_box)
        
    def _build_summary_tab(self):
        """Build the summary tab.""" 
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Statistics
        stats_group = QGroupBox(self.tr("Comparison Statistics"))
        stats_layout = QGridLayout(stats_group)
        
        self._total_entries_label = QLabel("0")
        self._added_entries_label = QLabel("0")
        self._removed_entries_label = QLabel("0")
        self._modified_entries_label = QLabel("0")
        self._unchanged_entries_label = QLabel("0")
        
        stats_layout.addWidget(QLabel(self.tr("Total entries:")), 0, 0)
        stats_layout.addWidget(self._total_entries_label, 0, 1)
        
        stats_layout.addWidget(QLabel(self.tr("Added:")), 1, 0)
        stats_layout.addWidget(self._added_entries_label, 1, 1)
        
        stats_layout.addWidget(QLabel(self.tr("Removed:")), 2, 0)
        stats_layout.addWidget(self._removed_entries_label, 2, 1)
        
        stats_layout.addWidget(QLabel(self.tr("Modified:")), 3, 0)
        stats_layout.addWidget(self._modified_entries_label, 3, 1)
        
        stats_layout.addWidget(QLabel(self.tr("Unchanged:")), 4, 0)
        stats_layout.addWidget(self._unchanged_entries_label, 4, 1)
        
        layout.addWidget(stats_group)
        
        # Summary text
        summary_group = QGroupBox(self.tr("Summary"))
        summary_layout = QVBoxLayout(summary_group)
        
        self._summary_text = QTextEdit()
        self._summary_text.setReadOnly(True)
        self._summary_text.setMaximumHeight(150)
        summary_layout.addWidget(self._summary_text)
        
        layout.addWidget(summary_group)
        layout.addStretch()
        
        self._results_tab.addTab(tab, self.tr("Summary"))
        
    def _build_side_by_side_tab(self):
        """Build the side by side comparison tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Splitter for side by side view
        splitter = QSplitter(Qt.Horizontal)
        
        # Left side (original file)
        left_group = QGroupBox(self.tr("Original File"))
        left_layout = QVBoxLayout(left_group)
        
        self._left_text = QTextEdit()
        self._left_text.setReadOnly(True)
        left_layout.addWidget(self._left_text)
        splitter.addWidget(left_group)
        
        # Right side (comparison file)
        right_group = QGroupBox(self.tr("Comparison File"))
        right_layout = QVBoxLayout(right_group)
        
        self._right_text = QTextEdit()
        self._right_text.setReadOnly(True)
        right_layout.addWidget(self._right_text)
        splitter.addWidget(right_group)
        
        layout.addWidget(splitter)
        self._results_tab.addTab(tab, self.tr("Side by Side"))
        
    def _build_changes_tab(self):
        """Build the changes list tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Filter controls
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel(self.tr("Show:")))
        
        self._changes_filter = QComboBox()
        self._changes_filter.addItems([
            self.tr("All Changes"),
            self.tr("Added Only"),
            self.tr("Removed Only"), 
            self.tr("Modified Only")
        ])
        filter_layout.addWidget(self._changes_filter)
        filter_layout.addStretch()
        
        layout.addLayout(filter_layout)
        
        # Changes table
        self._changes_table = QTableWidget()
        self._changes_table.setColumnCount(4)
        self._changes_table.setHorizontalHeaderLabels([
            self.tr("Change"), self.tr("Source Text"), self.tr("Original"), self.tr("Comparison")
        ])
        
        # Table settings
        self._changes_table.setAlternatingRowColors(True)
        self._changes_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        header = self._changes_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch) 
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        
        layout.addWidget(self._changes_table)
        self._results_tab.addTab(tab, self.tr("Changes"))
        
    def _setup_connections(self):
        """Setup signal connections."""
        self._file1_browse_btn.clicked.connect(lambda: self._browse_file(1))
        self._file2_browse_btn.clicked.connect(lambda: self._browse_file(2))
        self._compare_btn.clicked.connect(self._compare_files)
        self._changes_filter.currentTextChanged.connect(self._filter_changes)
        
    def _browse_file(self, file_num: int):
        """Browse for a file to compare."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Select Translation File"),
            "",
            self.tr("Translation files (*.po *.pot *.ts *.json *.xliff *.xlf);;All files (*)")
        )
        
        if not file_path:
            return
            
        if file_num == 1:
            self._file1_path.setText(file_path)
            self._load_file(file_path, 1)
        else:
            self._file2_path.setText(file_path)
            self._load_file(file_path, 2)
            
        # Enable compare button if both files are selected
        if (self._file1_path.text() != self.tr("No file selected") and 
            self._file2_path.text() != self.tr("No file selected")):
            self._compare_btn.setEnabled(True)
            
    def _load_file(self, file_path: str, file_num: int):
        """Load a translation file."""
        try:
            path = Path(file_path)
            
            # Parse file based on extension
            if path.suffix in (".po", ".pot"):
                file_data = parse_po(path)
                entries = [
                    {
                        "msgid": entry.msgid,
                        "msgstr": entry.msgstr,
                        "index": i,
                        "is_fuzzy": entry.fuzzy
                    }
                    for i, entry in enumerate(file_data.entries)
                ]
            elif path.suffix == ".ts":
                file_data = parse_ts(path)
                entries = [
                    {
                        "msgid": entry.source,
                        "msgstr": entry.translation,
                        "index": i,
                        "is_fuzzy": entry.is_fuzzy
                    }
                    for i, entry in enumerate(file_data.entries)
                ]
            elif path.suffix == ".json":
                file_data = parse_json(path)
                entries = [
                    {
                        "msgid": entry.key,
                        "msgstr": entry.value,
                        "index": i,
                        "is_fuzzy": False
                    }
                    for i, entry in enumerate(file_data.entries)
                ]
            elif path.suffix in (".xliff", ".xlf"):
                file_data = parse_xliff(path)
                entries = [
                    {
                        "msgid": entry.source,
                        "msgstr": entry.target,
                        "index": i,
                        "is_fuzzy": entry.is_fuzzy
                    }
                    for i, entry in enumerate(file_data.entries)
                ]
            else:
                self._show_error(self.tr("Unsupported file format: %s") % path.suffix)
                return
                
            if file_num == 1:
                self._file1_data = file_data
                self._file1_entries = entries
            else:
                self._file2_data = file_data
                self._file2_entries = entries
                
        except Exception as e:
            self._show_error(self.tr("Failed to load file: %s") % str(e))
            
    def _compare_files(self):
        """Start file comparison."""
        if not self._file1_entries or not self._file2_entries:
            return
            
        # Disable UI during comparison
        self._compare_btn.setEnabled(False)
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(0)
        
        # Start comparison thread
        options = {
            "ignore_case": self._ignore_case_cb.isChecked(),
            "ignore_whitespace": self._ignore_whitespace_cb.isChecked(),
            "show_unchanged": self._show_unchanged_cb.isChecked()
        }
        
        self._comparison_thread = DiffComparisonThread(
            self._file1_entries,
            self._file2_entries,
            options
        )
        self._comparison_thread.progress_updated.connect(self._on_progress_updated)
        self._comparison_thread.comparison_completed.connect(self._on_comparison_completed)
        self._comparison_thread.start()
        
    def _on_progress_updated(self, progress: int, status: str):
        """Handle progress update."""
        self._progress_bar.setValue(progress)
        self._status_label.setText(status)
        
    def _on_comparison_completed(self, results: Dict):
        """Handle comparison completion."""
        self._progress_bar.setVisible(False)
        self._compare_btn.setEnabled(True)
        
        if "error" in results:
            self._show_error(self.tr("Comparison failed: %s") % results["error"])
            return
            
        self._comparison_results = results
        self._update_results_display()
        
    def _update_results_display(self):
        """Update the results display with comparison data."""
        results = self._comparison_results
        stats = results.get("stats", {})
        
        # Update summary statistics
        self._total_entries_label.setText(str(stats.get("total", 0)))
        self._added_entries_label.setText(str(stats.get("added", 0)))
        self._removed_entries_label.setText(str(stats.get("removed", 0)))
        self._modified_entries_label.setText(str(stats.get("modified", 0)))
        self._unchanged_entries_label.setText(str(stats.get("unchanged", 0)))
        
        # Update summary text
        summary_lines = []
        if stats.get("added", 0) > 0:
            summary_lines.append(f"🟢 {stats['added']} entries were added")
        if stats.get("removed", 0) > 0:
            summary_lines.append(f"🔴 {stats['removed']} entries were removed")
        if stats.get("modified", 0) > 0:
            summary_lines.append(f"🟡 {stats['modified']} entries were modified")
        if stats.get("unchanged", 0) > 0:
            summary_lines.append(f"⚪ {stats['unchanged']} entries were unchanged")
            
        self._summary_text.setPlainText('\n'.join(summary_lines))
        
        # Update changes table
        self._populate_changes_table()
        
        # Update side by side view
        self._update_side_by_side()
        
        # Update status
        total_changes = stats.get("added", 0) + stats.get("removed", 0) + stats.get("modified", 0)
        self._status_label.setText(self.tr("Comparison complete. %d changes found.") % total_changes)
        
    def _populate_changes_table(self):
        """Populate the changes table."""
        results = self._comparison_results
        all_changes = []
        
        # Add "Added" entries
        for item in results.get("added", []):
            all_changes.append(("Added", item["msgid"], "", item["msgstr"]))
            
        # Add "Removed" entries
        for item in results.get("removed", []):
            all_changes.append(("Removed", item["msgid"], item["msgstr"], ""))
            
        # Add "Modified" entries
        for item in results.get("modified", []):
            all_changes.append(("Modified", item["msgid"], item["file1"], item["file2"]))
            
        self._changes_table.setRowCount(len(all_changes))
        
        for row, (change_type, msgid, original, comparison) in enumerate(all_changes):
            # Change type
            change_item = QTableWidgetItem(change_type)
            if change_type == "Added":
                change_item.setBackground(QBrush(QColor(220, 255, 220)))
            elif change_type == "Removed":
                change_item.setBackground(QBrush(QColor(255, 220, 220)))
            elif change_type == "Modified":
                change_item.setBackground(QBrush(QColor(255, 255, 220)))
            self._changes_table.setItem(row, 0, change_item)
            
            # Source text (truncated)
            msgid_preview = msgid[:100] + "..." if len(msgid) > 100 else msgid
            self._changes_table.setItem(row, 1, QTableWidgetItem(msgid_preview))
            
            # Original
            original_preview = original[:100] + "..." if len(original) > 100 else original
            self._changes_table.setItem(row, 2, QTableWidgetItem(original_preview))
            
            # Comparison
            comparison_preview = comparison[:100] + "..." if len(comparison) > 100 else comparison
            self._changes_table.setItem(row, 3, QTableWidgetItem(comparison_preview))
            
    def _update_side_by_side(self):
        """Update the side by side text comparison."""
        # Generate unified diff-style output for both sides
        file1_lines = []
        file2_lines = []
        
        results = self._comparison_results
        
        # Collect all changes for side by side display
        for item in results.get("modified", [])[:50]:  # Limit to first 50 for performance
            file1_lines.append(f"Source: {item['msgid']}")
            file1_lines.append(f"Translation: {item['file1']}")
            file1_lines.append("")
            
            file2_lines.append(f"Source: {item['msgid']}")  
            file2_lines.append(f"Translation: {item['file2']}")
            file2_lines.append("")
            
        self._left_text.setPlainText('\n'.join(file1_lines))
        self._right_text.setPlainText('\n'.join(file2_lines))
        
    def _filter_changes(self, filter_text: str):
        """Filter the changes table based on selection."""
        # Hide/show rows based on filter
        for row in range(self._changes_table.rowCount()):
            change_type_item = self._changes_table.item(row, 0)
            if not change_type_item:
                continue
                
            change_type = change_type_item.text()
            
            if filter_text == self.tr("All Changes"):
                self._changes_table.setRowHidden(row, False)
            elif filter_text == self.tr("Added Only"):
                self._changes_table.setRowHidden(row, change_type != "Added")
            elif filter_text == self.tr("Removed Only"):
                self._changes_table.setRowHidden(row, change_type != "Removed")
            elif filter_text == self.tr("Modified Only"):
                self._changes_table.setRowHidden(row, change_type != "Modified")
                
    def _show_error(self, message: str):
        """Show error message."""
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.critical(self, self.tr("Error"), message)