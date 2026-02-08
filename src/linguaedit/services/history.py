"""Translation history service — track and manage per-string undo history."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal


@dataclass
class HistoryEntry:
    """A single history entry for a translation string."""
    id: int
    file_path: str
    entry_index: int
    field: str  # 'source' or 'target' or 'comment' etc.
    old_value: str
    new_value: str
    timestamp: datetime
    user: str


class TranslationHistory(QObject):
    """Manages translation history using SQLite database."""
    
    history_added = Signal(str, int)  # file_path, entry_index
    
    def __init__(self):
        super().__init__()
        self._db_path = Path.home() / ".local" / "share" / "linguaedit" / "history.db"
        self._ensure_database()
    
    def _ensure_database(self):
        """Create database and tables if they don't exist."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS translation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL,
                entry_index INTEGER NOT NULL,
                field TEXT NOT NULL DEFAULT 'target',
                old_value TEXT NOT NULL,
                new_value TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                user TEXT DEFAULT ''
            )
        """)
        
        # Create index for faster lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_history_file_entry 
            ON translation_history(file_path, entry_index)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_history_timestamp
            ON translation_history(timestamp)
        """)
        
        conn.commit()
        conn.close()
    
    def add_change(self, file_path: str, entry_index: int, field: str,
                   old_value: str, new_value: str, user: str = "") -> int:
        """Add a change to the history.
        
        Returns the history entry ID.
        """
        # Skip if no actual change
        if old_value == new_value:
            return -1
        
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        
        timestamp = datetime.now().isoformat()
        
        cursor.execute("""
            INSERT INTO translation_history 
            (file_path, entry_index, field, old_value, new_value, timestamp, user)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (file_path, entry_index, field, old_value, new_value, timestamp, user))
        
        entry_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        self.history_added.emit(file_path, entry_index)
        return entry_id
    
    def get_entry_history(self, file_path: str, entry_index: int) -> List[HistoryEntry]:
        """Get all history entries for a specific translation entry."""
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, file_path, entry_index, field, old_value, new_value, timestamp, user
            FROM translation_history
            WHERE file_path = ? AND entry_index = ?
            ORDER BY timestamp DESC
        """, (file_path, entry_index))
        
        entries = []
        for row in cursor:
            entry = HistoryEntry(
                id=row[0],
                file_path=row[1],
                entry_index=row[2],
                field=row[3],
                old_value=row[4],
                new_value=row[5],
                timestamp=datetime.fromisoformat(row[6]),
                user=row[7]
            )
            entries.append(entry)
        
        conn.close()
        return entries
    
    def get_file_history(self, file_path: str, limit: int = 100) -> List[HistoryEntry]:
        """Get recent history entries for a file."""
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, file_path, entry_index, field, old_value, new_value, timestamp, user
            FROM translation_history
            WHERE file_path = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (file_path, limit))
        
        entries = []
        for row in cursor:
            entry = HistoryEntry(
                id=row[0],
                file_path=row[1],
                entry_index=row[2],
                field=row[3],
                old_value=row[4],
                new_value=row[5],
                timestamp=datetime.fromisoformat(row[6]),
                user=row[7]
            )
            entries.append(entry)
        
        conn.close()
        return entries
    
    def get_recent_history(self, limit: int = 50) -> List[HistoryEntry]:
        """Get recent history entries across all files."""
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, file_path, entry_index, field, old_value, new_value, timestamp, user
            FROM translation_history
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
        
        entries = []
        for row in cursor:
            entry = HistoryEntry(
                id=row[0],
                file_path=row[1],
                entry_index=row[2],
                field=row[3],
                old_value=row[4],
                new_value=row[5],
                timestamp=datetime.fromisoformat(row[6]),
                user=row[7]
            )
            entries.append(entry)
        
        conn.close()
        return entries
    
    def rollback_to_entry(self, history_id: int) -> Optional[HistoryEntry]:
        """Get a specific history entry for rollback.
        
        Returns the entry with the old value that can be restored.
        """
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, file_path, entry_index, field, old_value, new_value, timestamp, user
            FROM translation_history
            WHERE id = ?
        """, (history_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return HistoryEntry(
                id=row[0],
                file_path=row[1],
                entry_index=row[2],
                field=row[3],
                old_value=row[4],
                new_value=row[5],
                timestamp=datetime.fromisoformat(row[6]),
                user=row[7]
            )
        
        return None
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about the translation history."""
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        
        # Total changes
        cursor.execute("SELECT COUNT(*) FROM translation_history")
        total_changes = cursor.fetchone()[0]
        
        # Changes by file
        cursor.execute("""
            SELECT file_path, COUNT(*) as change_count
            FROM translation_history
            GROUP BY file_path
            ORDER BY change_count DESC
            LIMIT 10
        """)
        files = [{"path": row[0], "changes": row[1]} for row in cursor]
        
        # Changes by date
        cursor.execute("""
            SELECT DATE(timestamp) as date, COUNT(*) as change_count
            FROM translation_history
            WHERE timestamp >= date('now', '-30 days')
            GROUP BY DATE(timestamp)
            ORDER BY date DESC
        """)
        daily_changes = [{"date": row[0], "changes": row[1]} for row in cursor]
        
        # Most active entries
        cursor.execute("""
            SELECT file_path, entry_index, COUNT(*) as change_count
            FROM translation_history
            GROUP BY file_path, entry_index
            ORDER BY change_count DESC
            LIMIT 10
        """)
        active_entries = [
            {"file": row[0], "index": row[1], "changes": row[2]} 
            for row in cursor
        ]
        
        conn.close()
        
        return {
            "total_changes": total_changes,
            "files": files,
            "daily_changes": daily_changes,
            "active_entries": active_entries
        }
    
    def cleanup_old_history(self, days: int = 90):
        """Remove history entries older than specified days."""
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            DELETE FROM translation_history
            WHERE timestamp < datetime('now', '-{} days')
        """.format(days))
        
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        return deleted_count
    
    def clear_file_history(self, file_path: str):
        """Clear all history for a specific file."""
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            DELETE FROM translation_history
            WHERE file_path = ?
        """, (file_path,))
        
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        return deleted_count
    
    def has_history(self, file_path: str, entry_index: int) -> bool:
        """Check if an entry has any history."""
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) FROM translation_history
            WHERE file_path = ? AND entry_index = ?
        """, (file_path, entry_index))
        
        count = cursor.fetchone()[0]
        conn.close()
        
        return count > 0


# Global instance
_history_manager: Optional[TranslationHistory] = None


def get_history_manager() -> TranslationHistory:
    """Get the global translation history manager."""
    global _history_manager
    if _history_manager is None:
        _history_manager = TranslationHistory()
    return _history_manager