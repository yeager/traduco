"""Apple .strings and .stringsdict parser for iOS/macOS localization."""

from __future__ import annotations

import plistlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional, Union

from linguaedit.parsers.po_parser import TranslationEntry


@dataclass
class AppleStringsData:
    """Data structure for Apple .strings/.stringsdict files."""
    entries: List[TranslationEntry]
    file_path: str
    is_stringsdict: bool = False
    metadata: Dict[str, Any] = None


def parse_apple_strings(file_path: Union[str, Path]) -> AppleStringsData:
    """Parse Apple .strings or .stringsdict file."""
    path = Path(file_path)
    
    if path.suffix == '.stringsdict':
        return _parse_stringsdict(path)
    else:
        return _parse_strings(path)


def _parse_strings(file_path: Path) -> AppleStringsData:
    """Parse .strings file format."""
    entries = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        # Try UTF-16 encoding (common for Xcode-generated files)
        with open(file_path, 'r', encoding='utf-16') as f:
            content = f.read()
    
    # Parse .strings format: "key" = "value";
    # Also handle comments: /* comment */
    
    # Remove C-style comments
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    
    # Find all key-value pairs
    pattern = r'"([^"\\]*(\\.[^"\\]*)*)"\s*=\s*"([^"\\]*(\\.[^"\\]*)*)"\s*;'
    
    for match in re.finditer(pattern, content):
        key = match.group(1)
        value = match.group(3)
        
        # Unescape strings
        key = _unescape_string(key)
        value = _unescape_string(value)
        
        entry = TranslationEntry(
            msgid=key,
            msgstr=value,
            msgctxt=key,
        )
        
        entries.append(entry)
    
    return AppleStringsData(
        entries=entries,
        file_path=str(file_path),
        is_stringsdict=False
    )


def _parse_stringsdict(file_path: Path) -> AppleStringsData:
    """Parse .stringsdict file format (plist with plural forms)."""
    entries = []
    
    with open(file_path, 'rb') as f:
        plist_data = plistlib.load(f)
    
    for key, value in plist_data.items():
        if isinstance(value, dict) and 'NSStringLocalizedFormatKey' in value:
            # This is a plural form entry
            format_key = value['NSStringLocalizedFormatKey']
            
            # Extract plural forms
            plural_forms = {}
            for var_key, var_value in value.items():
                if var_key.startswith('VARIABLE_'):
                    variable_data = var_value
                    if isinstance(variable_data, dict) and 'NSStringFormatSpecTypeKey' in variable_data:
                        spec_type = variable_data['NSStringFormatSpecTypeKey']
                        if spec_type == 'NSStringPluralRuleType':
                            plural_rules = variable_data.get('NSStringFormatValueTypeKey', {})
                            for rule, text in plural_rules.items():
                                plural_forms[rule] = text
            
            # Create entries for each plural form
            if plural_forms:
                for rule, text in plural_forms.items():
                    entry = TranslationEntry(
                        msgid=f"{key}[{rule}]",
                        msgstr=text,
                        msgctxt=key,
                        comment=f"Plural form: {rule}; Format: {format_key}",
                        flags=['plural'],
                    )
                    entries.append(entry)
            else:
                # Regular entry
                entry = TranslationEntry(
                    msgid=key,
                    msgstr=format_key,
                    msgctxt=key,
                )
                entries.append(entry)
        else:
            # Simple key-value pair
            entry = TranslationEntry(
                msgid=key,
                msgstr=str(value),
                msgctxt=key,
            )
            entries.append(entry)
    
    return AppleStringsData(
        entries=entries,
        file_path=str(file_path),
        is_stringsdict=True
    )


def save_apple_strings(data: AppleStringsData, file_path: Union[str, Path]) -> None:
    """Save Apple strings data to file."""
    if data.is_stringsdict:
        _save_stringsdict(data, file_path)
    else:
        _save_strings(data, file_path)


def _save_strings(data: AppleStringsData, file_path: Path) -> None:
    """Save .strings file format."""
    lines = []
    
    for entry in data.entries:
        if entry.comment:
            lines.append(f"/* {entry.comment} */")
        
        key = _escape_string(entry.msgid)
        value = _escape_string(entry.msgstr)
        lines.append(f'"{key}" = "{value}";')
        lines.append("")  # Empty line for readability
    
    content = '\n'.join(lines)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)


def _save_stringsdict(data: AppleStringsData, file_path: Path) -> None:
    """Save .stringsdict file format."""
    plist_data = {}
    
    # Group entries by context (original key)
    grouped_entries = {}
    for entry in data.entries:
        context = entry.msgctxt or entry.msgid
        if context not in grouped_entries:
            grouped_entries[context] = []
        grouped_entries[context].append(entry)
    
    for context, entries in grouped_entries.items():
        # Check if this has plural forms
        plural_entries = [e for e in entries if 'plural' in e.flags]
        
        if plural_entries:
            # Create plural structure
            plural_dict = {
                'NSStringLocalizedFormatKey': f'%#@VARIABLE_{context.upper()}@',
                f'VARIABLE_{context.upper()}': {
                    'NSStringFormatSpecTypeKey': 'NSStringPluralRuleType',
                    'NSStringFormatValueTypeKey': {
                        'zero': '',
                        'one': '',
                        'two': '',
                        'few': '',
                        'many': '',
                        'other': ''
                    }
                }
            }
            
            # Fill in the plural forms
            for entry in plural_entries:
                # Extract plural rule from source like "key[zero]"
                match = re.search(r'\[(\w+)\]$', entry.msgid)
                if match:
                    rule = match.group(1)
                    plural_dict[f'VARIABLE_{context.upper()}']['NSStringFormatValueTypeKey'][rule] = entry.msgstr
            
            plist_data[context] = plural_dict
        else:
            # Simple key-value
            if entries:
                plist_data[context] = entries[0].msgstr
    
    with open(file_path, 'wb') as f:
        plistlib.dump(plist_data, f)


def _escape_string(s: str) -> str:
    """Escape string for .strings format."""
    # Escape backslashes and quotes
    s = s.replace('\\', '\\\\')
    s = s.replace('"', '\\"')
    s = s.replace('\n', '\\n')
    s = s.replace('\r', '\\r')
    s = s.replace('\t', '\\t')
    return s


def _unescape_string(s: str) -> str:
    """Unescape string from .strings format."""
    # Unescape standard sequences
    s = s.replace('\\n', '\n')
    s = s.replace('\\r', '\r')
    s = s.replace('\\t', '\t')
    s = s.replace('\\"', '"')
    s = s.replace('\\\\', '\\')
    return s


def is_apple_strings_file(file_path: Union[str, Path]) -> bool:
    """Check if file is an Apple strings file."""
    path = Path(file_path)
    return path.suffix in ['.strings', '.stringsdict']


# Register parser functions
def get_apple_strings_parser_info():
    """Get parser information for registration."""
    return {
        'name': 'Apple Strings',
        'extensions': ['.strings', '.stringsdict'],
        'parse_func': parse_apple_strings,
        'save_func': save_apple_strings,
        'check_func': is_apple_strings_file,
        'description': 'iOS/macOS localization files (.strings, .stringsdict)'
    }
