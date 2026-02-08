"""Translation history dialog — shows undo history for entries."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QTextEdit, QSplitter, QGroupBox, 
    QHeaderView, QMessageBox, QAbstractItemView, QFrame
)
from PySide6.QtCore import Qt, Slot, Signal
from PySide6.QtGui import QFont, QTextCharFormat, QSyntaxHighlighter, QTextDocument

from linguaedit.services.history import get_history_manager, HistoryEntry


class DiffHighlighter(QSyntaxHighlighter):
    """Simple diff highlighter for showing text differences."""
    
    def __init__(self, parent: QTextDocument = None):
        super().__init__(parent)
        
        # Define formats
        self.added_format = QTextCharFormat()
        self.added_format.setBackground(Qt.green)
        self.added_format.setForeground(Qt.darkGreen)
        
        self.removed_format = QTextCharFormat()
        self.removed_format.setBackground(Qt.red)
        self.removed_format.setForeground(Qt.darkRed)
    
    def highlightBlock(self, text: str):
        """Highlight additions and removals in diff text."""
        if text.startswith("+ "):
            self.setFormat(0, len(text), self.added_format)
        elif text.startswith("- "):
            self.setFormat(0, len(text), self.removed_format)


class HistoryDialog(QDialog):
    """Dialog showing translation history for a specific entry."""
    
    rollback_requested = Signal(str)  # old_value to restore
    
    def __init__(self, file_path: str, entry_index: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Translation History"))
        self.setModal(True)
        self.resize(800, 600)
        
        self._file_path = file_path
        self._entry_index = entry_index
        self._history_manager = get_history_manager()
        
        self._build_ui()
        self._load_history()
    
    def _build_ui(self):
        """Build the dialog UI."""
        layout = QVBoxLayout(self)
        
        # Header
        header_label = QLabel(
            self.tr("History for entry {0} in {1}").format(
                self._entry_index + 1,
                self._file_path.split("/")[-1]
            )
        )
        font = QFont()
        font.setPointSize(font.pointSize() + 1)
        font.setBold(True)
        header_label.setFont(font)
        layout.addWidget(header_label)
        
        # Main content
        splitter = QSplitter(Qt.Vertical)
        
        # History table
        table_group = QGroupBox(self.tr("Change History"))
        table_layout = QVBoxLayout(table_group)
        
        self._history_table = QTableWidget()
        self._history_table.setColumnCount(4)
        self._history_table.setHorizontalHeaderLabels([
            self.tr("Date/Time"), self.tr("Field"), self.tr("User"), self.tr("Change Type")
        ])
        
        header = self._history_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        
        self._history_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._history_table.itemSelectionChanged.connect(self._on_history_selected)
        
        table_layout.addWidget(self._history_table)
        splitter.addWidget(table_group)
        
        # Diff view
        diff_group = QGroupBox(self.tr("Changes"))
        diff_layout = QVBoxLayout(diff_group)
        
        # Before/After labels
        labels_layout = QHBoxLayout()
        labels_layout.addWidget(QLabel(self.tr("Before:")))
        labels_layout.addWidget(QLabel(self.tr("After:")))
        diff_layout.addLayout(labels_layout)
        
        # Text areas
        text_layout = QHBoxLayout()
        
        self._before_edit = QTextEdit()
        self._before_edit.setReadOnly(True)
        self._before_edit.setMaximumHeight(150)
        text_layout.addWidget(self._before_edit)
        
        self._after_edit = QTextEdit()
        self._after_edit.setReadOnly(True)
        self._after_edit.setMaximumHeight(150)
        text_layout.addWidget(self._after_edit)
        
        diff_layout.addLayout(text_layout)
        
        # Diff text
        self._diff_edit = QTextEdit()
        self._diff_edit.setReadOnly(True)
        self._diff_edit.setMaximumHeight(100)
        self._diff_edit.setPlainText(self.tr("Select a history entry to see changes"))
        
        # Add syntax highlighting
        self._highlighter = DiffHighlighter(self._diff_edit.document())
        
        diff_layout.addWidget(QLabel(self.tr("Diff:")))
        diff_layout.addWidget(self._diff_edit)
        
        splitter.addWidget(diff_group)
        layout.addWidget(splitter)
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        
        self._rollback_btn = QPushButton(self.tr("Rollback to This Version"))
        self._rollback_btn.setEnabled(False)
        self._rollback_btn.clicked.connect(self._on_rollback)
        button_layout.addWidget(self._rollback_btn)
        
        button_layout.addStretch()
        
        close_btn = QPushButton(self.tr("Close"))
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def _load_history(self):
        """Load and display history entries."""
        history = self._history_manager.get_entry_history(self._file_path, self._entry_index)
        
        self._history_table.setRowCount(len(history))
        self._history_entries = history
        
        for row, entry in enumerate(history):
            # Date/Time
            time_str = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            time_item = QTableWidgetItem(time_str)
            time_item.setData(Qt.UserRole, row)
            self._history_table.setItem(row, 0, time_item)
            
            # Field
            field_item = QTableWidgetItem(entry.field.title())
            self._history_table.setItem(row, 1, field_item)
            
            # User
            user_item = QTableWidgetItem(entry.user or self.tr("Unknown"))
            self._history_table.setItem(row, 2, user_item)
            
            # Change type
            if len(entry.old_value) == 0:
                change_type = self.tr("Added")
            elif len(entry.new_value) == 0:
                change_type = self.tr("Deleted")
            else:
                change_type = self.tr("Modified")
            
            change_item = QTableWidgetItem(change_type)
            self._history_table.setItem(row, 3, change_item)
        
        if not history:
            # No history
            no_history_item = QTableWidgetItem(self.tr("No history available"))
            no_history_item.setTextAlignment(Qt.AlignCenter)
            self._history_table.setItem(0, 0, no_history_item)
            self._history_table.setSpan(0, 0, 1, 4)
    
    @Slot()
    def _on_history_selected(self):
        """Handle history entry selection."""
        current_row = self._history_table.currentRow()
        if current_row < 0 or current_row >= len(self._history_entries):
            self._clear_diff()
            return
        
        entry = self._history_entries[current_row]
        
        # Update before/after text
        self._before_edit.setPlainText(entry.old_value)
        self._after_edit.setPlainText(entry.new_value)
        
        # Generate and display diff
        diff_text = self._generate_diff(entry.old_value, entry.new_value)
        self._diff_edit.setPlainText(diff_text)
        
        # Enable rollback button
        self._rollback_btn.setEnabled(True)
    
    def _clear_diff(self):
        """Clear the diff display."""
        self._before_edit.clear()
        self._after_edit.clear()
        self._diff_edit.setPlainText(self.tr("Select a history entry to see changes"))
        self._rollback_btn.setEnabled(False)
    
    def _generate_diff(self, old_text: str, new_text: str) -> str:
        """Generate a simple diff between two texts."""
        from difflib import unified_diff
        
        old_lines = old_text.splitlines(keepends=True)
        new_lines = new_text.splitlines(keepends=True)
        
        diff_lines = list(unified_diff(
            old_lines,
            new_lines,
            fromfile="before",
            tofile="after",
            lineterm=""
        ))
        
        if not diff_lines:
            return self.tr("No changes")
        
        return "".join(diff_lines)
    
    @Slot()
    def _on_rollback(self):
        """Handle rollback request."""
        current_row = self._history_table.currentRow()
        if current_row < 0 or current_row >= len(self._history_entries):
            return
        
        entry = self._history_entries[current_row]
        
        # Confirm rollback
        reply = QMessageBox.question(
            self,
            self.tr("Confirm Rollback"),
            self.tr(
                "Are you sure you want to rollback to this version?\n\n"
                "This will replace the current text with:\n{}"
            ).format(entry.old_value[:200] + ("..." if len(entry.old_value) > 200 else "")),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.rollback_requested.emit(entry.old_value)
            self.accept()


class FileHistoryDialog(QDialog):
    """Dialog showing all recent changes in a file."""
    
    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("File History"))
        self.setModal(True)
        self.resize(900, 600)
        
        self._file_path = file_path
        self._history_manager = get_history_manager()
        
        self._build_ui()
        self._load_history()
    
    def _build_ui(self):
        """Build the dialog UI."""
        layout = QVBoxLayout(self)
        
        # Header
        header_label = QLabel(
            self.tr("Recent changes in: {}").format(self._file_path.split("/")[-1])
        )
        font = QFont()
        font.setPointSize(font.pointSize() + 1)
        font.setBold(True)
        header_label.setFont(font)
        layout.addWidget(header_label)
        
        # History table
        self._history_table = QTableWidget()
        self._history_table.setColumnCount(5)
        self._history_table.setHorizontalHeaderLabels([
            self.tr("Date/Time"), self.tr("Entry"), self.tr("Field"), 
            self.tr("User"), self.tr("Summary")
        ])
        
        header = self._history_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        
        self._history_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._history_table.doubleClicked.connect(self._on_entry_double_clicked)
        
        layout.addWidget(self._history_table)
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        
        self._view_entry_btn = QPushButton(self.tr("View Entry History"))
        self._view_entry_btn.setEnabled(False)
        self._view_entry_btn.clicked.connect(self._on_view_entry_history)
        button_layout.addWidget(self._view_entry_btn)
        
        button_layout.addStretch()
        
        close_btn = QPushButton(self.tr("Close"))
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        self._history_table.itemSelectionChanged.connect(self._on_selection_changed)
    
    def _load_history(self):
        """Load and display file history."""
        history = self._history_manager.get_file_history(self._file_path, 200)
        
        self._history_table.setRowCount(len(history))
        self._history_entries = history
        
        for row, entry in enumerate(history):
            # Date/Time
            time_str = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            time_item = QTableWidgetItem(time_str)
            time_item.setData(Qt.UserRole, entry.entry_index)
            self._history_table.setItem(row, 0, time_item)
            
            # Entry index
            entry_item = QTableWidgetItem(str(entry.entry_index + 1))
            self._history_table.setItem(row, 1, entry_item)
            
            # Field
            field_item = QTableWidgetItem(entry.field.title())
            self._history_table.setItem(row, 2, field_item)
            
            # User
            user_item = QTableWidgetItem(entry.user or self.tr("Unknown"))
            self._history_table.setItem(row, 3, user_item)
            
            # Summary
            old_preview = entry.old_value[:50] + ("..." if len(entry.old_value) > 50 else "")
            new_preview = entry.new_value[:50] + ("..." if len(entry.new_value) > 50 else "")
            summary = f"'{old_preview}' → '{new_preview}'"
            
            summary_item = QTableWidgetItem(summary)
            self._history_table.setItem(row, 4, summary_item)
    
    @Slot()
    def _on_selection_changed(self):
        """Handle selection change."""
        self._view_entry_btn.setEnabled(self._history_table.currentRow() >= 0)
    
    @Slot()
    def _on_entry_double_clicked(self):
        """Handle double-click on entry."""
        self._on_view_entry_history()
    
    @Slot()
    def _on_view_entry_history(self):
        """Open history dialog for selected entry."""
        current_row = self._history_table.currentRow()
        if current_row < 0 or current_row >= len(self._history_entries):
            return
        
        entry = self._history_entries[current_row]
        
        dialog = HistoryDialog(self._file_path, entry.entry_index, self)
        dialog.exec()