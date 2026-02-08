"""TMX (Translation Memory eXchange) import/export service."""

from __future__ import annotations

import sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Iterator

from linguaedit.services.tm import TM_DB


class TMXService:
    """Handle TMX 1.4b import and export operations."""
    
    @staticmethod
    def export_to_tmx(output_path: Path, source_lang: str = "en", target_lang: str = "sv") -> int:
        """Export translation memory to TMX file.
        
        Returns the number of translation units exported.
        """
        # Connect to TM database
        conn = sqlite3.connect(TM_DB)
        cursor = conn.cursor()
        
        # Create TMX root
        tmx = ET.Element("tmx", version="1.4b")
        header = ET.SubElement(tmx, "header")
        header.set("creationtool", "LinguaEdit")
        header.set("creationtoolversion", "0.11.0")
        header.set("datatype", "plaintext")
        header.set("segtype", "sentence")
        header.set("adminlang", source_lang)
        header.set("srclang", source_lang)
        header.set("o-tmf", "LinguaEdit")
        header.set("creationdate", datetime.now().strftime("%Y%m%dT%H%M%SZ"))
        
        body = ET.SubElement(tmx, "body")
        
        # Export TM entries
        cursor.execute("""
            SELECT source_text, target_text, source_lang, target_lang
            FROM tm_entries
            WHERE source_lang = ? AND target_lang = ?
        """, (source_lang, target_lang))
        
        count = 0
        for row in cursor:
            source_text, target_text, src_lang, tgt_lang = row
            
            # Create TU (Translation Unit)
            tu = ET.SubElement(body, "tu")
            tu.set("tuid", f"tu{count + 1}")
            
            # Source TUV
            tuv_source = ET.SubElement(tu, "tuv")
            tuv_source.set("xml:lang", src_lang)
            seg_source = ET.SubElement(tuv_source, "seg")
            seg_source.text = source_text
            
            # Target TUV
            tuv_target = ET.SubElement(tu, "tuv")
            tuv_target.set("xml:lang", tgt_lang)
            seg_target = ET.SubElement(tuv_target, "seg")
            seg_target.text = target_text
            
            count += 1
        
        conn.close()
        
        # Write TMX file
        tree = ET.ElementTree(tmx)
        ET.indent(tree, space="  ", level=0)
        tree.write(output_path, encoding="utf-8", xml_declaration=True)
        
        return count
    
    @staticmethod
    def import_from_tmx(tmx_path: Path) -> tuple[int, list[str]]:
        """Import TMX file into translation memory.
        
        Returns (imported_count, errors).
        """
        errors = []
        imported = 0
        
        try:
            tree = ET.parse(tmx_path)
            tmx = tree.getroot()
            
            if tmx.tag != "tmx":
                errors.append("Not a valid TMX file: root element is not 'tmx'")
                return 0, errors
            
            # Get header info
            header = tmx.find("header")
            if header is not None:
                src_lang = header.get("srclang", "en")
            else:
                src_lang = "en"
            
            body = tmx.find("body")
            if body is None:
                errors.append("TMX file has no body element")
                return 0, errors
            
            # Connect to TM database
            conn = sqlite3.connect(TM_DB)
            cursor = conn.cursor()
            
            # Ensure tables exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tm_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_text TEXT NOT NULL,
                    target_text TEXT NOT NULL,
                    source_lang TEXT NOT NULL,
                    target_lang TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(source_text, target_text, source_lang, target_lang)
                )
            """)
            
            # Process translation units
            for tu in body.findall("tu"):
                try:
                    tuvs = tu.findall("tuv")
                    if len(tuvs) < 2:
                        continue
                    
                    source_tuv = None
                    target_tuv = None
                    
                    # Find source and target TUVs
                    for tuv in tuvs:
                        lang = tuv.get("xml:lang", "").lower()
                        seg = tuv.find("seg")
                        if seg is None or not seg.text:
                            continue
                        
                        if lang == src_lang.lower():
                            source_tuv = seg.text
                        else:
                            target_tuv = seg.text
                            target_lang = lang
                    
                    if source_tuv and target_tuv:
                        cursor.execute("""
                            INSERT OR IGNORE INTO tm_entries 
                            (source_text, target_text, source_lang, target_lang)
                            VALUES (?, ?, ?, ?)
                        """, (source_tuv, target_tuv, src_lang, target_lang))
                        
                        if cursor.rowcount > 0:
                            imported += 1
                
                except Exception as e:
                    errors.append(f"Error processing TU: {str(e)}")
            
            conn.commit()
            conn.close()
            
        except ET.ParseError as e:
            errors.append(f"XML parse error: {str(e)}")
        except Exception as e:
            errors.append(f"Import error: {str(e)}")
        
        return imported, errors
    
    @staticmethod
    def validate_tmx(tmx_path: Path) -> tuple[bool, list[str]]:
        """Validate a TMX file and return (is_valid, errors)."""
        errors = []
        
        try:
            tree = ET.parse(tmx_path)
            tmx = tree.getroot()
            
            # Check root element
            if tmx.tag != "tmx":
                errors.append("Root element must be 'tmx'")
                return False, errors
            
            # Check version
            version = tmx.get("version")
            if not version:
                errors.append("Missing TMX version attribute")
            elif not version.startswith("1.4"):
                errors.append(f"Unsupported TMX version: {version}")
            
            # Check header
            header = tmx.find("header")
            if header is None:
                errors.append("Missing header element")
                return False, errors
            
            # Check body
            body = tmx.find("body")
            if body is None:
                errors.append("Missing body element")
                return False, errors
            
            # Count TUs
            tu_count = len(body.findall("tu"))
            if tu_count == 0:
                errors.append("No translation units found")
            
        except ET.ParseError as e:
            errors.append(f"XML parse error: {str(e)}")
            return False, errors
        except Exception as e:
            errors.append(f"Validation error: {str(e)}")
            return False, errors
        
        return len(errors) == 0, errors
    
    @staticmethod
    def get_tmx_info(tmx_path: Path) -> dict:
        """Get information about a TMX file."""
        info = {
            "valid": False,
            "version": None,
            "source_lang": None,
            "tu_count": 0,
            "languages": [],
            "creation_tool": None,
            "creation_date": None
        }
        
        try:
            tree = ET.parse(tmx_path)
            tmx = tree.getroot()
            
            info["valid"] = True
            info["version"] = tmx.get("version")
            
            header = tmx.find("header")
            if header is not None:
                info["source_lang"] = header.get("srclang")
                info["creation_tool"] = header.get("creationtool")
                info["creation_date"] = header.get("creationdate")
            
            body = tmx.find("body")
            if body is not None:
                info["tu_count"] = len(body.findall("tu"))
                
                # Get all languages used
                languages = set()
                for tuv in body.findall(".//tuv"):
                    lang = tuv.get("xml:lang")
                    if lang:
                        languages.add(lang)
                info["languages"] = sorted(languages)
                
        except Exception:
            pass
        
        return info