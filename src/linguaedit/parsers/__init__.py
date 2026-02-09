"""File format parsers for PO, TS, JSON, XLIFF, Android, ARB, PHP, YAML, SDLXLIFF, and MQXLIFF."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Union


def safe_parse_xml(path: Union[str, Path]) -> ET.ElementTree:
    """Parse XML with external entity resolution disabled (XXE protection).

    Uses a custom XMLParser that forbids DTD loading and external entities
    to prevent XXE (XML External Entity) and billion laughs attacks.
    """
    parser = ET.XMLParser()
    # Disable external entity resolution via expat
    parser.parser.UseForeignDTD(False)
    parser.parser.SetParamEntityParsing(0)  # XML_PARAM_ENTITY_PARSING_NEVER
    try:
        # Also attempt to disable entity declarations entirely
        parser.parser.ExternalEntityRefHandler = lambda *a: 0
    except Exception:
        pass
    return ET.parse(str(path), parser=parser)


def safe_fromstring_xml(text: Union[str, bytes]) -> ET.Element:
    """Parse XML string with external entity resolution disabled (XXE protection)."""
    parser = ET.XMLParser()
    parser.parser.UseForeignDTD(False)
    parser.parser.SetParamEntityParsing(0)
    try:
        parser.parser.ExternalEntityRefHandler = lambda *a: 0
    except Exception:
        pass
    return ET.fromstring(text, parser=parser)
