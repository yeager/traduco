"""Project View Dock Widget for LinguaEdit."""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Dict, Optional

from PySide6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QTreeWidget, QTreeWidgetItem, QLabel, QPushButton,
    QLineEdit, QComboBox, QProgressBar, QMenu,
    QHeaderView, QAbstractItemView, QFileDialog,
    QMessageBox, QToolButton, QFrame
)
from PySide6.QtCore import Qt, Signal, QThread, QFileSystemWatcher
from PySide6.QtGui import QAction, QIcon, QBrush, QColor, QPixmap

# Import parsers for statistics
from linguaedit.parsers.po_parser import parse_po
from linguaedit.parsers.ts_parser import parse_ts
from linguaedit.parsers.json_parser import parse_json
from linguaedit.parsers.xliff_parser import parse_xliff
from linguaedit.parsers.android_parser import parse_android
from linguaedit.parsers.arb_parser import parse_arb
from linguaedit.parsers.php_parser import parse_php
from linguaedit.parsers.yaml_parser import parse_yaml


class FileAnalysisThread(QThread):
    """Thread for analyzing project files."""
    
    progress_updated = Signal(int, str)  # progress, status
    file_analyzed = Signal(dict)  # file info
    analysis_completed = Signal()
    
    def __init__(self, project_path: str, extensions: List[str]):
        super().__init__()
        self.project_path = project_path
        self.extensions = extensions
        
    def run(self):
        """Analyze all translation files in the project."""
        try:
            # Find all translation files
            translation_files = []
            project_path = Path(self.project_path)
            
            for ext in self.extensions:
                translation_files.extend(project_path.rglob(f"*{ext}"))
                
            total_files = len(translation_files)
            
            if total_files == 0:
                self.analysis_completed.emit()
                return
                
            for i, file_path in enumerate(translation_files):
                self.progress_updated.emit(
                    int(i * 100 / total_files),
                    f"Analyzing {file_path.name}..."
                )
                
                try:
                    file_info = self._analyze_file(file_path)
                    if file_info:
                        self.file_analyzed.emit(file_info)
                except Exception as e:
                    # Skip files that can't be analyzed
                    pass
                    
        except Exception as e:
            pass
            
        self.analysis_completed.emit()
        
    def _analyze_file(self, file_path: Path) -> Optional[Dict]:
        """Analyze a single translation file."""
        try:
            file_data = None
            
            # Parse file based on extension
            if file_path.suffix in (".po", ".pot"):
                file_data = parse_po(file_path)
            elif file_path.suffix == ".ts":
                file_data = parse_ts(file_path)
            elif file_path.suffix == ".json":
                file_data = parse_json(file_path)
            elif file_path.suffix in (".xliff", ".xlf"):
                file_data = parse_xliff(file_path)
            elif file_path.suffix == ".xml":
                file_data = parse_android(file_path)
            elif file_path.suffix == ".arb":
                file_data = parse_arb(file_path)
            elif file_path.suffix == ".php":
                file_data = parse_php(file_path)
            elif file_path.suffix in (".yml", ".yaml"):
                file_data = parse_yaml(file_path)
                
            if not file_data:
                return None
                
            # Calculate statistics
            total = getattr(file_data, 'total_count', 0)
            translated = getattr(file_data, 'translated_count', 0)
            fuzzy = getattr(file_data, 'fuzzy_count', 0)
            
            percentage = (translated / total * 100) if total > 0 else 0
            
            return {
                "path": str(file_path),
                "name": file_path.name,
                "type": file_path.suffix[1:],  # Remove the dot
                "total": total,
                "translated": translated,
                "fuzzy": fuzzy,
                "untranslated": total - translated - fuzzy,
                "percentage": percentage,
                "size": file_path.stat().st_size,
                "modified": file_path.stat().st_mtime
            }
            
        except Exception:
            return None


