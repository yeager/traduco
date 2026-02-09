"""SDLXLIFF (Trados Studio) file parser.

SDLXLIFF is XLIFF 1.2 with SDL-specific extensions including:
- sdl:seg-defs for segmentation definitions
- sdl:seg for segment markers within source/target
- sdl:cmt-defs for comment definitions
- sdl:value for custom metadata
"""
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from linguaedit.parsers import safe_parse_xml


_NS_XLIFF = "urn:oasis:names:tc:xliff:document:1.2"
_NS_SDL = "http://sdl.com/FileTypes/SdlXliff/1.0"

_NSMAP = {
    "xliff": _NS_XLIFF,
    "sdl": _NS_SDL,
}


def _ns(ns: str, tag: str) -> str:
    return f"{{{_NSMAP[ns]}}}{tag}"


def _text_content(el: Optional[ET.Element]) -> str:
    """Extract all text from an element, stripping inline tags (mrk, g, x, etc.)."""
    if el is None:
        return ""
    parts: list[str] = []
    if el.text:
        parts.append(el.text)
    for child in el:
        # Recurse into inline elements (mrk, g, bpt, ept, ph, etc.)
        parts.append(_text_content(child))
        if child.tail:
            parts.append(child.tail)
    return "".join(parts)


@dataclass
class SDLXLIFFEntry:
    """A single SDLXLIFF translation unit."""
    id: str
    source: str
    target: str = ""
    note: str = ""
    state: str = ""
    context: str = ""
    locked: bool = False
    origin: str = ""  # e.g. "interactive", "mt", "tm"
    match_percent: int = 0
    confirmed: bool = False

    @property
    def is_translated(self) -> bool:
        return bool(self.target)

    @property
    def is_fuzzy(self) -> bool:
        return self.state in (
            "needs-translation", "needs-review-translation",
            "needs-l10n", "new",
        ) or (self.is_translated and not self.confirmed)

    # Compatibility properties for window.py
    @property
    def msgid(self) -> str:
        return self.source

    @property
    def msgstr(self) -> str:
        return self.target

    @property
    def fuzzy(self) -> bool:
        return self.is_fuzzy


@dataclass
class SDLXLIFFFileData:
    """Parsed SDLXLIFF file."""
    path: Path
    entries: list[SDLXLIFFEntry]
    source_language: str = ""
    target_language: str = ""
    original: str = ""
    _tree: Optional[ET.ElementTree] = field(default=None, repr=False)

    @property
    def translated_count(self) -> int:
        return sum(1 for e in self.entries if e.is_translated and not e.is_fuzzy)

    @property
    def untranslated_count(self) -> int:
        return sum(1 for e in self.entries if not e.is_translated)

    @property
    def fuzzy_count(self) -> int:
        return sum(1 for e in self.entries if e.is_fuzzy)

    @property
    def total_count(self) -> int:
        return len(self.entries)

    @property
    def percent_translated(self) -> float:
        total = self.total_count
        return round(self.translated_count / total * 100, 1) if total else 100.0


