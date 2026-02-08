"""Java Properties parser — hantera Java .properties-filer."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class JavaPropertiesEntry:
    """En enskild nyckel-värde-par i .properties-format."""
    key: str
    value: str = ""
    comment: str = ""
    line_number: int = 0
    is_comment_line: bool = False  # För rena kommentarrader


@dataclass
class JavaPropertiesFileData:
    """Java Properties fildata."""
    path: Path
    entries: List[JavaPropertiesEntry] = field(default_factory=list)
    encoding: str = "utf-8"
    header_comment: str = ""


def _unescape_properties_value(value: str) -> str:
    """Unescape Java Properties-värde."""
    # Hantera unicode escapes (\uXXXX)
    def replace_unicode(match):
        return chr(int(match.group(1), 16))
    
    value = re.sub(r'\\u([0-9a-fA-F]{4})', replace_unicode, value)
    
    # Hantera andra escape-sekvenser
    escapes = {
        '\\n': '\n',
        '\\r': '\r',
        '\\t': '\t',
        '\\f': '\f',
        '\\\\': '\\',
        '\\:': ':',
        '\\=': '=',
        '\\ ': ' ',
    }
    
    for escaped, unescaped in escapes.items():
        value = value.replace(escaped, unescaped)
        
    return value


def _escape_properties_value(value: str) -> str:
    """Escape Java Properties-värde."""
    # Escape specialtecken
    escapes = {
        '\\': '\\\\',
        '\n': '\\n',
        '\r': '\\r',
        '\t': '\\t',
        '\f': '\\f',
    }
    
    for unescaped, escaped in escapes.items():
        value = value.replace(unescaped, escaped)
    
    # Escape unicode-tecken utanför ASCII
    result = ""
    for char in value:
        if ord(char) > 127:
            result += f"\\u{ord(char):04x}"
        else:
            result += char
    
    return result


def _parse_properties_line(line: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Parsa en rad från properties-fil. Returnerar (key, value, comment)."""
    original_line = line
    line = line.strip()
    
    # Tomma rader
    if not line:
        return None, None, None
    
    # Kommentarrader (# eller !)
    if line.startswith('#') or line.startswith('!'):
        comment = line[1:].strip()
        return None, None, comment
    
    # Hitta separator (=, :, eller whitespace)
    # Hantera escaped separators
    separator_pos = -1
    in_escape = False
    
    for i, char in enumerate(line):
        if in_escape:
            in_escape = False
            continue
        if char == '\\':
            in_escape = True
            continue
        if char in '=:' or char.isspace():
            separator_pos = i
            break
    
    if separator_pos == -1:
        # Ingen separator funnen, hela raden är key med tomt värde
        return line, "", None
    
    key = line[:separator_pos].strip()
    value_part = line[separator_pos:].lstrip('=: \t')
    
    # Hantera multiline values (som slutar med \)
    if value_part.endswith('\\'):
        value_part = value_part[:-1]  # Ta bort trailing backslash
    
    return key, value_part, None


def parse_java_properties(path: Path) -> JavaPropertiesFileData:
    """Parsa Java .properties-fil."""
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    
    # Läs fil med encoding-detektion
    content = ""
    encoding = "utf-8"
    
    for enc in ["utf-8", "latin1", "cp1252", "iso-8859-1"]:
        try:
            content = path.read_text(encoding=enc)
            encoding = enc
            break
        except UnicodeDecodeError:
            continue
    
    if not content:
        raise ValueError(f"Could not decode file: {path}")
    
    lines = content.splitlines()
    entries = []
    header_comments = []
    in_header = True
    current_key = None
    current_value = ""
    current_comment = ""
    
    for line_num, line in enumerate(lines, 1):
        key, value, comment = _parse_properties_line(line)
        
        # Header-kommentarer (innan första key)
        if comment and in_header and key is None:
            header_comments.append(comment)
            continue
        
        if key is not None:
            in_header = False
            
            # Spara föregående entry om vi har en
            if current_key:
                entry = JavaPropertiesEntry(
                    key=current_key,
                    value=_unescape_properties_value(current_value),
                    comment=current_comment,
                    line_number=line_num - 1
                )
                entries.append(entry)
            
            # Börja ny entry
            current_key = key
            current_value = value or ""
            current_comment = ""
        
        elif comment and current_key:
            # Kommentar för current key
            if current_comment:
                current_comment += " " + comment
            else:
                current_comment = comment
        
        elif value and current_key:
            # Fortsättning av multiline value
            current_value += value
        
        # Kolla om värdet fortsätter på nästa rad
        if line.rstrip().endswith('\\'):
            current_value = current_value[:-1]  # Ta bort trailing backslash
            continue
    
    # Spara sista entry
    if current_key:
        entry = JavaPropertiesEntry(
            key=current_key,
            value=_unescape_properties_value(current_value),
            comment=current_comment,
            line_number=len(lines)
        )
        entries.append(entry)
    
    return JavaPropertiesFileData(
        path=path,
        entries=entries,
        encoding=encoding,
        header_comment="\n".join(header_comments)
    )


def save_java_properties(file_data: JavaPropertiesFileData, path: Optional[Path] = None) -> None:
    """Spara Java .properties-fil."""
    if path:
        file_data.path = path
    
    lines = []
    
    # Header-kommentar
    if file_data.header_comment:
        for line in file_data.header_comment.split('\n'):
            if line.strip():
                lines.append(f"# {line.strip()}")
            else:
                lines.append("#")
        lines.append("")
    
    # Entries
    for entry in file_data.entries:
        # Kommentar för denna entry
        if entry.comment:
            for comment_line in entry.comment.split('\n'):
                if comment_line.strip():
                    lines.append(f"# {comment_line.strip()}")
        
        # Key = Value
        escaped_value = _escape_properties_value(entry.value)
        
        # Hantera långa rader (split vid 80 tecken)
        if len(entry.key) + len(escaped_value) > 80:
            lines.append(f"{entry.key} = \\")
            # Split value på lämpliga ställen
            words = escaped_value.split(' ')
            current_line = "    "
            
            for word in words:
                if len(current_line) + len(word) > 76:
                    lines.append(current_line.rstrip() + " \\")
                    current_line = "    " + word + " "
                else:
                    current_line += word + " "
            
            if current_line.strip():
                lines.append(current_line.rstrip())
        else:
            lines.append(f"{entry.key} = {escaped_value}")
        
        lines.append("")  # Tom rad mellan entries
    
    content = '\n'.join(lines)
    file_data.path.write_text(content, encoding=file_data.encoding)