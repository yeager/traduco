"""Glossary / terminology management."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

GLOSSARY_FILE = Path.home() / ".config" / "linguaedit" / "glossary.json"


@dataclass
class GlossaryTerm:
    """A glossary term."""
    source: str
    target: str
    notes: str = ""
    domain: str = ""


@dataclass
class GlossaryViolation:
    """A glossary consistency violation."""
    term: GlossaryTerm
    entry_index: int
    found_translation: str
    message: str = ""


def _load_glossary() -> list[dict]:
    if GLOSSARY_FILE.exists():
        try:
            return json.loads(GLOSSARY_FILE.read_text("utf-8"))
        except Exception:
            return []
    return []


def _save_glossary(terms: list[dict]) -> None:
    GLOSSARY_FILE.parent.mkdir(parents=True, exist_ok=True)
    GLOSSARY_FILE.write_text(json.dumps(terms, ensure_ascii=False, indent=2), "utf-8")


def get_terms() -> list[GlossaryTerm]:
    """Load all glossary terms."""
    data = _load_glossary()
    return [GlossaryTerm(
        source=t.get("source", ""),
        target=t.get("target", ""),
        notes=t.get("notes", ""),
        domain=t.get("domain", ""),
    ) for t in data]


def add_term(source: str, target: str, notes: str = "", domain: str = "") -> None:
    """Add or update a glossary term."""
    data = _load_glossary()
    for t in data:
        if t["source"].lower() == source.lower():
            t["target"] = target
            t["notes"] = notes
            t["domain"] = domain
            _save_glossary(data)
            return
    data.append({"source": source, "target": target, "notes": notes, "domain": domain})
    _save_glossary(data)


def remove_term(source: str) -> None:
    """Remove a glossary term."""
    data = _load_glossary()
    data = [t for t in data if t.get("source", "").lower() != source.lower()]
    _save_glossary(data)


def check_glossary(entries: list[dict]) -> list[GlossaryViolation]:
    """Check translations against glossary.

    Each entry: {"index": int, "msgid": str, "msgstr": str}
    Returns list of violations where a glossary source term appears
    in msgid but the expected target is not in msgstr.
    """
    terms = get_terms()
    if not terms:
        return []

    violations = []
    for entry in entries:
        idx = entry.get("index", -1)
        msgid = entry.get("msgid", "").lower()
        msgstr = entry.get("msgstr", "").lower()
        if not msgid or not msgstr:
            continue
        for term in terms:
            if term.source.lower() in msgid:
                if term.target.lower() not in msgstr:
                    violations.append(GlossaryViolation(
                        term=term, entry_index=idx,
                        found_translation=entry.get("msgstr", ""),
                        message=f"Expected '{term.target}' for '{term.source}', not found in translation",
                    ))
    return violations
