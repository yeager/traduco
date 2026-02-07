"""YAML i18n parser (Rails i18n style)."""

from __future__ import annotations

import yaml
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class YAMLEntry:
    """A single YAML translation unit."""
    key: str  # dot-separated
    value: str
    comment: str = ""

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
class YAMLFileData:
    """Parsed YAML i18n file."""
    path: Path
    entries: list[YAMLEntry]
    root_key: str = ""  # e.g. "sv" for Rails i18n

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


def _flatten_yaml(obj, prefix: str = "") -> list[YAMLEntry]:
    """Flatten nested YAML dict."""
    entries = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            full_key = f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v, dict):
                entries.extend(_flatten_yaml(v, full_key))
            else:
                entries.append(YAMLEntry(key=full_key, value=str(v) if v is not None else ""))
    return entries


def _unflatten_yaml(entries: list[YAMLEntry]) -> dict:
    """Unflatten dot-separated keys."""
    result: dict = {}
    for entry in entries:
        parts = entry.key.split(".")
        d = result
        for part in parts[:-1]:
            d = d.setdefault(part, {})
        d[parts[-1]] = entry.value
    return result


def parse_yaml(path: str | Path) -> YAMLFileData:
    """Parse a YAML i18n file."""
    path = Path(path)
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        return YAMLFileData(path=path, entries=[])

    # Rails i18n: top-level key is locale
    root_key = ""
    keys = list(data.keys())
    if len(keys) == 1 and isinstance(data[keys[0]], dict):
        root_key = str(keys[0])
        entries = _flatten_yaml(data[root_key], root_key)
    else:
        entries = _flatten_yaml(data)

    return YAMLFileData(path=path, entries=entries, root_key=root_key)


def save_yaml(data: YAMLFileData, path: Optional[str | Path] = None) -> None:
    """Save a YAML i18n file."""
    out = Path(path) if path else data.path
    obj = _unflatten_yaml(data.entries)
    with open(out, "w", encoding="utf-8") as f:
        yaml.dump(obj, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
