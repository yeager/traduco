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


# ── Git-based diff dialog ───────────────────────────────────────────

class GitDiffDialog(QDialog):
    """Compare current file with a previous git commit."""

    def __init__(self, parent=None, file_path: str = "", file_type: str = "",
                 current_entries: list = None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Diff with Previous Version"))
        self.setMinimumSize(950, 650)

        self._file_path = file_path
        self._file_type = file_type
        self._current_entries = current_entries or []
        self._old_entries: list = []
        self._commits: list = []

        self._build_ui()
        self._load_commits()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Commit selector
        top = QHBoxLayout()
        top.addWidget(QLabel(self.tr("Compare with commit:")))
        self._commit_combo = QComboBox()
        self._commit_combo.setMinimumWidth(400)
        top.addWidget(self._commit_combo, 1)
        self._compare_btn = QPushButton(self.tr("Compare"))
        self._compare_btn.clicked.connect(self._run_compare)
        top.addWidget(self._compare_btn)
        layout.addLayout(top)

        # Status
        self._status = QLabel("")
        layout.addWidget(self._status)

        # Results tabs
        self._tabs = QTabWidget()

        # Summary tab
        summary_w = QWidget()
        summary_l = QVBoxLayout(summary_w)
        self._summary_text = QTextEdit()
        self._summary_text.setReadOnly(True)
        summary_l.addWidget(self._summary_text)
        self._tabs.addTab(summary_w, self.tr("Summary"))

        # Changes table
        changes_w = QWidget()
        changes_l = QVBoxLayout(changes_w)
        self._changes_table = QTableWidget()
        self._changes_table.setColumnCount(5)
        self._changes_table.setHorizontalHeaderLabels([
            self.tr("Type"), self.tr("Source (old)"), self.tr("Source (new)"),
            self.tr("Translation (old)"), self.tr("Translation (new)"),
        ])
        self._changes_table.setAlternatingRowColors(True)
        self._changes_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        header = self._changes_table.horizontalHeader()
        for c in range(5):
            header.setSectionResizeMode(c, QHeaderView.Stretch if c > 0 else QHeaderView.ResizeToContents)
        changes_l.addWidget(self._changes_table)
        self._tabs.addTab(changes_w, self.tr("Changes"))

        # Outdated tab
        outdated_w = QWidget()
        outdated_l = QVBoxLayout(outdated_w)
        outdated_l.addWidget(QLabel(self.tr(
            "<b>Outdated translations</b> — source changed but translation stayed the same."
        )))
        self._outdated_table = QTableWidget()
        self._outdated_table.setColumnCount(4)
        self._outdated_table.setHorizontalHeaderLabels([
            self.tr("Old Source"), self.tr("New Source"),
            self.tr("Translation"), self.tr("Status"),
        ])
        self._outdated_table.setAlternatingRowColors(True)
        oh = self._outdated_table.horizontalHeader()
        for c in range(4):
            oh.setSectionResizeMode(c, QHeaderView.Stretch)
        outdated_l.addWidget(self._outdated_table)
        self._tabs.addTab(outdated_w, self.tr("Outdated"))

        layout.addWidget(self._tabs, 1)

        # Close
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def _load_commits(self):
        from linguaedit.services.git_integration import get_commits_for_file
        self._commits = get_commits_for_file(self._file_path)
        self._commit_combo.clear()
        if not self._commits:
            self._commit_combo.addItem(self.tr("No git history found"))
            self._compare_btn.setEnabled(False)
            return
        for sha, subject in self._commits:
            self._commit_combo.addItem(f"{sha[:8]} — {subject}", sha)

    def _parse_content(self, content: str):
        """Parse file content string into entries list."""
        import tempfile, os
        suffix = "." + self._file_type if self._file_type else ".po"
        # Map file_type to actual extension
        ext_map = {"po": ".po", "ts": ".ts", "json": ".json", "xliff": ".xliff"}
        suffix = ext_map.get(self._file_type, ".po")

        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False, encoding="utf-8")
        tmp.write(content)
        tmp.close()
        try:
            from pathlib import Path as P
            p = P(tmp.name)
            if self._file_type == "po":
                fd = parse_po(p)
                return [(e.msgid, e.msgstr, e.fuzzy) for e in fd.entries]
            elif self._file_type == "ts":
                fd = parse_ts(p)
                return [(e.source, e.translation, e.is_fuzzy) for e in fd.entries]
            elif self._file_type == "json":
                fd = parse_json(p)
                return [(e.key, e.value, False) for e in fd.entries]
            elif self._file_type == "xliff":
                fd = parse_xliff(p)
                return [(e.source, e.target, e.is_fuzzy) for e in fd.entries]
        except Exception:
            return []
        finally:
            os.unlink(tmp.name)
        return []

    def _run_compare(self):
        idx = self._commit_combo.currentIndex()
        if idx < 0 or not self._commits:
            return
        sha = self._commit_combo.currentData()
        if not sha:
            return

        from linguaedit.services.git_integration import get_file_at_commit
        ok, content = get_file_at_commit(self._file_path, sha)
        if not ok:
            self._status.setText(self.tr("Failed to get file at commit %s") % sha[:8])
            return

        self._old_entries = self._parse_content(content)
        if not self._old_entries:
            self._status.setText(self.tr("Could not parse old version"))
            return

        self._status.setText(self.tr("Comparing %d old vs %d current entries…") % (
            len(self._old_entries), len(self._current_entries)))
        self._do_compare()

    def _do_compare(self):
        old_dict = {}
        for msgid, msgstr, fuzzy in self._old_entries:
            old_dict[msgid] = (msgstr, fuzzy)

        new_dict = {}
        for msgid, msgstr, fuzzy in self._current_entries:
            new_dict[msgid] = (msgstr, fuzzy)

        added = []
        removed = []
        changed_source = []  # source key changed (approximated by missing old + new)
        changed_trans = []
        outdated = []

        all_keys = set(old_dict.keys()) | set(new_dict.keys())

        for key in all_keys:
            old = old_dict.get(key)
            new = new_dict.get(key)
            if old and not new:
                removed.append((key, old[0]))
            elif new and not old:
                added.append((key, new[0]))
            elif old and new:
                if old[0] != new[0]:
                    changed_trans.append((key, old[0], new[0]))

        # Detect outdated: find entries where source text changed but translation is same
        # Use sequence matching to pair old→new renamed sources
        old_only = [k for k in old_dict if k not in new_dict]
        new_only = [k for k in new_dict if k not in old_dict]

        from difflib import SequenceMatcher
        for old_key in old_only:
            best_ratio = 0
            best_new = None
            for new_key in new_only:
                r = SequenceMatcher(None, old_key, new_key).ratio()
                if r > best_ratio and r > 0.6:
                    best_ratio = r
                    best_new = new_key
            if best_new:
                old_trans = old_dict[old_key][0]
                new_trans = new_dict[best_new][0]
                if old_trans and old_trans == new_trans:
                    outdated.append((old_key, best_new, old_trans))
                elif old_key != best_new:
                    changed_source.append((old_key, best_new, old_dict[old_key][0], new_dict[best_new][0]))

        # Summary
        lines = [
            self.tr("<h3>Comparison Results</h3>"),
            self.tr("<b>Added strings:</b> %d") % len(added),
            self.tr("<b>Removed strings:</b> %d") % len(removed),
            self.tr("<b>Changed translations:</b> %d") % len(changed_trans),
            self.tr("<b>Changed source text:</b> %d") % len(changed_source),
            self.tr("<b>Potentially outdated:</b> %d") % len(outdated),
        ]
        self._summary_text.setHtml("<br>".join(lines))

        # Changes table
        rows = []
        for key, trans in added:
            rows.append((self.tr("Added"), "", key[:80], "", trans[:80]))
        for key, trans in removed:
            rows.append((self.tr("Removed"), key[:80], "", trans[:80], ""))
        for key, old_t, new_t in changed_trans:
            rows.append((self.tr("Modified"), key[:80], key[:80], old_t[:80], new_t[:80]))
        for old_k, new_k, old_t, new_t in changed_source:
            rows.append((self.tr("Source changed"), old_k[:80], new_k[:80], old_t[:80], new_t[:80]))

        self._changes_table.setRowCount(len(rows))
        color_map = {
            self.tr("Added"): QColor(220, 255, 220),
            self.tr("Removed"): QColor(255, 220, 220),
            self.tr("Modified"): QColor(255, 255, 220),
            self.tr("Source changed"): QColor(230, 230, 255),
        }
        for r, (typ, *cols) in enumerate(rows):
            ti = QTableWidgetItem(typ)
            bg = color_map.get(typ)
            if bg:
                ti.setBackground(QBrush(bg))
            self._changes_table.setItem(r, 0, ti)
            for c, val in enumerate(cols):
                item = QTableWidgetItem(val)
                if bg:
                    item.setBackground(QBrush(bg))
                self._changes_table.setItem(r, c + 1, item)

        # Outdated table
        self._outdated_table.setRowCount(len(outdated))
        for r, (old_src, new_src, trans) in enumerate(outdated):
            self._outdated_table.setItem(r, 0, QTableWidgetItem(old_src[:100]))
            self._outdated_table.setItem(r, 1, QTableWidgetItem(new_src[:100]))
            self._outdated_table.setItem(r, 2, QTableWidgetItem(trans[:100]))
            warn = QTableWidgetItem(self.tr("⚠ Outdated"))
            warn.setForeground(QBrush(QColor(200, 120, 0)))
            self._outdated_table.setItem(r, 3, warn)

        self._status.setText(self.tr("Comparison complete."))