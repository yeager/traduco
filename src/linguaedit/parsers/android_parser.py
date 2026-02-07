"""Android strings.xml parser."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class AndroidEntry:
    """A single Android string resource."""
    key: str
    value: str
    comment: str = ""
    translatable: bool = True

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
class AndroidFileData:
    """Parsed Android strings.xml."""
    path: Path
    entries: list[AndroidEntry]

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


def parse_android(path: str | Path) -> AndroidFileData:
    """Parse an Android strings.xml file."""
    path = Path(path)
    tree = ET.parse(str(path))
    root = tree.getroot()
    entries: list[AndroidEntry] = []
    comment = ""

    for elem in root:
        if elem.tag is ET.Comment:
            comment = elem.text.strip() if elem.text else ""
            continue
        if elem.tag == "string":
            name = elem.get("name", "")
            translatable = elem.get("translatable", "true").lower() != "false"
            # Get inner text (may contain XML formatting)
            value = elem.text or ""
            entries.append(AndroidEntry(
                key=name, value=value, comment=comment,
                translatable=translatable,
            ))
            comment = ""
        elif elem.tag == "string-array":
            name = elem.get("name", "")
            for i, item in enumerate(elem.findall("item")):
                entries.append(AndroidEntry(
                    key=f"{name}[{i}]", value=item.text or "",
                    comment=comment,
                ))
            comment = ""
        elif elem.tag == "plurals":
            name = elem.get("name", "")
            for item in elem.findall("item"):
                quantity = item.get("quantity", "other")
                entries.append(AndroidEntry(
                    key=f"{name}:{quantity}", value=item.text or "",
                    comment=comment,
                ))
            comment = ""

    return AndroidFileData(path=path, entries=entries)


def save_android(data: AndroidFileData, path: Optional[str | Path] = None) -> None:
    """Save an Android strings.xml file."""
    out = Path(path) if path else data.path
    root = ET.Element("resources")

    # Group entries: plain strings, arrays, plurals
    arrays: dict[str, list[tuple[int, str]]] = {}
    plurals: dict[str, list[tuple[str, str]]] = {}
    plain: list[AndroidEntry] = []

    for entry in data.entries:
        if "[" in entry.key and entry.key.endswith("]"):
            # string-array item
            base = entry.key[:entry.key.rindex("[")]
            idx = int(entry.key[entry.key.rindex("[") + 1:-1])
            arrays.setdefault(base, []).append((idx, entry.value))
        elif ":" in entry.key:
            base, quantity = entry.key.rsplit(":", 1)
            plurals.setdefault(base, []).append((quantity, entry.value))
        else:
            plain.append(entry)

    for entry in plain:
        if entry.comment:
            root.append(ET.Comment(f" {entry.comment} "))
        el = ET.SubElement(root, "string", name=entry.key)
        if not entry.translatable:
            el.set("translatable", "false")
        el.text = entry.value

    for name, items in arrays.items():
        arr = ET.SubElement(root, "string-array", name=name)
        for _, val in sorted(items):
            item = ET.SubElement(arr, "item")
            item.text = val

    for name, items in plurals.items():
        pl = ET.SubElement(root, "plurals", name=name)
        for quantity, val in items:
            item = ET.SubElement(pl, "item", quantity=quantity)
            item.text = val

    tree = ET.ElementTree(root)
    ET.indent(tree, space="    ")
    tree.write(str(out), encoding="utf-8", xml_declaration=True)
