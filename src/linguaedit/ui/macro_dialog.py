"""Macro management dialog — record, edit, and manage macros."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QLineEdit, QTextEdit, QSplitter, QGroupBox,
    QMessageBox, QInputDialog, QFileDialog, QKeySequenceEdit,
    QCheckBox, QFormLayout
)
from PySide6.QtCore import Qt, Slot, QTimer
from PySide6.QtGui import QFont, QKeySequence

from linguaedit.services.macros import get_macro_manager, MacroActionType


class MacroDialog(QDialog):
    """Dialog for managing macros."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Manage Macros"))
        self.setModal(True)
        self.resize(800, 600)
        
        self._macro_manager = get_macro_manager()
        self._recording_timer = QTimer()
        self._recording_timer.timeout.connect(self._update_recording_status)
        
        # Connect signals
        self._macro_manager.recorder.recording_started.connect(self._on_recording_started)
        self._macro_manager.recorder.recording_stopped.connect(self._on_recording_stopped)
        self._macro_manager.recorder.action_recorded.connect(self._on_action_recorded)
        self._macro_manager.macro_added.connect(self._refresh_macros)
        self._macro_manager.macro_removed.connect(self._refresh_macros)
        self._macro_manager.macro_modified.connect(self._refresh_macros)
        
        self._build_ui()
        self._refresh_macros()
    
    def _build_ui(self):
        """Build the dialog UI."""
        layout = QVBoxLayout(self)
        
        # Top buttons
        button_layout = QHBoxLayout()
        
        self._record_btn = QPushButton(self.tr("Record New Macro"))
        self._record_btn.clicked.connect(self._on_record_macro)
        button_layout.addWidget(self._record_btn)
        
        self._stop_record_btn = QPushButton(self.tr("Stop Recording"))
        self._stop_record_btn.clicked.connect(self._on_stop_recording)
        self._stop_record_btn.setEnabled(False)
        button_layout.addWidget(self._stop_record_btn)
        
        button_layout.addStretch()
        
        self._import_btn = QPushButton(self.tr("Import"))
        self._import_btn.clicked.connect(self._on_import_macro)
        button_layout.addWidget(self._import_btn)
        
        self._export_btn = QPushButton(self.tr("Export"))
        self._export_btn.clicked.connect(self._on_export_macro)
        self._export_btn.setEnabled(False)
        button_layout.addWidget(self._export_btn)
        
        layout.addLayout(button_layout)
        
        # Recording status
        self._status_label = QLabel(self.tr("Ready to record"))
        self._status_label.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(self._status_label)
        
        # Main content
        splitter = QSplitter(Qt.Horizontal)
        
        # Macro list
        left_widget = QGroupBox(self.tr("Macros"))
        left_layout = QVBoxLayout(left_widget)
        
        self._macro_list = QListWidget()
        self._macro_list.itemSelectionChanged.connect(self._on_macro_selected)
        left_layout.addWidget(self._macro_list)
        
        # List buttons
        list_buttons = QHBoxLayout()
        
        self._play_btn = QPushButton(self.tr("Play"))
        self._play_btn.clicked.connect(self._on_play_macro)
        self._play_btn.setEnabled(False)
        list_buttons.addWidget(self._play_btn)
        
        self._rename_btn = QPushButton(self.tr("Rename"))
        self._rename_btn.clicked.connect(self._on_rename_macro)
        self._rename_btn.setEnabled(False)
        list_buttons.addWidget(self._rename_btn)
        
        self._delete_btn = QPushButton(self.tr("Delete"))
        self._delete_btn.clicked.connect(self._on_delete_macro)
        self._delete_btn.setEnabled(False)
        list_buttons.addWidget(self._delete_btn)
        
        left_layout.addLayout(list_buttons)
        splitter.addWidget(left_widget)
        
        # Macro details
        right_widget = QGroupBox(self.tr("Macro Details"))
        right_layout = QVBoxLayout(right_widget)
        
        # Properties form
        form_layout = QFormLayout()
        
        self._name_edit = QLineEdit()
        self._name_edit.setReadOnly(True)
        form_layout.addRow(self.tr("Name:"), self._name_edit)
        
        self._shortcut_edit = QKeySequenceEdit()
        self._shortcut_edit.editingFinished.connect(self._on_shortcut_changed)
        form_layout.addRow(self.tr("Shortcut:"), self._shortcut_edit)
        
        self._enabled_check = QCheckBox()
        self._enabled_check.toggled.connect(self._on_enabled_changed)
        form_layout.addRow(self.tr("Enabled:"), self._enabled_check)
        
        right_layout.addLayout(form_layout)
        
        # Description
        self._description_edit = QTextEdit()
        self._description_edit.setMaximumHeight(80)
        self._description_edit.textChanged.connect(self._on_description_changed)
        right_layout.addWidget(QLabel(self.tr("Description:")))
        right_layout.addWidget(self._description_edit)
        
        # Actions
        self._actions_edit = QTextEdit()
        self._actions_edit.setReadOnly(True)
        right_layout.addWidget(QLabel(self.tr("Actions:")))
        right_layout.addWidget(self._actions_edit)
        
        splitter.addWidget(right_widget)
        layout.addWidget(splitter)
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        close_btn = QPushButton(self.tr("Close"))
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        # Initial state
        self._clear_details()
    
    def _refresh_macros(self):
        """Refresh the macro list."""
        self._macro_list.clear()
        
        macros = self._macro_manager.get_all_macros()
        for name, macro in macros.items():
            item = QListWidgetItem(name)
            if not macro.enabled:
                item.setToolTip(self.tr("Disabled"))
                font = item.font()
                font.setItalic(True)
                item.setFont(font)
            
            self._macro_list.addItem(item)
        
        self._clear_details()
    
    def _clear_details(self):
        """Clear macro details."""
        self._name_edit.clear()
        self._shortcut_edit.clear()
        self._enabled_check.setChecked(False)
        self._description_edit.clear()
        self._actions_edit.clear()
        
        self._play_btn.setEnabled(False)
        self._rename_btn.setEnabled(False)
        self._delete_btn.setEnabled(False)
        self._export_btn.setEnabled(False)
    
    @Slot()
    def _on_macro_selected(self):
        """Handle macro selection."""
        current_item = self._macro_list.currentItem()
        if not current_item:
            self._clear_details()
            return
        
        macro_name = current_item.text()
        macro = self._macro_manager.get_macro(macro_name)
        
        if not macro:
            self._clear_details()
            return
        
        # Update details
        self._name_edit.setText(macro.name)
        
        if macro.shortcut:
            self._shortcut_edit.setKeySequence(QKeySequence(macro.shortcut))
        else:
            self._shortcut_edit.clear()
        
        self._enabled_check.setChecked(macro.enabled)
        self._description_edit.setPlainText(macro.description)
        
        # Format actions
        actions_text = []
        for i, action in enumerate(macro.actions):
            action_desc = self._format_action(action)
            actions_text.append(f"{i+1:3d}. {action_desc}")
        
        if actions_text:
            self._actions_edit.setPlainText("\n".join(actions_text))
        else:
            self._actions_edit.setPlainText(self.tr("No actions recorded"))
        
        # Enable buttons
        self._play_btn.setEnabled(macro.enabled)
        self._rename_btn.setEnabled(True)
        self._delete_btn.setEnabled(True)
        self._export_btn.setEnabled(True)
    
    def _format_action(self, action) -> str:
        """Format an action for display."""
        action_type = action.action_type
        params = action.parameters
        
        if action_type == MacroActionType.EDIT_TEXT:
            text_preview = params.get("text", "")[:50]
            if len(params.get("text", "")) > 50:
                text_preview += "..."
            return f"Edit text: '{text_preview}'"
        
        elif action_type == MacroActionType.NAVIGATE:
            direction = params.get("direction", "unknown")
            return f"Navigate {direction}"
        
        elif action_type == MacroActionType.SEARCH_REPLACE:
            search = params.get("search_text", "")[:30]
            replace = params.get("replace_text", "")[:30]
            return f"Search/Replace: '{search}' → '{replace}'"
        
        elif action_type == MacroActionType.SET_FUZZY:
            fuzzy = params.get("fuzzy", False)
            return f"Set fuzzy: {fuzzy}"
        
        elif action_type == MacroActionType.SET_TRANSLATED:
            translated = params.get("translated", True)
            return f"Set translated: {translated}"
        
        elif action_type == MacroActionType.INSERT_TEXT:
            text = params.get("text", "")[:30]
            if len(params.get("text", "")) > 30:
                text += "..."
            return f"Insert text: '{text}'"
        
        else:
            return f"{action_type.value}: {params}"
    
    @Slot()
    def _on_record_macro(self):
        """Start recording a new macro."""
        if self._macro_manager.is_recording:
            return
        
        # Get macro name
        name, ok = QInputDialog.getText(
            self, 
            self.tr("Record Macro"),
            self.tr("Enter macro name:")
        )
        
        if not ok or not name.strip():
            return
        
        name = name.strip()
        
        # Check if name already exists
        if self._macro_manager.get_macro(name):
            QMessageBox.warning(
                self,
                self.tr("Macro Exists"),
                self.tr("A macro with this name already exists. Please choose a different name.")
            )
            return
        
        # Store name for when recording stops
        self._recording_macro_name = name
        
        # Start recording
        self._macro_manager.start_recording()
        
        # Close dialog during recording
        self.hide()
    
    @Slot()
    def _on_stop_recording(self):
        """Stop recording macro."""
        if not self._macro_manager.is_recording:
            return
        
        # Get description
        description, ok = QInputDialog.getText(
            self,
            self.tr("Macro Description"),
            self.tr("Enter macro description (optional):")
        )
        
        if not ok:
            description = ""
        
        # Stop and save
        success = self._macro_manager.stop_recording_and_save(
            self._recording_macro_name, 
            description
        )
        
        if success:
            QMessageBox.information(
                self,
                self.tr("Macro Saved"),
                self.tr("Macro '{}' has been saved successfully.").format(self._recording_macro_name)
            )
        else:
            QMessageBox.warning(
                self,
                self.tr("Recording Failed"),
                self.tr("Failed to save the macro. No actions were recorded.")
            )
        
        self._recording_macro_name = ""
    
    @Slot()
    def _on_recording_started(self):
        """Handle recording started."""
        self._record_btn.setEnabled(False)
        self._stop_record_btn.setEnabled(True)
        self._status_label.setText(self.tr("🔴 Recording in progress..."))
        self._status_label.setStyleSheet("color: red; font-weight: bold;")
        self._recording_timer.start(500)  # Update every 500ms
    
    @Slot()
    def _on_recording_stopped(self):
        """Handle recording stopped."""
        self._record_btn.setEnabled(True)
        self._stop_record_btn.setEnabled(False)
        self._status_label.setText(self.tr("Ready to record"))
        self._status_label.setStyleSheet("color: gray; font-style: italic;")
        self._recording_timer.stop()
        
        # Show dialog again
        self.show()
    
    @Slot()
    def _on_action_recorded(self):
        """Handle action recorded."""
        # Update status to show number of actions
        if hasattr(self._macro_manager.recorder, '_current_macro'):
            count = len(self._macro_manager.recorder._current_macro)
            self._status_label.setText(
                self.tr("🔴 Recording... ({} actions)").format(count)
            )
    
    @Slot()
    def _update_recording_status(self):
        """Update recording status periodically."""
        if self._macro_manager.is_recording:
            current_text = self._status_label.text()
            if current_text.endswith("..."):
                self._status_label.setText(current_text[:-3])
            else:
                self._status_label.setText(current_text + "...")
    
    @Slot()
    def _on_play_macro(self):
        """Play the selected macro."""
        current_item = self._macro_list.currentItem()
        if not current_item:
            return
        
        macro_name = current_item.text()
        
        # Get main window for playback target
        main_window = self.parent()
        while main_window and not hasattr(main_window, '_on_next'):
            main_window = main_window.parent()
        
        if not main_window:
            QMessageBox.warning(
                self,
                self.tr("Playback Error"),
                self.tr("Cannot find main window for macro playback.")
            )
            return
        
        # Play macro
        success = self._macro_manager.play_macro(macro_name, main_window)
        
        if not success:
            QMessageBox.warning(
                self,
                self.tr("Playback Error"),
                self.tr("Failed to play macro '{}'.").format(macro_name)
            )
        else:
            # Close dialog during playback
            self.accept()
    
    @Slot()
    def _on_rename_macro(self):
        """Rename the selected macro."""
        current_item = self._macro_list.currentItem()
        if not current_item:
            return
        
        old_name = current_item.text()
        
        new_name, ok = QInputDialog.getText(
            self,
            self.tr("Rename Macro"),
            self.tr("Enter new name:"),
            text=old_name
        )
        
        if not ok or not new_name.strip():
            return
        
        new_name = new_name.strip()
        
        if new_name == old_name:
            return
        
        success = self._macro_manager.rename_macro(old_name, new_name)
        
        if not success:
            QMessageBox.warning(
                self,
                self.tr("Rename Failed"),
                self.tr("Failed to rename macro. The new name may already exist.")
            )
    
    @Slot()
    def _on_delete_macro(self):
        """Delete the selected macro."""
        current_item = self._macro_list.currentItem()
        if not current_item:
            return
        
        macro_name = current_item.text()
        
        reply = QMessageBox.question(
            self,
            self.tr("Delete Macro"),
            self.tr("Are you sure you want to delete the macro '{}'?").format(macro_name),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            success = self._macro_manager.delete_macro(macro_name)
            
            if not success:
                QMessageBox.warning(
                    self,
                    self.tr("Delete Failed"),
                    self.tr("Failed to delete macro.")
                )
    
    @Slot()
    def _on_shortcut_changed(self):
        """Handle shortcut change."""
        current_item = self._macro_list.currentItem()
        if not current_item:
            return
        
        macro_name = current_item.text()
        shortcut = self._shortcut_edit.keySequence().toString()
        
        self._macro_manager.update_macro(macro_name, shortcut=shortcut)
    
    @Slot()
    def _on_enabled_changed(self, enabled: bool):
        """Handle enabled state change."""
        current_item = self._macro_list.currentItem()
        if not current_item:
            return
        
        macro_name = current_item.text()
        self._macro_manager.update_macro(macro_name, enabled=enabled)
        
        # Update play button
        self._play_btn.setEnabled(enabled)
        
        # Update item appearance
        font = current_item.font()
        font.setItalic(not enabled)
        current_item.setFont(font)
    
    @Slot()
    def _on_description_changed(self):
        """Handle description change."""
        current_item = self._macro_list.currentItem()
        if not current_item:
            return
        
        macro_name = current_item.text()
        description = self._description_edit.toPlainText()
        
        self._macro_manager.update_macro(macro_name, description=description)
    
    @Slot()
    def _on_import_macro(self):
        """Import a macro from file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Import Macro"),
            "",
            self.tr("JSON Files (*.json)")
        )
        
        if not file_path:
            return
        
        try:
            from pathlib import Path
            success, message = self._macro_manager.import_macro(Path(file_path))
            
            if success:
                QMessageBox.information(self, self.tr("Import Successful"), message)
            else:
                QMessageBox.warning(self, self.tr("Import Failed"), message)
                
        except Exception as e:
            QMessageBox.critical(
                self,
                self.tr("Import Error"),
                self.tr("Failed to import macro: {}").format(str(e))
            )
    
    @Slot()
    def _on_export_macro(self):
        """Export the selected macro to file."""
        current_item = self._macro_list.currentItem()
        if not current_item:
            return
        
        macro_name = current_item.text()
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Export Macro"),
            f"{macro_name}.json",
            self.tr("JSON Files (*.json)")
        )
        
        if not file_path:
            return
        
        try:
            from pathlib import Path
            success = self._macro_manager.export_macro(macro_name, Path(file_path))
            
            if success:
                QMessageBox.information(
                    self,
                    self.tr("Export Successful"),
                    self.tr("Macro exported to {}").format(file_path)
                )
            else:
                QMessageBox.warning(
                    self,
                    self.tr("Export Failed"),
                    self.tr("Failed to export macro.")
                )
                
        except Exception as e:
            QMessageBox.critical(
                self,
                self.tr("Export Error"),
                self.tr("Failed to export macro: {}").format(str(e))
            )


class RecordMacroDialog(QDialog):
    """Simple dialog shown during macro recording."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Recording Macro"))
        self.setModal(False)
        self.setWindowFlags(Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.resize(300, 100)
        
        layout = QVBoxLayout(self)
        
        status_label = QLabel(self.tr("🔴 Recording macro..."))
        status_label.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setPointSize(font.pointSize() + 2)
        font.setBold(True)
        status_label.setFont(font)
        status_label.setStyleSheet("color: red;")
        layout.addWidget(status_label)
        
        stop_btn = QPushButton(self.tr("Stop Recording"))
        stop_btn.clicked.connect(self.accept)
        layout.addWidget(stop_btn)