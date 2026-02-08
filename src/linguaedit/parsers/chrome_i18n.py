"""Chrome Extension i18n JSON parser — hantera Chrome extension localization."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any


@dataclass
class ChromeI18nEntry:
    """En enskild översättning i Chrome i18n-format."""
    key: str
    message: str = ""
    description: str = ""
    placeholders: Dict[str, Any] = field(default_factory=dict)
    line_number: int = 0


@dataclass
class ChromeI18nFileData:
    """Chrome i18n JSON fildata."""
    path: Path
    entries: List[ChromeI18nEntry] = field(default_factory=list)
    encoding: str = "utf-8"
    indent: int = 2


def parse_chrome_i18n(path: Path) -> ChromeI18nFileData:
    """Parsa Chrome extension i18n JSON-fil."""
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    
    # Läs fil med encoding-detektion
    content = ""
    encoding = "utf-8"
    
    for enc in ["utf-8", "utf-8-sig", "latin1"]:
        try:
            content = path.read_text(encoding=enc)
            encoding = enc
            break
        except UnicodeDecodeError:
            continue
    
    if not content:
        raise ValueError(f"Could not decode file: {path}")
    
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")
    
    if not isinstance(data, dict):
        raise ValueError("Expected JSON object at root level")
    
    entries = []
    
    for key, value in data.items():
        if not isinstance(value, dict):
            continue
            
        message = value.get("message", "")
        description = value.get("description", "")
        placeholders = value.get("placeholders", {})
        
        entry = ChromeI18nEntry(
            key=key,
            message=message,
            description=description,
            placeholders=placeholders
        )
        entries.append(entry)
    
    return ChromeI18nFileData(
        path=path,
        entries=entries,
        encoding=encoding
    )


def save_chrome_i18n(file_data: ChromeI18nFileData, path: Optional[Path] = None) -> None:
    """Spara Chrome i18n JSON-fil."""
    if path:
        file_data.path = path
    
    # Bygg JSON-struktur
    data = {}
    
    for entry in file_data.entries:
        entry_data = {"message": entry.message}
        
        if entry.description:
            entry_data["description"] = entry.description
            
        if entry.placeholders:
            entry_data["placeholders"] = entry.placeholders
            
        data[entry.key] = entry_data
    
    # Serialisera med pretty-printing
    content = json.dumps(data, indent=file_data.indent, ensure_ascii=False, sort_keys=True)
    file_data.path.write_text(content, encoding=file_data.encoding)