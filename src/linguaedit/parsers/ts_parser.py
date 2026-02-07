"""Qt TS (XML) file parser."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class TSEntry:
    """A single TS translation unit."""
    source: str
    translation: str = ""
    context_name: str = ""
    comment: str = ""
    location_file: str = ""
    location_line: str = ""
    translation_type: str = ""  # "unfinished", "obsolete", "vanished", ""

    @property
    def is_translated(self) -> bool:
        return bool(self.translation) and self.translation_type != "unfinished"

    @property
    def is_fuzzy(self) -> bool:
        return self.translation_type == "unfinished" and bool(self.translation)

    @property
    def is_obsolete(self) -> bool:
        return self.translation_type in ("obsolete", "vanished")


@dataclass
class TSFileData:
    """Parsed TS file."""
    path: Path
    entries: list[TSEntry]
    language: str = ""
    source_language: str = ""

    @property
    def translated_count(self) -> int:
        return sum(1 for e in self.entries if e.is_translated and not e.is_obsolete)

    @property
    def untranslated_count(self) -> int:
        return sum(1 for e in self.entries if not e.is_translated and not e.is_obsolete and not e.is_fuzzy)

    @property
    def fuzzy_count(self) -> int:
        return sum(1 for e in self.entries if e.is_fuzzy)

    @property
    def total_count(self) -> int:
        return sum(1 for e in self.entries if not e.is_obsolete)

    @property
    def percent_translated(self) -> float:
        total = self.total_count
        return round(self.translated_count / total * 100, 1) if total else 100.0


def parse_ts(path: str | Path) -> TSFileData:
    """Parse a Qt TS file."""
    path = Path(path)
    tree = ET.parse(str(path))
    root = tree.getroot()
    lang = root.get("language", "")
    src_lang = root.get("sourcelanguage", "")
    entries: list[TSEntry] = []

    for ctx in root.findall("context"):
        ctx_name = ctx.findtext("name", "")
        for msg in ctx.findall("message"):
            source = msg.findtext("source", "")
            trans_el = msg.find("translation")
            translation = trans_el.text or "" if trans_el is not None else ""
            trans_type = trans_el.get("type", "") if trans_el is not None else ""
            comment = msg.findtext("comment", "") or msg.findtext("extracomment", "")
            loc = msg.find("location")
            loc_file = loc.get("filename", "") if loc is not None else ""
            loc_line = loc.get("line", "") if loc is not None else ""
            entries.append(TSEntry(
                source=source, translation=translation, context_name=ctx_name,
                comment=comment or "", location_file=loc_file, location_line=loc_line,
                translation_type=trans_type,
            ))

    return TSFileData(path=path, entries=entries, language=lang, source_language=src_lang)


def save_ts(data: TSFileData, path: Optional[str | Path] = None) -> None:
    """Save a TS file."""
    out = Path(path) if path else data.path
    root = ET.Element("TS", version="2.1")
    if data.language:
        root.set("language", data.language)
    if data.source_language:
        root.set("sourcelanguage", data.source_language)

    contexts: dict[str, ET.Element] = {}
    for entry in data.entries:
        if entry.context_name not in contexts:
            ctx_el = ET.SubElement(root, "context")
            name_el = ET.SubElement(ctx_el, "name")
            name_el.text = entry.context_name
            contexts[entry.context_name] = ctx_el

        ctx_el = contexts[entry.context_name]
        msg = ET.SubElement(ctx_el, "message")
        if entry.location_file:
            loc = ET.SubElement(msg, "location")
            loc.set("filename", entry.location_file)
            if entry.location_line:
                loc.set("line", entry.location_line)
        src = ET.SubElement(msg, "source")
        src.text = entry.source
        if entry.comment:
            cmt = ET.SubElement(msg, "comment")
            cmt.text = entry.comment
        trans = ET.SubElement(msg, "translation")
        if entry.translation_type:
            trans.set("type", entry.translation_type)
        trans.text = entry.translation

    tree = ET.ElementTree(root)
    ET.indent(tree, space="    ")
    tree.write(str(out), encoding="utf-8", xml_declaration=True)
