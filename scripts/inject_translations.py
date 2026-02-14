#!/usr/bin/env python3
"""Inject translations from generate_translations.py into .ts files.

Reads the Python dict from generate_translations.py (even if truncated),
matches source strings in the corresponding .ts files, and fills in
translations that are currently empty/unfinished.
"""

import ast
import re
import sys
from pathlib import Path

TS_DIR = Path(__file__).parent.parent / "src" / "linguaedit" / "translations"

# Map from generate_translations.py keys to .ts file language codes
LANG_MAP = {
    "ja": "ja",
    "zh_CN": "zh_CN",
    "ko": "ko",
    "pl": "pl",
    "da": "da",
    "nb": "nb",
}


def extract_dicts_from_file(filepath: Path) -> dict[str, dict[str, str]]:
    """Extract language translation dicts from generate_translations.py.
    
    Handles truncated files by trying to parse each language block separately.
    """
    with open(filepath) as f:
        content = f.read()
    
    results = {}
    # Find each language block: "xx": { "lang": "...", "strings": { ... } }
    # We'll find the "strings" dict for each language
    pattern = re.compile(
        r'"(\w+)"\s*:\s*\{\s*"lang"\s*:\s*"[^"]+"\s*,\s*"strings"\s*:\s*\{',
        re.DOTALL
    )
    
    matches = list(pattern.finditer(content))
    for i, m in enumerate(matches):
        lang_key = m.group(1)
        # Find the start of the strings dict
        strings_start = m.end()
        # Find the end: next language block or end of file
        if i + 1 < len(matches):
            search_end = matches[i + 1].start()
        else:
            search_end = len(content)
        
        # Extract the strings dict content
        block = content[strings_start:search_end]
        
        # Try to parse as a dict by closing it
        # Find all "key": "value" pairs
        strings = {}
        for pm in re.finditer(
            r'"((?:[^"\\]|\\.)*)"\s*:\s*"((?:[^"\\]|\\.)*)"',
            block
        ):
            key = pm.group(1).replace('\\"', '"').replace('\\n', '\n')
            val = pm.group(2).replace('\\"', '"').replace('\\n', '\n')
            strings[key] = val
        
        if strings:
            results[lang_key] = strings
            print(f"  {lang_key}: {len(strings)} strings")
    
    return results


def inject_into_ts(ts_path: Path, translations: dict[str, str]) -> int:
    """Inject translations into a .ts file. Returns number of strings filled."""
    with open(ts_path, encoding="utf-8") as f:
        content = f.read()
    
    filled = 0
    
    def replace_message(match):
        nonlocal filled
        full = match.group(0)
        source_text = match.group(1)
        
        # Only fill if currently unfinished
        if 'type="unfinished"' not in full:
            return full
        
        # Look up translation — try both raw and XML-unescaped source
        trans = translations.get(source_text)
        if not trans:
            # Unescape XML entities for lookup
            unescaped = (source_text
                         .replace("&amp;", "&")
                         .replace("&lt;", "<")
                         .replace("&gt;", ">")
                         .replace("&quot;", '"')
                         .replace("&#39;", "'"))
            trans = translations.get(unescaped)
        if not trans:
            return full
        
        # Escape for XML
        trans_xml = trans.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
        
        # Replace: handle both self-closing and open/close translation tags
        new = re.sub(
            r'<translation\s+type="unfinished"\s*/>',
            f'<translation>{trans_xml}</translation>',
            full,
        )
        if new == full:
            new = re.sub(
                r'<translation\s+type="unfinished"\s*>(.*?)</translation>',
                f'<translation>{trans_xml}</translation>',
                full,
                flags=re.DOTALL,
            )
        if new != full:
            filled += 1
        return new
    
    # Match message blocks
    pattern = re.compile(
        r'<message>.*?<source>(.*?)</source>.*?</message>',
        re.DOTALL
    )
    
    new_content = pattern.sub(replace_message, content)
    
    if filled > 0:
        with open(ts_path, "w", encoding="utf-8") as f:
            f.write(new_content)
    
    return filled


def main():
    gen_file = Path(__file__).parent.parent / "generate_translations.py"
    if not gen_file.exists():
        print(f"Error: {gen_file} not found")
        sys.exit(1)
    
    print("Extracting translations from generate_translations.py...")
    all_translations = extract_dicts_from_file(gen_file)
    
    print(f"\nInjecting into .ts files...")
    total_filled = 0
    for gen_key, ts_lang in LANG_MAP.items():
        if gen_key not in all_translations:
            print(f"  {ts_lang}: no translations found in source")
            continue
        
        ts_file = TS_DIR / f"linguaedit_{ts_lang}.ts"
        if not ts_file.exists():
            print(f"  {ts_lang}: .ts file not found")
            continue
        
        filled = inject_into_ts(ts_file, all_translations[gen_key])
        total_filled += filled
        print(f"  {ts_lang}: filled {filled} translations")
    
    print(f"\nTotal: {total_filled} translations injected")


if __name__ == "__main__":
    main()
