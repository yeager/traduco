"""MQXLIFF (memoQ) file parser.

MQXLIFF is XLIFF 1.2 with memoQ-specific namespace extensions including:
- mq:seg-props for segment properties (status, locked, etc.)
- mq:key for segment keys
- mq:comment for memoQ comments
- Various status attributes (confirmed, locked, proofread, etc.)
"""
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from linguaedit.parsers import safe_parse_xml


_NS_XLIFF = "urn:oasis:names:tc:xliff:document:1.2"
_NS_MQ = "MQXliff"

_NSMAP = {
    "xliff": _NS_XLIFF,
    "mq": _NS_MQ,
}


def _text_content(el: Optional[ET.Element]) -> str:
    """Extract all text from an element, stripping inline tags."""
    if el is None:
        return ""
    parts: list[str] = []
    if el.text:
        parts.append(el.text)
    for child in el:
        parts.append(_text_content(child))
        if child.tail:
            parts.append(child.tail)
    return "".join(parts)


@dataclass
class MQXLIFFEntry:
    """A single MQXLIFF translation unit."""
    id: str
    source: str
    target: str = ""
    note: str = ""
    state: str = ""
    context: str = ""
    locked: bool = False
    confirmed: bool = False
    proofread: bool = False
    mq_status: str = ""  # memoQ-specific status

    @property
    def is_translated(self) -> bool:
        return bool(self.target)

    @property
    def is_fuzzy(self) -> bool:
        if self.state in ("needs-translation", "needs-review-translation",
                          "needs-l10n", "new"):
            return True
        return self.is_translated and not self.confirmed

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
class MQXLIFFFileData:
    """Parsed MQXLIFF file."""
    path: Path
    entries: list[MQXLIFFEntry]
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


def _detect_mq_namespace(root: ET.Element) -> str:
    """Detect the memoQ namespace URI used in the file."""
    # memoQ uses various namespace URIs; detect from the document
    for event, elem in ET.iterparse.__class__.__mro__:
        pass  # not needed, just check root attributes
    # Check all namespace declarations
    # ET doesn't directly expose xmlns, so check common patterns
    tag = root.tag
    # Try known memoQ namespace patterns
    for attr_name, attr_val in root.attrib.items():
        if "MQXliff" in attr_val or "mq" in attr_name.lower():
            return attr_val
    return _NS_MQ


def parse_mqxliff(path: str | Path) -> MQXLIFFFileData:
    """Parse an MQXLIFF file."""
    path = Path(path)

    # Pre-scan for memoQ namespace
    mq_ns = _NS_MQ
    with open(path, "r", encoding="utf-8") as f:
        header = f.read(2000)
        # Look for xmlns:mq="..." pattern
        import re
        m = re.search(r'xmlns:mq="([^"]+)"', header)
        if m:
            mq_ns = m.group(1)

    tree = safe_parse_xml(path)
    root = tree.getroot()

    ET.register_namespace("", _NS_XLIFF)
    ET.register_namespace("mq", mq_ns)

    ns = f"{{{_NS_XLIFF}}}"
    mq = f"{{{mq_ns}}}"

    entries: list[MQXLIFFEntry] = []
    src_lang = ""
    tgt_lang = ""
    original = ""

    for file_el in root.iter(f"{ns}file"):
        src_lang = file_el.get("source-language", src_lang)
        tgt_lang = file_el.get("target-language", tgt_lang)
        original = file_el.get("original", original)

        for body in file_el.iter(f"{ns}body"):
            for group in body.iter(f"{ns}group"):
                # memoQ wraps segments in groups
                for tu in group.iter(f"{ns}trans-unit"):
                    _parse_trans_unit(tu, ns, mq, entries)
            # Also handle trans-units directly in body
            for tu in body.findall(f"{ns}trans-unit"):
                _parse_trans_unit(tu, ns, mq, entries)

    return MQXLIFFFileData(
        path=path, entries=entries, source_language=src_lang,
        target_language=tgt_lang, original=original, _tree=tree,
    )


def _parse_trans_unit(tu: ET.Element, ns: str, mq: str,
                      entries: list[MQXLIFFEntry]) -> None:
    """Parse a single trans-unit element."""
    uid = tu.get("id", "")

    # Skip if already parsed (avoid duplicates from nested iteration)
    if any(e.id == uid for e in entries):
        return

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

    # memoQ properties
    locked = False
    confirmed = False
    proofread = False
    mq_status = ""

    # Check memoQ attributes on trans-unit
    for attr_name, attr_val in tu.attrib.items():
        attr_local = attr_name.split("}")[-1] if "}" in attr_name else attr_name
        if attr_local == "locked":
            locked = attr_val.lower() in ("true", "1", "yes")
        elif attr_local == "confirmed":
            confirmed = attr_val.lower() in ("true", "1", "yes")
        elif attr_local == "proofread":
            proofread = attr_val.lower() in ("true", "1", "yes")
        elif attr_local == "status":
            mq_status = attr_val

    # Check for mq:seg-props child
    for seg_props in tu.iter(f"{mq}seg-props"):
        locked = seg_props.get("locked", "false").lower() in ("true", "1")
        conf = seg_props.get("confirmed", "false")
        confirmed = conf.lower() in ("true", "1")

    # memoQ also uses translate="no" for locked segments
    if tu.get("translate", "yes") == "no":
        locked = True

    entries.append(MQXLIFFEntry(
        id=uid,
        source=source,
        target=target,
        note=note_text,
        state=state,
        locked=locked,
        confirmed=confirmed,
        proofread=proofread,
        mq_status=mq_status,
    ))


def save_mqxliff(data: MQXLIFFFileData, path: Optional[str | Path] = None) -> None:
    """Save an MQXLIFF file.

    Preserves original XML structure; only updates target text and
    confirmation status to avoid losing memoQ metadata.
    """
    out = Path(path) if path else data.path

    if data._tree is not None:
        root = data._tree.getroot()
        ns = f"{{{_NS_XLIFF}}}"

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

                    # Only update plain text targets
                    if len(target_el) == 0:
                        target_el.text = entry.target

                    if entry.confirmed and entry.target:
                        target_el.set("state", "translated")

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
