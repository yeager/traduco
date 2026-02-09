"""Translation Memory (TM) — SQLite-based fuzzy matching."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional, List

TM_DIR = Path.home() / ".local" / "share" / "linguaedit"
TM_DB = TM_DIR / "tm.db"


@dataclass
class TMMatch:
    """A translation memory match."""
    source: str
    target: str
    source_lang: str
    target_lang: str
    similarity: float  # 0.0 – 1.0
    file_path: Optional[str] = None
    timestamp: Optional[str] = None


def _init_db() -> None:
    """Initialize the TM database."""
    TM_DIR.mkdir(parents=True, exist_ok=True)
    
    with sqlite3.connect(TM_DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS translation_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                target TEXT NOT NULL,
                source_lang TEXT NOT NULL DEFAULT 'en',
                target_lang TEXT NOT NULL DEFAULT 'sv',
                file_path TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(source, source_lang, target_lang)
            )
        """)
        
        # Create index for faster lookups
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_source 
            ON translation_memory(source)
        """)
        
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_langs
            ON translation_memory(source_lang, target_lang)
        """)


def add_to_tm(source: str, target: str, source_lang: str = "en", target_lang: str = "sv", file_path: Optional[str] = None) -> None:
    """Add or update a TM entry."""
    if not source.strip() or not target.strip():
        return
        
    _init_db()
    
    with sqlite3.connect(TM_DB) as conn:
        conn.execute("""
            INSERT OR REPLACE INTO translation_memory 
            (source, target, source_lang, target_lang, file_path, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (source, target, source_lang, target_lang, file_path, datetime.now().isoformat()))


def lookup_tm(source: str, source_lang: str = "en", target_lang: str = "sv", threshold: float = 0.7, max_results: int = 5) -> List[TMMatch]:
    """Find TM matches above threshold."""
    if not source.strip():
        return []
        
    try:
        _init_db()
    except Exception:
        return []
    
    matches = []
    
    try:
        with sqlite3.connect(TM_DB) as conn:
            # Get all entries for the language pair
            cursor = conn.execute("""
                SELECT source, target, source_lang, target_lang, file_path, timestamp
                FROM translation_memory 
                WHERE source_lang = ? AND target_lang = ?
            """, (source_lang, target_lang))
            
            for row in cursor:
                db_source, db_target, db_src_lang, db_tgt_lang, db_file, db_timestamp = row
                
                # Calculate fuzzy match similarity
                sim = SequenceMatcher(None, source.lower(), db_source.lower()).ratio()
                
                if sim >= threshold:
                    matches.append(TMMatch(
                        source=db_source,
                        target=db_target, 
                        source_lang=db_src_lang,
                        target_lang=db_tgt_lang,
                        similarity=sim,
                        file_path=db_file,
                        timestamp=db_timestamp
                    ))
    except Exception:
        return []
        
    # Sort by similarity (best matches first)
    matches.sort(key=lambda m: m.similarity, reverse=True)
    return matches[:max_results]


def feed_file_to_tm(entries: List[tuple[str, str]], source_lang: str = "en", target_lang: str = "sv", file_path: Optional[str] = None) -> int:
    """Bulk-add translated pairs to TM. Returns count added."""
    if not entries:
        return 0
        
    _init_db()
    count = 0
    
    with sqlite3.connect(TM_DB) as conn:
        for src, tgt in entries:
            if src.strip() and tgt.strip():
                try:
                    conn.execute("""
                        INSERT OR REPLACE INTO translation_memory 
                        (source, target, source_lang, target_lang, file_path, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (src, tgt, source_lang, target_lang, file_path, datetime.now().isoformat()))
                    count += 1
                except Exception:
                    continue
                    
    return count


def get_tm_stats() -> dict:
    """Get TM database statistics."""
    try:
        _init_db()
    except Exception:
        return {"total": 0, "languages": []}
        
    with sqlite3.connect(TM_DB) as conn:
        # Total entries
        cursor = conn.execute("SELECT COUNT(*) FROM translation_memory")
        total = cursor.fetchone()[0]
        
        # Language pairs
        cursor = conn.execute("""
            SELECT source_lang, target_lang, COUNT(*) 
            FROM translation_memory 
            GROUP BY source_lang, target_lang
            ORDER BY COUNT(*) DESC
        """)
        languages = [{"source": row[0], "target": row[1], "count": row[2]} for row in cursor]
        
    return {"total": total, "languages": languages}


def concordance_search(query: str, source_lang: str = "", target_lang: str = "", max_results: int = 100) -> List[TMMatch]:
    """Search TM for segments containing the query in source or target."""
    if not query.strip():
        return []

    try:
        _init_db()
    except Exception:
        return []

    matches = []
    pattern = f"%{query}%"

    try:
        with sqlite3.connect(TM_DB) as conn:
            if source_lang and target_lang:
                cursor = conn.execute("""
                    SELECT source, target, source_lang, target_lang, file_path, timestamp
                    FROM translation_memory
                    WHERE (source LIKE ? OR target LIKE ?)
                      AND source_lang = ? AND target_lang = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (pattern, pattern, source_lang, target_lang, max_results))
            else:
                cursor = conn.execute("""
                    SELECT source, target, source_lang, target_lang, file_path, timestamp
                    FROM translation_memory
                    WHERE source LIKE ? OR target LIKE ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (pattern, pattern, max_results))

            query_lower = query.lower()
            for row in cursor:
                db_source, db_target, db_src_lang, db_tgt_lang, db_file, db_timestamp = row
                # Score based on how prominent the match is
                src_count = db_source.lower().count(query_lower)
                tgt_count = db_target.lower().count(query_lower)
                total_len = max(len(db_source) + len(db_target), 1)
                score = (src_count + tgt_count) * len(query) / total_len
                matches.append(TMMatch(
                    source=db_source,
                    target=db_target,
                    source_lang=db_src_lang,
                    target_lang=db_tgt_lang,
                    similarity=min(score, 1.0),
                    file_path=db_file,
                    timestamp=db_timestamp,
                ))
    except Exception:
        return []

    matches.sort(key=lambda m: m.similarity, reverse=True)
    return matches[:max_results]


def clear_tm() -> int:
    """Clear all TM entries. Returns count of deleted entries."""
    try:
        _init_db()
    except Exception:
        return 0
        
    with sqlite3.connect(TM_DB) as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM translation_memory")
        count = cursor.fetchone()[0]
        conn.execute("DELETE FROM translation_memory")
        
    return count


def export_tm(file_path: str, source_lang: str = "", target_lang: str = "") -> int:
    """Export TM to CSV file. Returns count of exported entries."""
    import csv
    
    try:
        _init_db()
    except Exception:
        return 0
        
    count = 0
    
    with sqlite3.connect(TM_DB) as conn:
        if source_lang and target_lang:
            cursor = conn.execute("""
                SELECT source, target, source_lang, target_lang, file_path, timestamp
                FROM translation_memory 
                WHERE source_lang = ? AND target_lang = ?
                ORDER BY timestamp DESC
            """, (source_lang, target_lang))
        else:
            cursor = conn.execute("""
                SELECT source, target, source_lang, target_lang, file_path, timestamp
                FROM translation_memory 
                ORDER BY timestamp DESC
            """)
            
        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['source', 'target', 'source_lang', 'target_lang', 'file_path', 'timestamp'])
            
            for row in cursor:
                writer.writerow(row)
                count += 1
                
    return count


def import_tm(file_path: str) -> int:
    """Import TM from CSV file. Returns count of imported entries."""
    import csv
    
    if not Path(file_path).exists():
        return 0
        
    _init_db()
    count = 0
    
    with open(file_path, 'r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        
        with sqlite3.connect(TM_DB) as conn:
            for row in reader:
                try:
                    conn.execute("""
                        INSERT OR REPLACE INTO translation_memory 
                        (source, target, source_lang, target_lang, file_path, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        row.get('source', ''),
                        row.get('target', ''),
                        row.get('source_lang', 'en'),
                        row.get('target_lang', 'sv'),
                        row.get('file_path', ''),
                        row.get('timestamp', datetime.now().isoformat())
                    ))
                    count += 1
                except Exception:
                    continue
                    
    return count
