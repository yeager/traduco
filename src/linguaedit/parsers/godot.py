"""Godot CSV/TRES parser — hantera Godot projektfiler."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class GodotEntry:
    """En enskild översättning i Godot-format."""
    key: str
    translations: Dict[str, str] = field(default_factory=dict)
    comment: str = ""
    line_number: int = 0


@dataclass
class GodotFileData:
    """Godot CSV/TRES fildata."""
    path: Path
    format: str  # "csv" eller "tres"
    languages: List[str] = field(default_factory=list)
    entries: List[GodotEntry] = field(default_factory=list)
    header: List[str] = field(default_factory=list)
    encoding: str = "utf-8"
    delimiter: str = ","


def _detect_delimiter(content: str) -> str:
    """Detektera delimiter (komma eller tab)."""
    comma_count = content.count(',')
    tab_count = content.count('\t')
    return '\t' if tab_count > comma_count else ','


def _parse_csv_content(content: str, encoding: str = "utf-8") -> GodotFileData:
    """Parsa CSV-innehåll."""
    lines = content.splitlines()
    if not lines:
        return GodotFileData(Path(), "csv")
    
    delimiter = _detect_delimiter(content)
    
    # Läs header (första raden)
    reader = csv.reader([lines[0]], delimiter=delimiter)
    header = next(reader)
    
    if not header or len(header) < 2:
        raise ValueError(self.tr("Invalid CSV format: missing header"))
    
    # Första kolumnen är key, resten är språk
    languages = header[1:]
    entries = []
    
    # Parsa data-rader
    for line_num, line in enumerate(lines[1:], 2):
        if not line.strip() or line.startswith('#'):
            continue
            
        reader = csv.reader([line], delimiter=delimiter)
        try:
            row = next(reader)
        except csv.Error:
            continue
            
        if len(row) < 2:
            continue
            
        key = row[0].strip()
        if not key:
            continue
            
        translations = {}
        for i, lang in enumerate(languages):
            if i + 1 < len(row):
                translations[lang] = row[i + 1]
            else:
                translations[lang] = ""
                
        entry = GodotEntry(
            key=key,
            translations=translations,
            line_number=line_num
        )
        entries.append(entry)
    
    return GodotFileData(
        path=Path(),
        format="csv",
        languages=languages,
        entries=entries,
        header=header,
        delimiter=delimiter,
        encoding=encoding
    )


def _parse_tres_content(content: str) -> GodotFileData:
    """Parsa TRES-resursfil."""
    entries = []
    languages = set()
    
    # TRES format: [resource] följt av locale/key = "value" par
    lines = content.splitlines()
    current_key = None
    
    for line_num, line in enumerate(lines, 1):
        line = line.strip()
        
        # Skip kommentarer och tomma rader
        if not line or line.startswith(';') or line.startswith('#'):
            continue
            
        # Kolla efter locale/key = "value" pattern
        match = re.match(r'^([^/]+)/([^=]+)\s*=\s*"(.*)"$', line)
        if match:
            locale, key, value = match.groups()
            locale = locale.strip()
            key = key.strip()
            value = value.replace('\\"', '"')  # Unescape quotes
            
            languages.add(locale)
            
            # Hitta eller skapa entry
            entry = None
            for e in entries:
                if e.key == key:
                    entry = e
                    break
                    
            if not entry:
                entry = GodotEntry(key=key, line_number=line_num)
                entries.append(entry)
                
            entry.translations[locale] = value
    
    return GodotFileData(
        path=Path(),
        format="tres",
        languages=sorted(languages),
        entries=entries,
        encoding="utf-8"
    )


def parse_godot(path: Path) -> GodotFileData:
    """Parsa Godot CSV/TRES-fil."""
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    
    # Detektera format baserat på filändelse
    format_type = "tres" if path.suffix.lower() == ".tres" else "csv"
    
    # Läs fil med encoding-detektion
    content = ""
    encoding = "utf-8"
    
    for enc in ["utf-8", "latin1", "cp1252"]:
        try:
            content = path.read_text(encoding=enc)
            encoding = enc
            break
        except UnicodeDecodeError:
            continue
    
    if not content:
        raise ValueError(f"Could not decode file: {path}")
    
    # Parsa baserat på format
    if format_type == "tres":
        file_data = _parse_tres_content(content)
    else:
        file_data = _parse_csv_content(content, encoding)
    
    file_data.path = path
    file_data.encoding = encoding
    
    return file_data


def save_godot(file_data: GodotFileData, path: Optional[Path] = None) -> None:
    """Spara Godot CSV/TRES-fil."""
    if path:
        file_data.path = path
    
    if file_data.format == "tres":
        _save_tres(file_data)
    else:
        _save_csv(file_data)


def _save_csv(file_data: GodotFileData) -> None:
    """Spara CSV-format."""
    lines = []
    
    # Header
    header = ["key"] + file_data.languages
    lines.append(file_data.delimiter.join(header))
    
    # Data-rader
    for entry in file_data.entries:
        row = [entry.key]
        for lang in file_data.languages:
            value = entry.translations.get(lang, "")
            # Escape värden som innehåller delimiter
            if file_data.delimiter in value or '"' in value or '\n' in value:
                value = '"' + value.replace('"', '""') + '"'
            row.append(value)
        lines.append(file_data.delimiter.join(row))
    
    content = '\n'.join(lines)
    file_data.path.write_text(content, encoding=file_data.encoding)


def _save_tres(file_data: GodotFileData) -> None:
    """Spara TRES-format."""
    lines = []
    
    # TRES header
    lines.append("[gd_resource type=\"Translation\" format=3]")
    lines.append("")
    lines.append("[resource]")
    lines.append("")
    
    # Sortera entries och språk för konsistent output
    sorted_entries = sorted(file_data.entries, key=lambda e: e.key)
    sorted_langs = sorted(file_data.languages)
    
    for entry in sorted_entries:
        for lang in sorted_langs:
            if lang in entry.translations and entry.translations[lang]:
                value = entry.translations[lang]
                # Escape quotes
                value = value.replace('"', '\\"')
                lines.append(f'{lang}/{entry.key} = "{value}"')
    
    content = '\n'.join(lines)
    file_data.path.write_text(content, encoding=file_data.encoding)