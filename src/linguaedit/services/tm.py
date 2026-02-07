"""Translation Memory (TM) — simple file-based fuzzy matching."""

from __future__ import annotations

import json
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

TM_DIR = Path.home() / ".config" / "linguaedit"
TM_FILE = TM_DIR / "tm.json"


@dataclass
class TMMatch:
    """A translation memory match."""
    source: str
    target: str
    similarity: float  # 0.0 – 1.0


def _load_tm() -> list[dict]:
    if TM_FILE.exists():
        try:
            return json.loads(TM_FILE.read_text("utf-8"))
        except Exception:
            return []
    return []


def _save_tm(entries: list[dict]) -> None:
    TM_DIR.mkdir(parents=True, exist_ok=True)
    TM_FILE.write_text(json.dumps(entries, ensure_ascii=False, indent=1), "utf-8")


def add_to_tm(source: str, target: str) -> None:
    """Add or update a TM entry."""
    if not source.strip() or not target.strip():
        return
    entries = _load_tm()
    # Update existing
    for e in entries:
        if e["s"] == source:
            e["t"] = target
            _save_tm(entries)
            return
    entries.append({"s": source, "t": target})
    # Cap at 10000
    if len(entries) > 10000:
        entries = entries[-10000:]
    _save_tm(entries)


def lookup_tm(source: str, threshold: float = 0.6, max_results: int = 5) -> list[TMMatch]:
    """Find TM matches above threshold."""
    if not source.strip():
        return []
    entries = _load_tm()
    matches = []
    for e in entries:
        sim = SequenceMatcher(None, source.lower(), e["s"].lower()).ratio()
        if sim >= threshold:
            matches.append(TMMatch(source=e["s"], target=e["t"], similarity=sim))
    matches.sort(key=lambda m: m.similarity, reverse=True)
    return matches[:max_results]


def feed_file_to_tm(entries: list[tuple[str, str]]) -> int:
    """Bulk-add translated pairs to TM. Returns count added."""
    count = 0
    for src, tgt in entries:
        if src.strip() and tgt.strip():
            add_to_tm(src, tgt)
            count += 1
    return count
