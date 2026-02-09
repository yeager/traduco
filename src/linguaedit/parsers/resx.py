"""RESX parser for .NET resource files."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional, Union

from linguaedit.parsers.po_parser import TranslationEntry


@dataclass
class RESXData:
    """Data structure for .resx files."""
    entries: List[TranslationEntry]
    file_path: str
    metadata: Dict[str, Any] = None
    schema: str = ""
    headers: Dict[str, str] = None


def parse_resx(file_path: Union[str, Path]) -> RESXData:
    """Parse .NET RESX file."""
    path = Path(file_path)
    entries = []
    metadata = {}
    headers = {}
    schema = ""
    
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        
        # Extract schema information
        if 'xmlns' in root.attrib:
            schema = root.attrib['xmlns']
        
        # Parse entries
        for data_elem in root.findall('data'):
            name = data_elem.get('name', '')
            space = data_elem.get('{http://www.w3.org/XML/1998/namespace}space', '')
            type_attr = data_elem.get('type', '')
            mime_type = data_elem.get('mimetype', '')
            
            # Find value element
            value_elem = data_elem.find('value')
            value = value_elem.text if value_elem is not None else ''
            
            # Find comment element
            comment_elem = data_elem.find('comment')
            comment = comment_elem.text if comment_elem is not None else ''
            
            # Create translation entry
            flags_list = []
            comment_parts = []
            if comment:
                comment_parts.append(comment)
            if space:
                flags_list.append(f'xml:space={space}')
            if type_attr:
                comment_parts.append(f'Type: {type_attr}')
            if mime_type:
                comment_parts.append(f'MIME: {mime_type}')

            entry = TranslationEntry(
                msgid=name,
                msgstr=value or '',
                msgctxt=name,
                comment='\n'.join(comment_parts),
                flags=flags_list,
                occurrences=[(str(path), '')],
                fuzzy=False
            )
            
            entries.append(entry)
        
        # Parse metadata (resheader elements)
        for resheader in root.findall('resheader'):
            name = resheader.get('name', '')
            value_elem = resheader.find('value')
            value = value_elem.text if value_elem is not None else ''
            
            if name and value:
                headers[name] = value
        
        # Extract assembly references
        for assembly in root.findall('assembly'):
            alias = assembly.get('alias', '')
            name = assembly.get('name', '')
            if alias and name:
                metadata[f'assembly_{alias}'] = name
        
    except ET.ParseError as e:
        raise ValueError(f"Invalid XML in RESX file: {e}")
    except Exception as e:
        raise ValueError(f"Error parsing RESX file: {e}")
    
    return RESXData(
        entries=entries,
        file_path=str(path),
        metadata=metadata,
        schema=schema,
        headers=headers or {}
    )


def save_resx(data: RESXData, file_path: Union[str, Path]) -> None:
    """Save RESX data to file."""
    path = Path(file_path)
    
    # Create root element
    root = ET.Element('root')
    
    # Add schema if available (skip reserved namespaces)
    if data.schema and data.schema != 'http://www.w3.org/XML/1998/namespace':
        root.set('xmlns', data.schema)
    
    # Add standard resheader elements
    standard_headers = {
        'resmimetype': 'text/microsoft-resx',
        'version': '2.0',
        'reader': 'System.Resources.ResXResourceReader, System.Windows.Forms, Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089',
        'writer': 'System.Resources.ResXResourceWriter, System.Windows.Forms, Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089'
    }
    
    # Merge with existing headers
    all_headers = {**standard_headers, **(data.headers or {})}
    
    for name, value in all_headers.items():
        resheader = ET.SubElement(root, 'resheader')
        resheader.set('name', name)
        value_elem = ET.SubElement(resheader, 'value')
        value_elem.text = value
    
    # Add assembly references from metadata
    for key, value in (data.metadata or {}).items():
        if key.startswith('assembly_'):
            alias = key[9:]  # Remove 'assembly_' prefix
            assembly = ET.SubElement(root, 'assembly')
            assembly.set('alias', alias)
            assembly.set('name', value)
    
    # Add data entries
    for entry in data.entries:
        data_elem = ET.SubElement(root, 'data')
        data_elem.set('name', entry.msgid)
        
        # Add xml:space if needed
        for flag in entry.flags:
            if flag.startswith('xml:space='):
                space_value = flag[10:]  # Remove 'xml:space=' prefix
                data_elem.set('{http://www.w3.org/XML/1998/namespace}space', space_value)
        
        # Parse metadata from comment field
        comment_lines = entry.comment.split('\n') if entry.comment else []
        for cline in comment_lines:
            if cline.startswith('Type: '):
                data_elem.set('type', cline[6:])
            elif cline.startswith('MIME: '):
                data_elem.set('mimetype', cline[6:])
        
        # Add value
        value_elem = ET.SubElement(data_elem, 'value')
        value_elem.text = entry.msgstr
        
        # Add comment if available and not metadata
        regular_comments = [c for c in comment_lines
                          if not c.startswith('Type: ') and not c.startswith('MIME: ')]
        if regular_comments:
            comment_elem = ET.SubElement(data_elem, 'comment')
            comment_elem.text = '\n'.join(regular_comments)
    
    # Write to file with proper formatting
    _indent_xml(root)
    tree = ET.ElementTree(root)
    
    # Write with XML declaration
    with open(path, 'wb') as f:
        tree.write(f, encoding='utf-8', xml_declaration=True)


def _indent_xml(elem, level=0):
    """Add indentation to XML for pretty printing."""
    indent = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = indent + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = indent
        for child in elem:
            _indent_xml(child, level + 1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = indent
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = indent


def is_resx_file(file_path: Union[str, Path]) -> bool:
    """Check if file is a RESX file."""
    path = Path(file_path)
    
    if path.suffix.lower() != '.resx':
        return False
    
    try:
        # Quick check for RESX content
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read(1000)  # Read first 1000 characters
            
        return ('<root' in content and 
                ('microsoft-resx' in content or 'data name=' in content))
    except Exception:
        return False


def convert_resx_to_po_entries(resx_data: RESXData) -> List[TranslationEntry]:
    """Convert RESX entries to PO-style entries for editing."""
    po_entries = []
    
    for entry in resx_data.entries:
        # Use the key as both source and context
        po_entry = TranslationEntry(
            msgid=entry.msgid,
            msgstr="",
            msgctxt=entry.msgid,
            comment=((entry.comment + "\n") if entry.comment else "") + f"Original value: {entry.msgstr}",
            occurrences=entry.occurrences,
            flags=entry.flags,
            fuzzy=True,
        )
        po_entries.append(po_entry)
    
    return po_entries


def update_resx_from_po_entries(resx_data: RESXData, po_entries: List[TranslationEntry]) -> RESXData:
    """Update RESX data with translations from PO entries."""
    translations = {}
    for po_entry in po_entries:
        if po_entry.msgstr and not po_entry.fuzzy:
            translations[po_entry.msgid] = po_entry.msgstr
    
    updated_entries = []
    for resx_entry in resx_data.entries:
        if resx_entry.msgid in translations:
            updated_entry = TranslationEntry(
                msgid=resx_entry.msgid,
                msgstr=translations[resx_entry.msgid],
                msgctxt=resx_entry.msgctxt,
                comment=resx_entry.comment,
                occurrences=resx_entry.occurrences,
                flags=resx_entry.flags,
                fuzzy=False,
            )
            updated_entries.append(updated_entry)
        else:
            updated_entries.append(resx_entry)
    
    return RESXData(
        entries=updated_entries,
        file_path=resx_data.file_path,
        metadata=resx_data.metadata,
        schema=resx_data.schema,
        headers=resx_data.headers
    )


# Register parser functions
def get_resx_parser_info():
    """Get parser information for registration."""
    return {
        'name': 'RESX (.NET)',
        'extensions': ['.resx'],
        'parse_func': parse_resx,
        'save_func': save_resx,
        'check_func': is_resx_file,
        'description': '.NET resource files (.resx)'
    }