"""Gamification and achievements system for LinguaEdit."""

from __future__ import annotations

import json
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal


@dataclass
class Achievement:
    """Represents an unlocked achievement."""
    id: str
    name: str
    description: str
    icon: str
    unlocked_at: datetime
    progress: int = 100  # Percentage (0-100)


@dataclass
class AchievementDefinition:
    """Definition of an achievement that can be unlocked."""
    id: str
    name: str
    description: str
    icon: str
    condition_type: str
    condition_value: Any
    hidden: bool = False


class AchievementManager(QObject):
    """Manages achievements and gamification features."""
    
    achievement_unlocked = Signal(Achievement)
    progress_updated = Signal(str, int)  # achievement_id, progress
    
    def __init__(self):
        super().__init__()
        self._data_file = Path.home() / ".local" / "share" / "linguaedit" / "achievements.json"
        self._stats_file = Path.home() / ".local" / "share" / "linguaedit" / "user_stats.json"
        
        self._achievements: Dict[str, Achievement] = {}
        self._stats: Dict[str, Any] = {}
        
        self._define_achievements()
        self._load_data()
    
    def _define_achievements(self):
        """Define all available achievements."""
        self._definitions = {
            "first_translation": AchievementDefinition(
                id="first_translation",
                name=self.tr("First Steps"),
                description=self.tr("Complete your first translation"),
                icon="🌱",
                condition_type="translation_count",
                condition_value=1
            ),
            "translations_10": AchievementDefinition(
                id="translations_10",
                name=self.tr("Getting Started"),
                description=self.tr("Complete 10 translations"),
                icon="📝",
                condition_type="translation_count",
                condition_value=10
            ),
            "translations_100": AchievementDefinition(
                id="translations_100",
                name=self.tr("Dedicated Translator"),
                description=self.tr("Complete 100 translations"),
                icon="💯",
                condition_type="translation_count",
                condition_value=100
            ),
            "translations_1000": AchievementDefinition(
                id="translations_1000",
                name=self.tr("Translation Master"),
                description=self.tr("Complete 1000 translations"),
                icon="👑",
                condition_type="translation_count",
                condition_value=1000
            ),
            "full_file": AchievementDefinition(
                id="full_file",
                name=self.tr("Completionist"),
                description=self.tr("Fully translate a file (100% complete)"),
                icon="✅",
                condition_type="file_completion",
                condition_value=100
            ),
            "speed_demon": AchievementDefinition(
                id="speed_demon",
                name=self.tr("Speed Demon"),
                description=self.tr("Translate 50 strings in one hour"),
                icon="⚡",
                condition_type="translations_per_hour",
                condition_value=50
            ),
            "streak_3": AchievementDefinition(
                id="streak_3",
                name=self.tr("Getting Into Rhythm"),
                description=self.tr("Translate for 3 days in a row"),
                icon="🔥",
                condition_type="daily_streak",
                condition_value=3
            ),
            "streak_7": AchievementDefinition(
                id="streak_7",
                name=self.tr("Week Warrior"),
                description=self.tr("Translate for 7 days in a row"),
                icon="🔥🔥",
                condition_type="daily_streak",
                condition_value=7
            ),
            "streak_30": AchievementDefinition(
                id="streak_30",
                name=self.tr("Unstoppable"),
                description=self.tr("Translate for 30 days in a row"),
                icon="🔥🔥🔥",
                condition_type="daily_streak",
                condition_value=30
            ),
            "polyglot_3": AchievementDefinition(
                id="polyglot_3",
                name=self.tr("Polyglot"),
                description=self.tr("Work with 3 different languages"),
                icon="🌍",
                condition_type="language_count",
                condition_value=3
            ),
            "polyglot_5": AchievementDefinition(
                id="polyglot_5",
                name=self.tr("Linguistic Expert"),
                description=self.tr("Work with 5 different languages"),
                icon="🌎",
                condition_type="language_count",
                condition_value=5
            ),
            "early_bird": AchievementDefinition(
                id="early_bird",
                name=self.tr("Early Bird"),
                description=self.tr("Translate before 8 AM"),
                icon="🌅",
                condition_type="early_translation",
                condition_value=8
            ),
            "night_owl": AchievementDefinition(
                id="night_owl",
                name=self.tr("Night Owl"),
                description=self.tr("Translate after 10 PM"),
                icon="🦉",
                condition_type="late_translation",
                condition_value=22
            ),
            "perfectionist": AchievementDefinition(
                id="perfectionist",
                name=self.tr("Perfectionist"),
                description=self.tr("Complete 50 translations without using auto-translate"),
                icon="💎",
                condition_type="manual_translations",
                condition_value=50
            ),
            "explorer": AchievementDefinition(
                id="explorer",
                name=self.tr("Format Explorer"),
                description=self.tr("Work with 5 different file formats"),
                icon="📁",
                condition_type="format_count",
                condition_value=5
            ),
        }
    
    def tr(self, text: str) -> str:
        """Translation helper."""
        return text  # TODO: Implement proper translation
    
    def _load_data(self):
        """Load achievements and stats from disk."""
        # Load achievements
        if self._data_file.exists():
            try:
                data = json.loads(self._data_file.read_text("utf-8"))
                for item in data:
                    achievement = Achievement(
                        id=item["id"],
                        name=item["name"],
                        description=item["description"],
                        icon=item["icon"],
                        unlocked_at=datetime.fromisoformat(item["unlocked_at"]),
                        progress=item.get("progress", 100)
                    )
                    self._achievements[achievement.id] = achievement
            except Exception:
                pass
        
        # Load stats
        if self._stats_file.exists():
            try:
                self._stats = json.loads(self._stats_file.read_text("utf-8"))
            except Exception:
                self._stats = {}
        
        # Initialize default stats
        self._ensure_stats()
    
    def _ensure_stats(self):
        """Ensure all required stats exist with default values."""
        defaults = {
            "total_translations": 0,
            "files_completed": 0,
            "languages_used": [],
            "formats_used": [],
            "daily_activity": {},  # date -> translation_count
            "hourly_sessions": [],  # list of {start_time, translation_count}
            "manual_translations": 0,
            "auto_translations": 0,
            "current_streak": 0,
            "best_streak": 0,
            "last_activity_date": None
        }
        
        for key, default in defaults.items():
            if key not in self._stats:
                self._stats[key] = default
    
    def _save_data(self):
        """Save achievements and stats to disk."""
        # Save achievements
        self._data_file.parent.mkdir(parents=True, exist_ok=True)
        achievements_data = []
        for achievement in self._achievements.values():
            achievements_data.append({
                "id": achievement.id,
                "name": achievement.name,
                "description": achievement.description,
                "icon": achievement.icon,
                "unlocked_at": achievement.unlocked_at.isoformat(),
                "progress": achievement.progress
            })
        
        self._data_file.write_text(
            json.dumps(achievements_data, ensure_ascii=False, indent=2), "utf-8"
        )
        
        # Save stats
        self._stats_file.parent.mkdir(parents=True, exist_ok=True)
        self._stats_file.write_text(
            json.dumps(self._stats, ensure_ascii=False, indent=2), "utf-8"
        )
    
    def record_translation(self, language: str, format_type: str, is_manual: bool = True):
        """Record a translation event and check for achievements."""
        today = date.today().isoformat()
        hour = datetime.now().hour
        
        # Update stats
        self._stats["total_translations"] += 1
        
        if language and language not in self._stats["languages_used"]:
            self._stats["languages_used"].append(language)
        
        if format_type and format_type not in self._stats["formats_used"]:
            self._stats["formats_used"].append(format_type)
        
        if is_manual:
            self._stats["manual_translations"] += 1
        else:
            self._stats["auto_translations"] += 1
        
        # Daily activity
        if today not in self._stats["daily_activity"]:
            self._stats["daily_activity"][today] = 0
        self._stats["daily_activity"][today] += 1
        
        # Update streak
        self._update_streak(today)
        
        # Record hourly session
        now = datetime.now()
        # Clean old sessions (older than 1 hour)
        self._stats["hourly_sessions"] = [
            session for session in self._stats["hourly_sessions"]
            if (now - datetime.fromisoformat(session["start_time"])).seconds < 3600
        ]
        
        # Add/update current hour session
        current_session = None
        for session in self._stats["hourly_sessions"]:
            session_time = datetime.fromisoformat(session["start_time"])
            if session_time.hour == hour and session_time.date() == now.date():
                current_session = session
                break
        
        if current_session:
            current_session["translation_count"] += 1
        else:
            self._stats["hourly_sessions"].append({
                "start_time": now.isoformat(),
                "translation_count": 1
            })
        
        # Check achievements
        self._check_achievements(hour)
        
        # Save data
        self._save_data()
    
    def record_file_completion(self, language: str, format_type: str):
        """Record when a file is fully completed."""
        self._stats["files_completed"] += 1
        
        # Check completion achievement
        if not self.is_unlocked("full_file"):
            self._unlock_achievement("full_file")
        
        self._save_data()
    
    def _update_streak(self, today_str: str):
        """Update the daily translation streak."""
        last_date = self._stats.get("last_activity_date")
        
        if not last_date:
            # First day
            self._stats["current_streak"] = 1
        else:
            last_date_obj = date.fromisoformat(last_date)
            today_obj = date.fromisoformat(today_str)
            
            if (today_obj - last_date_obj).days == 1:
                # Consecutive day
                self._stats["current_streak"] += 1
            elif today_str != last_date:
                # Gap in streak
                self._stats["current_streak"] = 1
            # Same day = no change to streak
        
        # Update best streak
        if self._stats["current_streak"] > self._stats["best_streak"]:
            self._stats["best_streak"] = self._stats["current_streak"]
        
        self._stats["last_activity_date"] = today_str
    
    def _check_achievements(self, current_hour: int):
        """Check and unlock achievements based on current stats."""
        # Translation count achievements
        count = self._stats["total_translations"]
        for achievement_id in ["first_translation", "translations_10", "translations_100", "translations_1000"]:
            if not self.is_unlocked(achievement_id):
                definition = self._definitions[achievement_id]
                if count >= definition.condition_value:
                    self._unlock_achievement(achievement_id)
        
        # Speed achievement
        if not self.is_unlocked("speed_demon"):
            total_in_hour = sum(
                session["translation_count"] 
                for session in self._stats["hourly_sessions"]
            )
            if total_in_hour >= 50:
                self._unlock_achievement("speed_demon")
        
        # Streak achievements
        streak = self._stats["current_streak"]
        for achievement_id in ["streak_3", "streak_7", "streak_30"]:
            if not self.is_unlocked(achievement_id):
                definition = self._definitions[achievement_id]
                if streak >= definition.condition_value:
                    self._unlock_achievement(achievement_id)
        
        # Language achievements
        lang_count = len(self._stats["languages_used"])
        for achievement_id in ["polyglot_3", "polyglot_5"]:
            if not self.is_unlocked(achievement_id):
                definition = self._definitions[achievement_id]
                if lang_count >= definition.condition_value:
                    self._unlock_achievement(achievement_id)
        
        # Time-based achievements
        if not self.is_unlocked("early_bird") and current_hour < 8:
            self._unlock_achievement("early_bird")
        
        if not self.is_unlocked("night_owl") and current_hour >= 22:
            self._unlock_achievement("night_owl")
        
        # Manual translation achievement
        if not self.is_unlocked("perfectionist"):
            if self._stats["manual_translations"] >= 50:
                self._unlock_achievement("perfectionist")
        
        # Format achievement
        if not self.is_unlocked("explorer"):
            format_count = len(self._stats["formats_used"])
            if format_count >= 5:
                self._unlock_achievement("explorer")
    
    def _unlock_achievement(self, achievement_id: str):
        """Unlock an achievement."""
        if achievement_id in self._achievements:
            return  # Already unlocked
        
        definition = self._definitions.get(achievement_id)
        if not definition:
            return
        
        achievement = Achievement(
            id=definition.id,
            name=definition.name,
            description=definition.description,
            icon=definition.icon,
            unlocked_at=datetime.now()
        )
        
        self._achievements[achievement_id] = achievement
        self.achievement_unlocked.emit(achievement)
    
    def is_unlocked(self, achievement_id: str) -> bool:
        """Check if an achievement is unlocked."""
        return achievement_id in self._achievements
    
    def get_unlocked_achievements(self) -> List[Achievement]:
        """Get all unlocked achievements, sorted by unlock time."""
        return sorted(
            self._achievements.values(),
            key=lambda a: a.unlocked_at,
            reverse=True
        )
    
    def get_available_achievements(self) -> List[AchievementDefinition]:
        """Get all achievement definitions."""
        return list(self._definitions.values())
    
    def get_progress(self, achievement_id: str) -> int:
        """Get progress toward an achievement (0-100)."""
        if self.is_unlocked(achievement_id):
            return 100
        
        definition = self._definitions.get(achievement_id)
        if not definition:
            return 0
        
        condition_type = definition.condition_type
        target_value = definition.condition_value
        
        if condition_type == "translation_count":
            current = self._stats["total_translations"]
        elif condition_type == "daily_streak":
            current = self._stats["current_streak"]
        elif condition_type == "language_count":
            current = len(self._stats["languages_used"])
        elif condition_type == "format_count":
            current = len(self._stats["formats_used"])
        elif condition_type == "manual_translations":
            current = self._stats["manual_translations"]
        elif condition_type == "translations_per_hour":
            current = sum(
                session["translation_count"] 
                for session in self._stats["hourly_sessions"]
            )
        else:
            return 0
        
        return min(100, int((current / target_value) * 100))
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current user statistics."""
        return self._stats.copy()
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of achievements and stats."""
        total_achievements = len(self._definitions)
        unlocked_count = len(self._achievements)
        
        return {
            "total_translations": self._stats["total_translations"],
            "achievement_progress": f"{unlocked_count}/{total_achievements}",
            "current_streak": self._stats["current_streak"],
            "best_streak": self._stats["best_streak"],
            "languages_used": len(self._stats["languages_used"]),
            "recent_achievements": self.get_unlocked_achievements()[:3]
        }


# Global instance
_achievement_manager: Optional[AchievementManager] = None


def get_achievement_manager() -> AchievementManager:
    """Get the global achievement manager."""
    global _achievement_manager
    if _achievement_manager is None:
        _achievement_manager = AchievementManager()
    return _achievement_manager