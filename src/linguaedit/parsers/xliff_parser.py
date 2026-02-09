"""XLIFF 1.2 and 2.0 file parser."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from linguaedit.parsers import safe_parse_xml


@dataclass
class XLIFFEntry:
    """A single XLIFF translation unit."""
    id: str
    source: str
    target: str = ""
    note: str = ""
    state: str = ""  # "translated", "needs-translation", "final", etc.
    context: str = ""

    @property
    def is_translated(self) -> bool:
        return bool(self.target)

    @property
    def is_fuzzy(self) -> bool:
        return self.state in ("needs-translation", "needs-review-translation", "needs-l10n", "new")

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
class XLIFFFileData:
    """Parsed XLIFF file."""
    path: Path
    entries: list[XLIFFEntry]
    source_language: str = ""
    target_language: str = ""
    version: str = "1.2"  # "1.2" or "2.0"
    original: str = ""

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


# XLIFF 1.2 namespace
_NS_12 = {"xliff": "urn:oasis:names:tc:xliff:document:1.2"}
# XLIFF 2.0 namespace
_NS_20 = {"xliff": "urn:oasis:names:tc:xliff:document:2.0"}


def _detect_version(root: ET.Element) -> str:
    """Detect XLIFF version from root element."""
    version = root.get("version", "")
    if version.startswith("2"):
        return "2.0"
    tag = root.tag
    if "2.0" in tag:
        return "2.0"
    return "1.2"


def parse_xliff(path: str | Path) -> XLIFFFileData:
    """Parse an XLIFF file (1.2 or 2.0)."""
    path = Path(path)
    tree = safe_parse_xml(path)
    root = tree.getroot()
    version = _detect_version(root)

    # Strip namespace from tag for easier handling
    ns = ""
    if "}" in root.tag:
        ns = root.tag.split("}")[0] + "}"

    entries: list[XLIFFEntry] = []
    src_lang = ""
    tgt_lang = ""
    original = ""

    if version == "2.0":
        # XLIFF 2.0: <xliff><file><unit><segment><source/target>
        src_lang = root.get("srcLang", "")
        tgt_lang = root.get("trgLang", "")
        for file_el in root.iter(f"{ns}file"):
            original = file_el.get("original", original)
            for unit in file_el.iter(f"{ns}unit"):
                uid = unit.get("id", "")
                note_text = ""
                for note in unit.iter(f"{ns}note"):
                    note_text = note.text or ""
                for segment in unit.iter(f"{ns}segment"):
                    state = segment.get("state", "")
                    source_el = segment.find(f"{ns}source")
                    target_el = segment.find(f"{ns}target")
                    source = source_el.text or "" if source_el is not None else ""
                    target = target_el.text or "" if target_el is not None else ""
                    entries.append(XLIFFEntry(
                        id=uid, source=source, target=target,
                        note=note_text, state=state,
                    ))
    else:
        # XLIFF 1.2: <xliff><file><body><trans-unit>
        for file_el in root.iter(f"{ns}file"):
            src_lang = file_el.get("source-language", src_lang)
            tgt_lang = file_el.get("target-language", tgt_lang)
            original = file_el.get("original", original)
            for body in file_el.iter(f"{ns}body"):
                for tu in body.iter(f"{ns}trans-unit"):
                    uid = tu.get("id", "")
                    state = ""
                    source_el = tu.find(f"{ns}source")
                    target_el = tu.find(f"{ns}target")
                    source = source_el.text or "" if source_el is not None else ""
                    target = ""
                    if target_el is not None:
                        target = target_el.text or ""
                        state = target_el.get("state", "")
                    note_text = ""
                    for note in tu.iter(f"{ns}note"):
                        note_text = note.text or ""
                    entries.append(XLIFFEntry(
                        id=uid, source=source, target=target,
                        note=note_text, state=state,
                    ))

    return XLIFFFileData(
        path=path, entries=entries, source_language=src_lang,
        target_language=tgt_lang, version=version, original=original,
    )


def save_xliff(data: XLIFFFileData, path: Optional[str | Path] = None) -> None:
    """Save an XLIFF file."""
    out = Path(path) if path else data.path

    if data.version == "2.0":
        ns = "urn:oasis:names:tc:xliff:document:2.0"
        ET.register_namespace("", ns)
        root = ET.Element(f"{{{ns}}}xliff", version="2.0")
        root.set("srcLang", data.source_language)
        if data.target_language:
            root.set("trgLang", data.target_language)
        file_el = ET.SubElement(root, f"{{{ns}}}file", id="f1")
        if data.original:
            file_el.set("original", data.original)
        for entry in data.entries:
            unit = ET.SubElement(file_el, f"{{{ns}}}unit", id=entry.id)
            if entry.note:
                note = ET.SubElement(unit, f"{{{ns}}}note")
                note.text = entry.note
            segment = ET.SubElement(unit, f"{{{ns}}}segment")
            if entry.state:
                segment.set("state", entry.state)
            src = ET.SubElement(segment, f"{{{ns}}}source")
            src.text = entry.source
            tgt = ET.SubElement(segment, f"{{{ns}}}target")
            tgt.text = entry.target
    else:
        ns = "urn:oasis:names:tc:xliff:document:1.2"
        ET.register_namespace("", ns)
        root = ET.Element(f"{{{ns}}}xliff", version="1.2")
        file_el = ET.SubElement(root, f"{{{ns}}}file")
        file_el.set("source-language", data.source_language)
        if data.target_language:
            file_el.set("target-language", data.target_language)
        if data.original:
            file_el.set("original", data.original)
        file_el.set("datatype", "plaintext")
        body = ET.SubElement(file_el, f"{{{ns}}}body")
        for entry in data.entries:
            tu = ET.SubElement(body, f"{{{ns}}}trans-unit", id=entry.id)
            src = ET.SubElement(tu, f"{{{ns}}}source")
            src.text = entry.source
            tgt = ET.SubElement(tu, f"{{{ns}}}target")
            tgt.text = entry.target
            if entry.state:
                tgt.set("state", entry.state)
            if entry.note:
                note = ET.SubElement(tu, f"{{{ns}}}note")
                note.text = entry.note

    tree = ET.ElementTree(root)
    ET.indent(tree, space="    ")
    tree.write(str(out), encoding="utf-8", xml_declaration=True)
