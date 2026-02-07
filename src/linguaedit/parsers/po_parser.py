"""PO/POT file parser using polib."""

from __future__ import annotations

import polib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class TranslationEntry:
    """A single translation unit."""
    msgid: str
    msgstr: str
    msgid_plural: str = ""
    msgstr_plural: dict[int, str] = field(default_factory=dict)
    msgctxt: str = ""
    comment: str = ""
    tcomment: str = ""
    flags: list[str] = field(default_factory=list)
    occurrences: list[tuple[str, str]] = field(default_factory=list)
    obsolete: bool = False
    fuzzy: bool = False

    @classmethod
    def from_polib(cls, entry: polib.POEntry) -> "TranslationEntry":
        return cls(
            msgid=entry.msgid,
            msgstr=entry.msgstr,
            msgid_plural=entry.msgid_plural or "",
            msgstr_plural=dict(entry.msgstr_plural) if entry.msgstr_plural else {},
            msgctxt=entry.msgctxt or "",
            comment=entry.comment or "",
            tcomment=entry.tcomment or "",
            flags=list(entry.flags),
            occurrences=list(entry.occurrences),
            obsolete=entry.obsolete,
            fuzzy="fuzzy" in entry.flags,
        )

    def to_polib(self) -> polib.POEntry:
        entry = polib.POEntry(
            msgid=self.msgid,
            msgstr=self.msgstr,
            msgid_plural=self.msgid_plural or None,
            msgctxt=self.msgctxt or None,
            comment=self.comment,
            tcomment=self.tcomment,
            flags=self.flags,
            occurrences=self.occurrences,
        )
        if self.msgstr_plural:
            entry.msgstr_plural = self.msgstr_plural
        return entry


@dataclass
class POFileData:
    """Parsed PO file."""
    path: Path
    entries: list[TranslationEntry]
    metadata: dict[str, str]
    encoding: str = "utf-8"

    @property
    def translated_count(self) -> int:
        return sum(1 for e in self.entries if e.msgstr and not e.fuzzy and not e.obsolete)

    @property
    def untranslated_count(self) -> int:
        return sum(1 for e in self.entries if not e.msgstr and not e.obsolete)

    @property
    def fuzzy_count(self) -> int:
        return sum(1 for e in self.entries if e.fuzzy and not e.obsolete)

    @property
    def total_count(self) -> int:
        return sum(1 for e in self.entries if not e.obsolete)

    @property
    def percent_translated(self) -> float:
        total = self.total_count
        if total == 0:
            return 100.0
        return round(self.translated_count / total * 100, 1)


def parse_po(path: str | Path) -> POFileData:
    """Parse a PO or POT file."""
    path = Path(path)
    po = polib.pofile(str(path))
    entries = [TranslationEntry.from_polib(e) for e in po]
    metadata = dict(po.metadata) if po.metadata else {}
    return POFileData(path=path, entries=entries, metadata=metadata, encoding=po.encoding or "utf-8")


def save_po(data: POFileData, path: Optional[str | Path] = None) -> None:
    """Save a PO file."""
    out = Path(path) if path else data.path
    po = polib.POFile()
    po.metadata = data.metadata
    po.encoding = data.encoding
    for entry in data.entries:
        pe = entry.to_polib()
        if entry.obsolete:
            po.obsolete_entries().append(pe)
        else:
            po.append(pe)
    po.save(str(out))
