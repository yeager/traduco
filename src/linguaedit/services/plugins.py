"""Plugin system for LinguaEdit — extensible linting, suggestions, and transformations."""

from __future__ import annotations

import importlib.util
import inspect
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import QObject, Signal

from linguaedit.services.linter import LintIssue


@dataclass
class PluginInfo:
    """Information about a loaded plugin."""
    name: str
    version: str
    description: str
    author: str
    enabled: bool
    file_path: Path
    instance: Any


class PluginBase:
    """Base class that plugins should inherit from (optional)."""
    
    @property
    def name(self) -> str:
        return getattr(self, '_name', self.__class__.__name__)
    
    @property
    def version(self) -> str:
        return getattr(self, '_version', '1.0.0')
    
    @property
    def description(self) -> str:
        return getattr(self, '_description', 'No description provided')
    
    @property
    def author(self) -> str:
        return getattr(self, '_author', 'Unknown')
    
    def lint_entry(self, source: str, target: str) -> list[LintIssue]:
        """Check a translation entry and return lint issues."""
        return []
    
    def suggest(self, source: str, lang: str) -> list[str]:
        """Generate suggestions for translating source text."""
        return []
    
    def transform(self, text: str) -> str:
        """Transform text (e.g., fix formatting, apply rules)."""
        return text


class PluginManager(QObject):
    """Manages loading, enabling/disabling, and using plugins."""
    
    plugins_changed = Signal()
    
    def __init__(self):
        super().__init__()
        self._plugins: dict[str, PluginInfo] = {}
        self._plugin_dir = Path.home() / ".local" / "share" / "linguaedit" / "plugins"
        self._config_file = Path.home() / ".config" / "linguaedit" / "plugins.json"
        self._ensure_directories()
        self._load_config()
    
    def _ensure_directories(self):
        """Create plugin directories if they don't exist."""
        self._plugin_dir.mkdir(parents=True, exist_ok=True)
        self._config_file.parent.mkdir(parents=True, exist_ok=True)
    
    def _load_config(self):
        """Load plugin enable/disable state from config."""
        self._enabled_plugins = set()
        if self._config_file.exists():
            try:
                config = json.loads(self._config_file.read_text("utf-8"))
                self._enabled_plugins = set(config.get("enabled_plugins", []))
            except Exception:
                pass
    
    def _save_config(self):
        """Save plugin enable/disable state to config."""
        config = {
            "enabled_plugins": list(self._enabled_plugins)
        }
        self._config_file.write_text(
            json.dumps(config, ensure_ascii=False, indent=2), "utf-8"
        )
    
    def load_plugins(self):
        """Load all plugins from the plugin directory."""
        self._plugins.clear()
        
        for plugin_file in self._plugin_dir.glob("*.py"):
            if plugin_file.name.startswith("_"):
                continue  # Skip private files
            
            try:
                self._load_plugin(plugin_file)
            except Exception as e:
                print(f"Failed to load plugin {plugin_file.name}: {e}")
        
        self.plugins_changed.emit()
    
    def _load_plugin(self, plugin_file: Path):
        """Load a single plugin file."""
        spec = importlib.util.spec_from_file_location(
            plugin_file.stem, plugin_file
        )
        if not spec or not spec.loader:
            return
        
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Find Plugin class in module
        plugin_class = None
        for name, obj in inspect.getmembers(module):
            if (inspect.isclass(obj) and 
                name == "Plugin" and 
                obj != PluginBase):
                plugin_class = obj
                break
        
        if not plugin_class:
            return
        
        # Instantiate plugin
        plugin_instance = plugin_class()
        
        # Create plugin info
        plugin_info = PluginInfo(
            name=plugin_instance.name,
            version=plugin_instance.version,
            description=plugin_instance.description,
            author=plugin_instance.author,
            enabled=plugin_instance.name in self._enabled_plugins,
            file_path=plugin_file,
            instance=plugin_instance
        )
        
        self._plugins[plugin_instance.name] = plugin_info
    
    def get_plugins(self) -> dict[str, PluginInfo]:
        """Get all loaded plugins."""
        return self._plugins.copy()
    
    def enable_plugin(self, name: str):
        """Enable a plugin."""
        if name in self._plugins:
            self._enabled_plugins.add(name)
            self._plugins[name].enabled = True
            self._save_config()
            self.plugins_changed.emit()
    
    def disable_plugin(self, name: str):
        """Disable a plugin."""
        if name in self._plugins:
            self._enabled_plugins.discard(name)
            self._plugins[name].enabled = False
            self._save_config()
            self.plugins_changed.emit()
    
    def is_plugin_enabled(self, name: str) -> bool:
        """Check if a plugin is enabled."""
        plugin = self._plugins.get(name)
        return plugin.enabled if plugin else False
    
    def lint_with_plugins(self, source: str, target: str) -> list[LintIssue]:
        """Run linting through all enabled plugins."""
        issues = []
        for plugin_info in self._plugins.values():
            if not plugin_info.enabled:
                continue
            
            try:
                plugin_issues = plugin_info.instance.lint_entry(source, target)
                if plugin_issues:
                    issues.extend(plugin_issues)
            except Exception as e:
                print(f"Plugin {plugin_info.name} lint error: {e}")
        
        return issues
    
    def get_suggestions_from_plugins(self, source: str, lang: str) -> list[str]:
        """Get suggestions from all enabled plugins."""
        suggestions = []
        for plugin_info in self._plugins.values():
            if not plugin_info.enabled:
                continue
            
            try:
                plugin_suggestions = plugin_info.instance.suggest(source, lang)
                if plugin_suggestions:
                    suggestions.extend(plugin_suggestions)
            except Exception as e:
                print(f"Plugin {plugin_info.name} suggestion error: {e}")
        
        return suggestions
    
    def transform_with_plugins(self, text: str) -> str:
        """Apply transformations from all enabled plugins."""
        result = text
        for plugin_info in self._plugins.values():
            if not plugin_info.enabled:
                continue
            
            try:
                result = plugin_info.instance.transform(result)
            except Exception as e:
                print(f"Plugin {plugin_info.name} transform error: {e}")
        
        return result
    
    def reload_plugins(self):
        """Reload all plugins from disk."""
        # Unload modules
        for plugin_info in self._plugins.values():
            module_name = plugin_info.file_path.stem
            if module_name in sys.modules:
                del sys.modules[module_name]
        
        # Reload
        self.load_plugins()


# Global instance
_plugin_manager: Optional[PluginManager] = None


def get_plugin_manager() -> PluginManager:
    """Get the global plugin manager instance."""
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
        _plugin_manager.load_plugins()
    return _plugin_manager