def parse_sdlxliff(path: str | Path) -> SDLXLIFFFileData:
    """Parse an SDLXLIFF file."""
    path = Path(path)
    tree = safe_parse_xml(path)
    root = tree.getroot()

    # Register namespaces for round-trip fidelity
    ET.register_namespace("", _NS_XLIFF)
    ET.register_namespace("sdl", _NS_SDL)

    ns = f"{{{_NS_XLIFF}}}"
    sdl = f"{{{_NS_SDL}}}"

    entries: list[SDLXLIFFEntry] = []
    src_lang = ""
    tgt_lang = ""
    original = ""

    for file_el in root.iter(f"{ns}file"):
        src_lang = file_el.get("source-language", src_lang)
        tgt_lang = file_el.get("target-language", tgt_lang)
        original = file_el.get("original", original)

        # Parse SDL segment definitions for confirmation/origin info
        seg_defs: dict[str, dict] = {}
        for sd_el in file_el.iter(f"{sdl}seg-defs"):
            for seg in sd_el.iter(f"{sdl}seg"):
                seg_id = seg.get("id", "")
                seg_defs[seg_id] = {
                    "conf": seg.get("conf", ""),
                    "origin": seg.get("origin", ""),
                    "percent": int(seg.get("percent", "0") or "0"),
                    "locked": seg.get("locked", "false") == "true",
                }

        for body in file_el.iter(f"{ns}body"):
            for tu in body.iter(f"{ns}trans-unit"):
                uid = tu.get("id", "")

                source_el = tu.find(f"{ns}source")
                target_el = tu.find(f"{ns}target")

                source = _text_content(source_el)
                target = _text_content(target_el)

                state = ""
                if target_el is not None:
                    state = target_el.get("state", "")

                note_text = ""
                for note in tu.iter(f"{ns}note"):
                    note_text = note.text or ""

                # Check SDL segment info
                locked = False
                origin = ""
                match_percent = 0
                confirmed = False

                # Look up seg-def info by trans-unit id
                if uid in seg_defs:
                    sd = seg_defs[uid]
                    locked = sd["locked"]
                    origin = sd["origin"]
                    match_percent = sd["percent"]
                    confirmed = sd["conf"] in ("Translated", "ApprovedTranslation",
                                                "ApprovedSignOff")

                # Also check for sdl:seg-defs directly within the trans-unit
                for sd_el in tu.iter(f"{sdl}seg-defs"):
                    for seg in sd_el.iter(f"{sdl}seg"):
                        conf = seg.get("conf", "")
                        confirmed = conf in ("Translated", "ApprovedTranslation",
                                              "ApprovedSignOff")
                        origin = seg.get("origin", origin)
                        match_percent = int(seg.get("percent", "0") or "0")
                        locked = seg.get("locked", "false") == "true"

                entries.append(SDLXLIFFEntry(
                    id=uid,
                    source=source,
                    target=target,
                    note=note_text,
                    state=state,
                    locked=locked,
                    origin=origin,
                    match_percent=match_percent,
                    confirmed=confirmed,
                ))

    return SDLXLIFFFileData(
        path=path, entries=entries, source_language=src_lang,
        target_language=tgt_lang, original=original, _tree=tree,
    )


def save_sdlxliff(data: SDLXLIFFFileData, path: Optional[str | Path] = None) -> None:
    """Save an SDLXLIFF file.

    Preserves original XML structure; only updates target text and
    confirmation status to avoid losing SDL metadata.
    """
    out = Path(path) if path else data.path

    if data._tree is not None:
        # Round-trip: update targets in the original tree
        root = data._tree.getroot()
        ns = f"{{{_NS_XLIFF}}}"
        sdl = f"{{{_NS_SDL}}}"

        # Build lookup by id
        entry_map = {e.id: e for e in data.entries}

        for file_el in root.iter(f"{ns}file"):
            for body in file_el.iter(f"{ns}body"):
                for tu in body.iter(f"{ns}trans-unit"):
                    uid = tu.get("id", "")
                    entry = entry_map.get(uid)
                    if entry is None:
                        continue

                    target_el = tu.find(f"{ns}target")
                    if target_el is None:
                        target_el = ET.SubElement(tu, f"{ns}target")

                    # If target has inline markup, only update if it's plain text
                    if len(target_el) == 0:
                        target_el.text = entry.target

                    # Update SDL confirmation
                    for sd_el in tu.iter(f"{sdl}seg-defs"):
                        for seg in sd_el.iter(f"{sdl}seg"):
                            if entry.confirmed:
                                seg.set("conf", "Translated")
                            elif entry.target:
                                seg.set("conf", "Draft")

        ET.indent(data._tree, space="    ")
        data._tree.write(str(out), encoding="utf-8", xml_declaration=True)
    else:
        # Fallback: write as standard XLIFF 1.2
        from linguaedit.parsers.xliff_parser import XLIFFFileData, XLIFFEntry, save_xliff
        xliff_entries = [
            XLIFFEntry(id=e.id, source=e.source, target=e.target,
                       note=e.note, state=e.state)
            for e in data.entries
        ]
        xliff_data = XLIFFFileData(
            path=out, entries=xliff_entries,
            source_language=data.source_language,
            target_language=data.target_language,
            version="1.2", original=data.original,
        )
        save_xliff(xliff_data, out)
