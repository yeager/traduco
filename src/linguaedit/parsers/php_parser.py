"""PHP array parser (Laravel/WordPress style)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class PHPEntry:
    """A single PHP translation unit."""
    key: str
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
class PHPFileData:
    """Parsed PHP translation file."""
    path: Path
    entries: list[PHPEntry]
    raw_header: str = ""  # Any content before the return statement

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


# Match 'key' => 'value' or "key" => "value"
_ENTRY_RE = re.compile(
    r"""(?:^|\n)\s*(['"])((?:(?!\1).|\\.)*)\1\s*=>\s*(['"])((?:(?!\3).|\\.)*)\3""",
    re.DOTALL,
)

# Match // or /* */ comments before entries
_COMMENT_RE = re.compile(r'//\s*(.+?)$|/\*\s*(.+?)\s*\*/', re.MULTILINE)


def _unescape_php(s: str) -> str:
    """Unescape PHP string escapes."""
    return s.replace("\\'", "'").replace('\\"', '"').replace("\\\\", "\\").replace("\\n", "\n").replace("\\t", "\t")


def _escape_php(s: str) -> str:
    """Escape string for PHP single-quoted string."""
    return s.replace("\\", "\\\\").replace("'", "\\'")


def parse_php(path: str | Path) -> PHPFileData:
    """Parse a PHP translation array file."""
    path = Path(path)
    content = path.read_text("utf-8")

    entries: list[PHPEntry] = []

    # Find all comment positions for association
    comments = {}
    for m in _COMMENT_RE.finditer(content):
        comment_text = m.group(1) or m.group(2) or ""
        comments[m.end()] = comment_text.strip()

    for m in _ENTRY_RE.finditer(content):
        key = _unescape_php(m.group(2))
        value = _unescape_php(m.group(4))
        # Find closest comment before this match
        comment = ""
        match_start = m.start()
        for cend, ctext in comments.items():
            if cend <= match_start + 5 and cend > match_start - 200:
                comment = ctext
        entries.append(PHPEntry(key=key, value=value, comment=comment))

    # Capture header
    header = ""
    return_idx = content.find("return")
    if return_idx > 0:
        header = content[:return_idx]

    return PHPFileData(path=path, entries=entries, raw_header=header)


def save_php(data: PHPFileData, path: Optional[str | Path] = None) -> None:
    """Save a PHP translation array file."""
    out = Path(path) if path else data.path
    lines = ["<?php\n\nreturn [\n"]

    for entry in data.entries:
        if entry.comment:
            lines.append(f"    // {entry.comment}\n")
        key_esc = _escape_php(entry.key)
        val_esc = _escape_php(entry.value)
        lines.append(f"    '{key_esc}' => '{val_esc}',\n")

    lines.append("];\n")
    out.write_text("".join(lines), "utf-8")
