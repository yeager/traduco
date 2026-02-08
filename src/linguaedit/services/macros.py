"""Macro recording and playback system for LinguaEdit."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QKeySequence


class MacroActionType(Enum):
    """Types of actions that can be recorded in macros."""
    EDIT_TEXT = "edit_text"
    NAVIGATE = "navigate"
    SEARCH_REPLACE = "search_replace"
    SET_FUZZY = "set_fuzzy"
    SET_TRANSLATED = "set_translated"
    APPLY_SUGGESTION = "apply_suggestion"
    INSERT_TEXT = "insert_text"
    DELETE_TEXT = "delete_text"
    MOVE_CURSOR = "move_cursor"
    SELECT_TEXT = "select_text"
    COPY_TEXT = "copy_text"
    PASTE_TEXT = "paste_text"
    FIND_NEXT = "find_next"
    FIND_PREVIOUS = "find_previous"


@dataclass
class MacroAction:
    """A single action in a macro."""
    action_type: MacroActionType
    parameters: Dict[str, Any]
    timestamp: float  # Relative to macro start


@dataclass
class Macro:
    """A recorded macro containing a sequence of actions."""
    name: str
    description: str
    actions: List[MacroAction]
    created_at: datetime
    modified_at: datetime
    shortcut: str = ""  # Keyboard shortcut
    enabled: bool = True


class MacroRecorder(QObject):
    """Records user actions for macro creation."""
    
    recording_started = Signal()
    recording_stopped = Signal()
    action_recorded = Signal(MacroAction)
    
    def __init__(self):
        super().__init__()
        self._recording = False
        self._current_macro: List[MacroAction] = []
        self._start_time: float = 0.0
    
    def start_recording(self):
        """Start recording a new macro."""
        if self._recording:
            return
        
        self._recording = True
        self._current_macro = []
        self._start_time = datetime.now().timestamp()
        self.recording_started.emit()
    
    def stop_recording(self) -> List[MacroAction]:
        """Stop recording and return the recorded actions."""
        if not self._recording:
            return []
        
        self._recording = False
        actions = self._current_macro.copy()
        self._current_macro = []
        self.recording_stopped.emit()
        return actions
    
    def record_action(self, action_type: MacroActionType, **parameters):
        """Record a single action."""
        if not self._recording:
            return
        
        current_time = datetime.now().timestamp()
        relative_time = current_time - self._start_time
        
        action = MacroAction(
            action_type=action_type,
            parameters=parameters,
            timestamp=relative_time
        )
        
        self._current_macro.append(action)
        self.action_recorded.emit(action)
    
    @property
    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self._recording


class MacroPlayer(QObject):
    """Plays back recorded macros."""
    
    playback_started = Signal(str)  # macro name
    playback_finished = Signal(str)
    action_executed = Signal(MacroAction)
    playback_error = Signal(str, str)  # macro name, error message
    
    def __init__(self):
        super().__init__()
        self._playing = False
        self._current_macro: Optional[str] = None
    
    def play_macro(self, macro: Macro, target_widget=None) -> bool:
        """Play a macro.
        
        Args:
            macro: The macro to play
            target_widget: Widget to apply actions to (usually the main window)
            
        Returns:
            True if playback started successfully
        """
        if self._playing:
            return False
        
        self._playing = True
        self._current_macro = macro.name
        self.playback_started.emit(macro.name)
        
        try:
            for action in macro.actions:
                if not self._playing:  # Check if stopped
                    break
                
                self._execute_action(action, target_widget)
                self.action_executed.emit(action)
            
            self.playback_finished.emit(macro.name)
            
        except Exception as e:
            self.playback_error.emit(macro.name, str(e))
        finally:
            self._playing = False
            self._current_macro = None
        
        return True
    
    def stop_playback(self):
        """Stop current playback."""
        self._playing = False
    
    def _execute_action(self, action: MacroAction, target_widget):
        """Execute a single macro action."""
        action_type = action.action_type
        params = action.parameters
        
        if not target_widget:
            return
        
        # Route actions to appropriate methods
        if action_type == MacroActionType.EDIT_TEXT:
            self._execute_edit_text(target_widget, params)
        elif action_type == MacroActionType.NAVIGATE:
            self._execute_navigate(target_widget, params)
        elif action_type == MacroActionType.SEARCH_REPLACE:
            self._execute_search_replace(target_widget, params)
        elif action_type == MacroActionType.SET_FUZZY:
            self._execute_set_fuzzy(target_widget, params)
        elif action_type == MacroActionType.SET_TRANSLATED:
            self._execute_set_translated(target_widget, params)
        elif action_type == MacroActionType.INSERT_TEXT:
            self._execute_insert_text(target_widget, params)
        # Add more action types as needed
    
    def _execute_edit_text(self, target_widget, params):
        """Execute text editing action."""
        entry_index = params.get("entry_index")
        new_text = params.get("text", "")
        
        if hasattr(target_widget, 'set_entry_text'):
            target_widget.set_entry_text(entry_index, new_text)
    
    def _execute_navigate(self, target_widget, params):
        """Execute navigation action."""
        direction = params.get("direction")
        
        if hasattr(target_widget, '_on_next') and direction == "next":
            target_widget._on_next()
        elif hasattr(target_widget, '_on_previous') and direction == "previous":
            target_widget._on_previous()
    
    def _execute_search_replace(self, target_widget, params):
        """Execute search and replace action."""
        search_text = params.get("search_text", "")
        replace_text = params.get("replace_text", "")
        
        if hasattr(target_widget, '_on_search_replace'):
            target_widget._on_search_replace(search_text, replace_text)
    
    def _execute_set_fuzzy(self, target_widget, params):
        """Execute set fuzzy flag action."""
        entry_index = params.get("entry_index")
        fuzzy = params.get("fuzzy", False)
        
        if hasattr(target_widget, 'set_entry_fuzzy'):
            target_widget.set_entry_fuzzy(entry_index, fuzzy)
    
    def _execute_set_translated(self, target_widget, params):
        """Execute set translated flag action."""
        entry_index = params.get("entry_index")
        translated = params.get("translated", True)
        
        if hasattr(target_widget, 'set_entry_translated'):
            target_widget.set_entry_translated(entry_index, translated)
    
    def _execute_insert_text(self, target_widget, params):
        """Execute insert text action."""
        text = params.get("text", "")
        position = params.get("position", -1)  # -1 = at cursor
        
        if hasattr(target_widget, 'insert_text_at_cursor'):
            target_widget.insert_text_at_cursor(text)
    
    @property
    def is_playing(self) -> bool:
        """Check if currently playing a macro."""
        return self._playing


class MacroManager(QObject):
    """Manages saved macros and provides the main interface."""
    
    macro_added = Signal(str)  # macro name
    macro_removed = Signal(str)
    macro_modified = Signal(str)
    
    def __init__(self):
        super().__init__()
        self._macros: Dict[str, Macro] = {}
        self._macros_file = Path.home() / ".config" / "linguaedit" / "macros.json"
        
        self.recorder = MacroRecorder()
        self.player = MacroPlayer()
        
        self._load_macros()
    
    def _load_macros(self):
        """Load macros from disk."""
        if not self._macros_file.exists():
            return
        
        try:
            data = json.loads(self._macros_file.read_text("utf-8"))
            
            for macro_data in data:
                actions = []
                for action_data in macro_data["actions"]:
                    action = MacroAction(
                        action_type=MacroActionType(action_data["action_type"]),
                        parameters=action_data["parameters"],
                        timestamp=action_data["timestamp"]
                    )
                    actions.append(action)
                
                macro = Macro(
                    name=macro_data["name"],
                    description=macro_data["description"],
                    actions=actions,
                    created_at=datetime.fromisoformat(macro_data["created_at"]),
                    modified_at=datetime.fromisoformat(macro_data["modified_at"]),
                    shortcut=macro_data.get("shortcut", ""),
                    enabled=macro_data.get("enabled", True)
                )
                
                self._macros[macro.name] = macro
                
        except Exception as e:
            print(f"Error loading macros: {e}")
    
    def _save_macros(self):
        """Save macros to disk."""
        self._macros_file.parent.mkdir(parents=True, exist_ok=True)
        
        data = []
        for macro in self._macros.values():
            actions_data = []
            for action in macro.actions:
                actions_data.append({
                    "action_type": action.action_type.value,
                    "parameters": action.parameters,
                    "timestamp": action.timestamp
                })
            
            macro_data = {
                "name": macro.name,
                "description": macro.description,
                "actions": actions_data,
                "created_at": macro.created_at.isoformat(),
                "modified_at": macro.modified_at.isoformat(),
                "shortcut": macro.shortcut,
                "enabled": macro.enabled
            }
            data.append(macro_data)
        
        self._macros_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), "utf-8"
        )
    
    def start_recording(self):
        """Start recording a new macro."""
        self.recorder.start_recording()
    
    def stop_recording_and_save(self, name: str, description: str = "") -> bool:
        """Stop recording and save the macro with given name.
        
        Returns True if macro was saved successfully.
        """
        actions = self.recorder.stop_recording()
        
        if not actions:
            return False
        
        if name in self._macros:
            return False  # Name already exists
        
        now = datetime.now()
        macro = Macro(
            name=name,
            description=description,
            actions=actions,
            created_at=now,
            modified_at=now
        )
        
        self._macros[name] = macro
        self._save_macros()
        self.macro_added.emit(name)
        return True
    
    def play_macro(self, name: str, target_widget=None) -> bool:
        """Play a macro by name."""
        macro = self._macros.get(name)
        if not macro or not macro.enabled:
            return False
        
        return self.player.play_macro(macro, target_widget)
    
    def get_macro(self, name: str) -> Optional[Macro]:
        """Get a macro by name."""
        return self._macros.get(name)
    
    def get_all_macros(self) -> Dict[str, Macro]:
        """Get all macros."""
        return self._macros.copy()
    
    def delete_macro(self, name: str) -> bool:
        """Delete a macro."""
        if name not in self._macros:
            return False
        
        del self._macros[name]
        self._save_macros()
        self.macro_removed.emit(name)
        return True
    
    def rename_macro(self, old_name: str, new_name: str) -> bool:
        """Rename a macro."""
        if old_name not in self._macros or new_name in self._macros:
            return False
        
        macro = self._macros[old_name]
        macro.name = new_name
        macro.modified_at = datetime.now()
        
        del self._macros[old_name]
        self._macros[new_name] = macro
        
        self._save_macros()
        self.macro_removed.emit(old_name)
        self.macro_added.emit(new_name)
        return True
    
    def update_macro(self, name: str, description: str = None, 
                    shortcut: str = None, enabled: bool = None) -> bool:
        """Update macro properties."""
        macro = self._macros.get(name)
        if not macro:
            return False
        
        if description is not None:
            macro.description = description
        
        if shortcut is not None:
            macro.shortcut = shortcut
        
        if enabled is not None:
            macro.enabled = enabled
        
        macro.modified_at = datetime.now()
        self._save_macros()
        self.macro_modified.emit(name)
        return True
    
    def export_macro(self, name: str, file_path: Path) -> bool:
        """Export a macro to a file."""
        macro = self._macros.get(name)
        if not macro:
            return False
        
        try:
            actions_data = []
            for action in macro.actions:
                actions_data.append({
                    "action_type": action.action_type.value,
                    "parameters": action.parameters,
                    "timestamp": action.timestamp
                })
            
            export_data = {
                "name": macro.name,
                "description": macro.description,
                "actions": actions_data,
                "created_at": macro.created_at.isoformat(),
                "modified_at": macro.modified_at.isoformat(),
                "shortcut": macro.shortcut,
                "enabled": macro.enabled,
                "exported_at": datetime.now().isoformat(),
                "version": "1.0"
            }
            
            file_path.write_text(
                json.dumps(export_data, ensure_ascii=False, indent=2), "utf-8"
            )
            return True
            
        except Exception:
            return False
    
    def import_macro(self, file_path: Path) -> tuple[bool, str]:
        """Import a macro from a file.
        
        Returns (success, message).
        """
        try:
            data = json.loads(file_path.read_text("utf-8"))
            
            name = data["name"]
            if name in self._macros:
                return False, f"Macro '{name}' already exists"
            
            actions = []
            for action_data in data["actions"]:
                action = MacroAction(
                    action_type=MacroActionType(action_data["action_type"]),
                    parameters=action_data["parameters"],
                    timestamp=action_data["timestamp"]
                )
                actions.append(action)
            
            macro = Macro(
                name=name,
                description=data["description"],
                actions=actions,
                created_at=datetime.fromisoformat(data["created_at"]),
                modified_at=datetime.now(),  # Update modified time
                shortcut=data.get("shortcut", ""),
                enabled=data.get("enabled", True)
            )
            
            self._macros[name] = macro
            self._save_macros()
            self.macro_added.emit(name)
            
            return True, f"Macro '{name}' imported successfully"
            
        except Exception as e:
            return False, f"Import failed: {str(e)}"
    
    @property
    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self.recorder.is_recording
    
    @property
    def is_playing(self) -> bool:
        """Check if currently playing a macro."""
        return self.player.is_playing


# Global instance
_macro_manager: Optional[MacroManager] = None


def get_macro_manager() -> MacroManager:
    """Get the global macro manager."""
    global _macro_manager
    if _macro_manager is None:
        _macro_manager = MacroManager()
    return _macro_manager