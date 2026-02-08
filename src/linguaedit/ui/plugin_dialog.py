"""Plugin management dialog."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QTextEdit, QSplitter, QGroupBox, QCheckBox,
    QHeaderView, QMessageBox, QFileDialog, QAbstractItemView
)
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QFont

from linguaedit.services.plugins import get_plugin_manager, PluginInfo


class PluginDialog(QDialog):
    """Dialog for managing plugins."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Manage Plugins"))
        self.setModal(True)
        self.resize(700, 500)
        
        self._plugin_manager = get_plugin_manager()
        self._plugin_manager.plugins_changed.connect(self._refresh_plugins)
        
        self._build_ui()
        self._refresh_plugins()
    
    def _build_ui(self):
        """Build the dialog UI."""
        layout = QVBoxLayout(self)
        
        # Top buttons
        button_layout = QHBoxLayout()
        
        self._reload_btn = QPushButton(self.tr("Reload Plugins"))
        self._reload_btn.clicked.connect(self._on_reload_plugins)
        button_layout.addWidget(self._reload_btn)
        
        self._open_folder_btn = QPushButton(self.tr("Open Plugin Folder"))
        self._open_folder_btn.clicked.connect(self._on_open_plugin_folder)
        button_layout.addWidget(self._open_folder_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # Main content
        splitter = QSplitter(Qt.Horizontal)
        
        # Plugin list
        left_widget = QGroupBox(self.tr("Installed Plugins"))
        left_layout = QVBoxLayout(left_widget)
        
        self._plugin_table = QTableWidget()
        self._plugin_table.setColumnCount(4)
        self._plugin_table.setHorizontalHeaderLabels([
            self.tr("Name"), self.tr("Version"), self.tr("Author"), self.tr("Enabled")
        ])
        
        header = self._plugin_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        
        self._plugin_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._plugin_table.itemSelectionChanged.connect(self._on_plugin_selected)
        
        left_layout.addWidget(self._plugin_table)
        splitter.addWidget(left_widget)
        
        # Plugin details
        right_widget = QGroupBox(self.tr("Plugin Details"))
        right_layout = QVBoxLayout(right_widget)
        
        self._name_label = QLabel()
        font = QFont()
        font.setPointSize(font.pointSize() + 2)
        font.setBold(True)
        self._name_label.setFont(font)
        right_layout.addWidget(self._name_label)
        
        self._version_label = QLabel()
        right_layout.addWidget(self._version_label)
        
        self._author_label = QLabel()
        right_layout.addWidget(self._author_label)
        
        self._description_edit = QTextEdit()
        self._description_edit.setReadOnly(True)
        self._description_edit.setMaximumHeight(100)
        right_layout.addWidget(self._description_edit)
        
        # Plugin actions
        plugin_actions = QHBoxLayout()
        
        self._enable_btn = QPushButton(self.tr("Enable"))
        self._enable_btn.clicked.connect(self._on_enable_plugin)
        plugin_actions.addWidget(self._enable_btn)
        
        self._disable_btn = QPushButton(self.tr("Disable"))
        self._disable_btn.clicked.connect(self._on_disable_plugin)
        plugin_actions.addWidget(self._disable_btn)
        
        plugin_actions.addStretch()
        right_layout.addLayout(plugin_actions)
        
        right_layout.addStretch()
        splitter.addWidget(right_widget)
        
        layout.addWidget(splitter)
        
        # Info
        info_label = QLabel(
            self.tr("Plugins are loaded from: {}").format(
                str(self._plugin_manager._plugin_dir)
            )
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: gray; font-size: 10pt;")
        layout.addWidget(info_label)
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        close_btn = QPushButton(self.tr("Close"))
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        # Initially disable action buttons
        self._enable_btn.setEnabled(False)
        self._disable_btn.setEnabled(False)
    
    def _refresh_plugins(self):
        """Refresh the plugin list."""
        plugins = self._plugin_manager.get_plugins()
        
        self._plugin_table.setRowCount(len(plugins))
        
        for row, (name, plugin_info) in enumerate(plugins.items()):
            # Name
            name_item = QTableWidgetItem(plugin_info.name)
            name_item.setData(Qt.UserRole, name)
            self._plugin_table.setItem(row, 0, name_item)
            
            # Version
            version_item = QTableWidgetItem(plugin_info.version)
            self._plugin_table.setItem(row, 1, version_item)
            
            # Author
            author_item = QTableWidgetItem(plugin_info.author)
            self._plugin_table.setItem(row, 2, author_item)
            
            # Enabled checkbox
            checkbox = QCheckBox()
            checkbox.setChecked(plugin_info.enabled)
            checkbox.toggled.connect(
                lambda checked, plugin_name=name: self._on_plugin_toggled(plugin_name, checked)
            )
            self._plugin_table.setCellWidget(row, 3, checkbox)
        
        # Clear selection and details
        self._clear_details()
    
    def _clear_details(self):
        """Clear plugin details."""
        self._name_label.setText("")
        self._version_label.setText("")
        self._author_label.setText("")
        self._description_edit.setText("")
        
        self._enable_btn.setEnabled(False)
        self._disable_btn.setEnabled(False)
    
    @Slot()
    def _on_plugin_selected(self):
        """Handle plugin selection."""
        current_row = self._plugin_table.currentRow()
        if current_row < 0:
            self._clear_details()
            return
        
        name_item = self._plugin_table.item(current_row, 0)
        if not name_item:
            return
        
        plugin_name = name_item.data(Qt.UserRole)
        plugins = self._plugin_manager.get_plugins()
        plugin_info = plugins.get(plugin_name)
        
        if not plugin_info:
            self._clear_details()
            return
        
        # Update details
        self._name_label.setText(plugin_info.name)
        self._version_label.setText(self.tr("Version: {}").format(plugin_info.version))
        self._author_label.setText(self.tr("Author: {}").format(plugin_info.author))
        self._description_edit.setText(plugin_info.description)
        
        # Update buttons
        self._enable_btn.setEnabled(not plugin_info.enabled)
        self._disable_btn.setEnabled(plugin_info.enabled)
    
    @Slot(str, bool)
    def _on_plugin_toggled(self, plugin_name: str, enabled: bool):
        """Handle plugin enable/disable toggle."""
        if enabled:
            self._plugin_manager.enable_plugin(plugin_name)
        else:
            self._plugin_manager.disable_plugin(plugin_name)
        
        # Update button states if this plugin is selected
        current_row = self._plugin_table.currentRow()
        if current_row >= 0:
            name_item = self._plugin_table.item(current_row, 0)
            if name_item and name_item.data(Qt.UserRole) == plugin_name:
                self._enable_btn.setEnabled(not enabled)
                self._disable_btn.setEnabled(enabled)
    
    @Slot()
    def _on_enable_plugin(self):
        """Enable the selected plugin."""
        current_row = self._plugin_table.currentRow()
        if current_row < 0:
            return
        
        name_item = self._plugin_table.item(current_row, 0)
        if name_item:
            plugin_name = name_item.data(Qt.UserRole)
            self._plugin_manager.enable_plugin(plugin_name)
            
            # Update checkbox
            checkbox = self._plugin_table.cellWidget(current_row, 3)
            if checkbox:
                checkbox.setChecked(True)
    
    @Slot()
    def _on_disable_plugin(self):
        """Disable the selected plugin."""
        current_row = self._plugin_table.currentRow()
        if current_row < 0:
            return
        
        name_item = self._plugin_table.item(current_row, 0)
        if name_item:
            plugin_name = name_item.data(Qt.UserRole)
            self._plugin_manager.disable_plugin(plugin_name)
            
            # Update checkbox
            checkbox = self._plugin_table.cellWidget(current_row, 3)
            if checkbox:
                checkbox.setChecked(False)
    
    @Slot()
    def _on_reload_plugins(self):
        """Reload all plugins."""
        try:
            self._plugin_manager.reload_plugins()
            QMessageBox.information(
                self, 
                self.tr("Plugins Reloaded"),
                self.tr("All plugins have been reloaded successfully.")
            )
        except Exception as e:
            QMessageBox.warning(
                self,
                self.tr("Reload Failed"), 
                self.tr("Failed to reload plugins: {}").format(str(e))
            )
    
    @Slot()
    def _on_open_plugin_folder(self):
        """Open the plugin folder in the system file manager."""
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._plugin_manager._plugin_dir)))