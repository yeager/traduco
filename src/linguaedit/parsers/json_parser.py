"""JSON i18n file parser (flat key-value and nested)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class JSONEntry:
    """A single JSON translation unit."""
    key: str  # dot-separated for nested
    value: str
    comment: str = ""

    @property
    def is_translated(self) -> bool:
        return bool(self.value)


@dataclass
class JSONFileData:
    """Parsed JSON i18n file."""
    path: Path
    entries: list[JSONEntry]

    @property
    def translated_count(self) -> int:
        return sum(1 for e in self.entries if e.is_translated)

    @property
    def untranslated_count(self) -> int:
        return sum(1 for e in self.entries if not e.is_translated)

    @property
    def total_count(self) -> int:
        return len(self.entries)

    @property
    def percent_translated(self) -> float:
        total = self.total_count
        return round(self.translated_count / total * 100, 1) if total else 100.0


def _flatten(obj: dict, prefix: str = "") -> list[JSONEntry]:
    """Flatten nested dict to dot-separated keys."""
    entries = []
    for k, v in obj.items():
        full_key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            entries.extend(_flatten(v, full_key))
        else:
            entries.append(JSONEntry(key=full_key, value=str(v) if v else ""))
    return entries


def _unflatten(entries: list[JSONEntry]) -> dict:
    """Unflatten dot-separated keys back to nested dict."""
    result: dict = {}
    for entry in entries:
        parts = entry.key.split(".")
        d = result
        for part in parts[:-1]:
            d = d.setdefault(part, {})
        d[parts[-1]] = entry.value
    return result


def parse_json(path: str | Path) -> JSONFileData:
    """Parse a JSON i18n file."""
    path = Path(path)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    entries = _flatten(data) if isinstance(data, dict) else []
    return JSONFileData(path=path, entries=entries)


def save_json(data: JSONFileData, path: Optional[str | Path] = None) -> None:
    """Save a JSON i18n file."""
    out = Path(path) if path else data.path
    obj = _unflatten(data.entries)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")
