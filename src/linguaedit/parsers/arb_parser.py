"""Flutter ARB (Application Resource Bundle) parser."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ARBEntry:
    """A single ARB translation unit."""
    key: str
    value: str
    description: str = ""
    placeholders: dict = None

    @property
    def source(self) -> str:
        return self.key

    @property
    def target(self) -> str:
        return self.value

    @property
    def msgid(self) -> str:
        return self.key

    @property
    def msgstr(self) -> str:
        return self.value

    @property
    def is_translated(self) -> bool:
        return bool(self.value)

    @property
    def is_fuzzy(self) -> bool:
        return False

    @property
    def fuzzy(self) -> bool:
        return False


@dataclass
class ARBFileData:
    """Parsed ARB file."""
    path: Path
    entries: list[ARBEntry]
    locale: str = ""
    last_modified: str = ""
    extra_meta: dict = None

    @property
    def translated_count(self) -> int:
        return sum(1 for e in self.entries if e.is_translated)

    @property
    def untranslated_count(self) -> int:
        return sum(1 for e in self.entries if not e.is_translated)

    @property
    def fuzzy_count(self) -> int:
        return 0

    @property
    def total_count(self) -> int:
        return len(self.entries)

    @property
    def percent_translated(self) -> float:
        total = self.total_count
        return round(self.translated_count / total * 100, 1) if total else 100.0


def parse_arb(path: str | Path) -> ARBFileData:
    """Parse a Flutter ARB file."""
    path = Path(path)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    locale = data.get("@@locale", "")
    last_modified = data.get("@@last_modified", "")
    entries: list[ARBEntry] = []
    extra_meta = {}

    for key, value in data.items():
        if key.startswith("@@"):
            extra_meta[key] = value
            continue
        if key.startswith("@"):
            # Metadata for previous key — skip (handled below)
            continue
        description = ""
        placeholders = None
        meta_key = f"@{key}"
        if meta_key in data and isinstance(data[meta_key], dict):
            description = data[meta_key].get("description", "")
            placeholders = data[meta_key].get("placeholders")

        entries.append(ARBEntry(
            key=key, value=str(value) if value else "",
            description=description, placeholders=placeholders,
        ))

    return ARBFileData(
        path=path, entries=entries, locale=locale,
        last_modified=last_modified, extra_meta=extra_meta,
    )


def save_arb(data: ARBFileData, path: Optional[str | Path] = None) -> None:
    """Save a Flutter ARB file."""
    out = Path(path) if path else data.path
    obj = {}
    if data.locale:
        obj["@@locale"] = data.locale
    if data.last_modified:
        obj["@@last_modified"] = data.last_modified
    if data.extra_meta:
        for k, v in data.extra_meta.items():
            if k not in obj:
                obj[k] = v

    for entry in data.entries:
        obj[entry.key] = entry.value
        meta = {}
        if entry.description:
            meta["description"] = entry.description
        if entry.placeholders:
            meta["placeholders"] = entry.placeholders
        if meta:
            obj[f"@{entry.key}"] = meta

    with open(out, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")