class ProjectFileItem(QTreeWidgetItem):
    """Custom tree widget item for project files."""
    
    def __init__(self, file_info: Dict):
        super().__init__()
        self.file_info = file_info
        self._update_display()
        
    def _update_display(self):
        """Update the item display."""
        info = self.file_info
        
        # File name
        self.setText(0, info["name"])
        
        # Progress percentage
        self.setText(1, f"{info['percentage']:.1f}%")
        
        # Statistics
        self.setText(2, f"{info['translated']}/{info['total']}")
        
        # File type
        self.setText(3, info["type"].upper())
        
        # Set progress bar color based on completion
        percentage = info["percentage"]
        if percentage >= 100:
            color = QColor(200, 255, 200)  # Light green
        elif percentage >= 80:
            color = QColor(255, 255, 200)  # Light yellow
        elif percentage >= 50:
            color = QColor(255, 220, 200)  # Light orange
        else:
            color = QColor(255, 200, 200)  # Light red
            
        self.setBackground(1, QBrush(color))
        
        # Store file path for opening
        self.setData(0, Qt.UserRole, info["path"])


class ProjectDockWidget(QDockWidget):
    """Project view dock widget."""
    
    # Signal emitted when a file should be opened
    file_open_requested = Signal(str)  # file path
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Project"))
        self.setObjectName("ProjectDock")
        
        self._project_path = ""
        self._file_info_cache: Dict[str, Dict] = {}
        self._analysis_thread: Optional[FileAnalysisThread] = None
        self._file_watcher: Optional[QFileSystemWatcher] = None
        
        # Supported extensions
        self._extensions = [".po", ".pot", ".ts", ".json", ".xliff", ".xlf", 
                          ".xml", ".arb", ".php", ".yml", ".yaml"]
        
        self._build_ui()
        self._setup_connections()
        
    def _build_ui(self):
        central = QWidget()
        self.setWidget(central)
        
        layout = QVBoxLayout(central)
        layout.setContentsMargins(4, 4, 4, 4)
        
        # Project path selector
        path_layout = QHBoxLayout()
        
        self._path_label = QLabel(self.tr("No project"))
        self._path_label.setStyleSheet("font-weight: bold; color: #333;")
        path_layout.addWidget(self._path_label)
        
        path_layout.addStretch()
        
        self._open_project_btn = QToolButton()
        self._open_project_btn.setText(self.tr("Open..."))
        self._open_project_btn.setToolTip(self.tr("Open project folder"))
        path_layout.addWidget(self._open_project_btn)
        
        self._refresh_btn = QToolButton() 
        self._refresh_btn.setText(self.tr("Refresh"))
        self._refresh_btn.setToolTip(self.tr("Refresh project files"))
        self._refresh_btn.setEnabled(False)
        path_layout.addWidget(self._refresh_btn)
        
        layout.addLayout(path_layout)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator)
        
        # Filter controls
        filter_layout = QHBoxLayout()
        
        filter_layout.addWidget(QLabel(self.tr("Filter:")))
        
        self._filter_combo = QComboBox()
        self._filter_combo.addItems([
            self.tr("All files"),
            self.tr("Incomplete"),
            self.tr("Complete"), 
            self.tr("PO files"),
            self.tr("TS files"),
            self.tr("JSON files"),
            self.tr("XLIFF files")
        ])
        filter_layout.addWidget(self._filter_combo)
        
        layout.addLayout(filter_layout)
        
        # Project tree
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels([
            self.tr("File"), self.tr("Progress"), self.tr("Translated"), self.tr("Type")
        ])
        self._tree.setRootIsDecorated(False)
        self._tree.setAlternatingRowColors(True)
        self._tree.setContextMenuPolicy(Qt.CustomContextMenu)
        
        # Header settings
        header = self._tree.header()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        
        layout.addWidget(self._tree, 1)
        
        # Progress bar (hidden by default)
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)
        
        # Status and statistics
        self._status_label = QLabel(self.tr("Open a project folder to begin"))
        self._status_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self._status_label)
        
        # Statistics summary
        stats_layout = QHBoxLayout()
        
        self._total_files_label = QLabel("0 files")
        self._avg_progress_label = QLabel("0%")
        
        stats_layout.addWidget(QLabel(self.tr("Files:")))
        stats_layout.addWidget(self._total_files_label)
        stats_layout.addStretch()
        stats_layout.addWidget(QLabel(self.tr("Avg:")))
        stats_layout.addWidget(self._avg_progress_label)
        
        layout.addLayout(stats_layout)
        
    def _setup_connections(self):
        """Setup signal connections."""
        self._open_project_btn.clicked.connect(self._open_project)
        self._refresh_btn.clicked.connect(self._refresh_project)
        self._filter_combo.currentTextChanged.connect(self._apply_filter)
        self._tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._tree.customContextMenuRequested.connect(self._show_context_menu)
        
    def _open_project(self):
        """Open a project folder."""
        folder = QFileDialog.getExistingDirectory(
            self,
            self.tr("Select Project Folder"),
            self._project_path or os.path.expanduser("~")
        )
        
        if not folder:
            return
            
        self.set_project_path(folder)
        
    def set_project_path(self, path: str):
        """Set the project path and start analysis."""
        self._project_path = path
        self._path_label.setText(Path(path).name)
        self._refresh_btn.setEnabled(True)
        
        # Setup file system watcher
        if self._file_watcher:
            self._file_watcher.deleteLater()
            
        self._file_watcher = QFileSystemWatcher([path])
        self._file_watcher.directoryChanged.connect(self._on_directory_changed)
        
        self._analyze_project()
        
    def _analyze_project(self):
        """Start project analysis."""
        if not self._project_path:
            return
            
        # Clear existing data
        self._tree.clear()
        self._file_info_cache.clear()
        
        # Show progress
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(0)
        self._status_label.setText(self.tr("Analyzing project..."))
        
        # Start analysis thread
        if self._analysis_thread and self._analysis_thread.isRunning():
            self._analysis_thread.quit()
            self._analysis_thread.wait()
            
        self._analysis_thread = FileAnalysisThread(self._project_path, self._extensions)
        self._analysis_thread.progress_updated.connect(self._on_analysis_progress)
        self._analysis_thread.file_analyzed.connect(self._on_file_analyzed)
        self._analysis_thread.analysis_completed.connect(self._on_analysis_completed)
        self._analysis_thread.start()
        
    def _refresh_project(self):
        """Refresh the project analysis."""
        self._analyze_project()
        
    def _on_directory_changed(self, path: str):
        """Handle directory changes."""
        # Auto-refresh on file system changes
        self._refresh_project()
        
    def _on_analysis_progress(self, progress: int, status: str):
        """Handle analysis progress."""
        self._progress_bar.setValue(progress)
        self._status_label.setText(status)
        
    def _on_file_analyzed(self, file_info: Dict):
        """Handle analyzed file.""" 
        # Cache file info
        self._file_info_cache[file_info["path"]] = file_info
        
        # Add to tree
        item = ProjectFileItem(file_info)
        self._tree.addTopLevelItem(item)
        
        # Apply current filter
        self._apply_current_filter_to_item(item)
        
    def _on_analysis_completed(self):
        """Handle analysis completion."""
        self._progress_bar.setVisible(False)
        
        total_files = len(self._file_info_cache)
        self._total_files_label.setText(f"{total_files} files")
        
        if total_files > 0:
            # Calculate average progress
            total_progress = sum(info["percentage"] for info in self._file_info_cache.values())
            avg_progress = total_progress / total_files
            self._avg_progress_label.setText(f"{avg_progress:.1f}%")
            
            self._status_label.setText(
                self.tr("Found %d translation files") % total_files
            )
        else:
            self._avg_progress_label.setText("0%")
            self._status_label.setText(
                self.tr("No translation files found in this folder")
            )
            
        # Sort by filename
        self._tree.sortItems(0, Qt.AscendingOrder)
        
    def _apply_filter(self, filter_text: str):
        """Apply filter to the project tree."""
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            self._apply_current_filter_to_item(item)
            
    def _apply_current_filter_to_item(self, item: ProjectFileItem):
        """Apply the current filter to a specific item."""
        filter_text = self._filter_combo.currentText()
        file_info = item.file_info
        
        visible = True
        
        if filter_text == self.tr("Incomplete"):
            visible = file_info["percentage"] < 100
        elif filter_text == self.tr("Complete"):
            visible = file_info["percentage"] >= 100
        elif filter_text == self.tr("PO files"):
            visible = file_info["type"] in ("po", "pot")
        elif filter_text == self.tr("TS files"):
            visible = file_info["type"] == "ts"
        elif filter_text == self.tr("JSON files"):
            visible = file_info["type"] == "json"
        elif filter_text == self.tr("XLIFF files"):
            visible = file_info["type"] in ("xliff", "xlf")
            
        item.setHidden(not visible)
        
    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        """Handle double-click on tree item."""
        if isinstance(item, ProjectFileItem):
            file_path = item.file_info["path"]
            self.file_open_requested.emit(file_path)
            
    def _show_context_menu(self, position):
        """Show context menu for tree items."""
        item = self._tree.itemAt(position)
        if not isinstance(item, ProjectFileItem):
            return
            
        menu = QMenu(self)
        
        # Open file
        open_action = QAction(self.tr("Open"), self)
        open_action.triggered.connect(
            lambda: self.file_open_requested.emit(item.file_info["path"])
        )
        menu.addAction(open_action)
        
        menu.addSeparator()
        
        # Show in file manager
        show_action = QAction(self.tr("Show in File Manager"), self)
        show_action.triggered.connect(
            lambda: self._show_in_file_manager(item.file_info["path"])
        )
        menu.addAction(show_action)
        
        # Copy file path
        copy_action = QAction(self.tr("Copy Path"), self)
        copy_action.triggered.connect(
            lambda: QApplication.clipboard().setText(item.file_info["path"])
        )
        menu.addAction(copy_action)
        
        menu.addSeparator()
        
        # File properties
        props_action = QAction(self.tr("Properties"), self)
        props_action.triggered.connect(
            lambda: self._show_file_properties(item.file_info)
        )
        menu.addAction(props_action)
        
        menu.exec(self._tree.mapToGlobal(position))
        
    def _show_in_file_manager(self, file_path: str):
        """Show file in the system file manager."""
        import subprocess
        import platform
        
        system = platform.system()
        try:
            if system == "Darwin":  # macOS
                subprocess.run(["open", "-R", file_path])
            elif system == "Windows":
                subprocess.run(["explorer", "/select,", file_path])
            else:  # Linux
                subprocess.run(["xdg-open", str(Path(file_path).parent)])
        except Exception:
            pass
            
    def _show_file_properties(self, file_info: Dict):
        """Show file properties dialog."""
        from datetime import datetime
        
        props_text = []
        props_text.append(f"File: {file_info['name']}")
        props_text.append(f"Path: {file_info['path']}")
        props_text.append(f"Type: {file_info['type'].upper()}")
        props_text.append(f"Size: {file_info['size']:,} bytes")
        props_text.append("")
        props_text.append(f"Total entries: {file_info['total']}")
        props_text.append(f"Translated: {file_info['translated']}")
        props_text.append(f"Fuzzy: {file_info['fuzzy']}")
        props_text.append(f"Untranslated: {file_info['untranslated']}")
        props_text.append(f"Progress: {file_info['percentage']:.1f}%")
        props_text.append("")
        
        # Modified date
        mod_time = datetime.fromtimestamp(file_info['modified'])
        props_text.append(f"Modified: {mod_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        QMessageBox.information(
            self,
            self.tr("File Properties"),
            '\n'.join(props_text)
        )
        
    def get_project_path(self) -> str:
        """Get the current project path."""
        return self._project_path
        
    def get_project_statistics(self) -> Dict:
        """Get overall project statistics.""" 
        if not self._file_info_cache:
            return {
                "total_files": 0,
                "total_entries": 0,
                "total_translated": 0,
                "total_fuzzy": 0,
                "average_progress": 0.0
            }
            
        total_files = len(self._file_info_cache)
        total_entries = sum(info["total"] for info in self._file_info_cache.values())
        total_translated = sum(info["translated"] for info in self._file_info_cache.values())
        total_fuzzy = sum(info["fuzzy"] for info in self._file_info_cache.values())
        
        avg_progress = 0.0
        if total_files > 0:
            total_progress = sum(info["percentage"] for info in self._file_info_cache.values())
            avg_progress = total_progress / total_files
            
        return {
            "total_files": total_files,
            "total_entries": total_entries,
            "total_translated": total_translated,
            "total_fuzzy": total_fuzzy,
            "total_untranslated": total_entries - total_translated - total_fuzzy,
            "average_progress": avg_progress
        }