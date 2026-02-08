"""Achievements dialog — view unlocked achievements and progress."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QScrollArea, QWidget,
    QPushButton, QLabel, QProgressBar, QGroupBox, QGridLayout,
    QFrame, QTextEdit, QTabWidget
)
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QFont, QPixmap, QPainter, QColor, QBrush

from linguaedit.services.achievements import get_achievement_manager


class AchievementWidget(QFrame):
    """Widget representing a single achievement."""
    
    def __init__(self, achievement_def, progress=0, unlocked_at=None):
        super().__init__()
        self.achievement_def = achievement_def
        self.progress = progress
        self.unlocked_at = unlocked_at
        self.is_unlocked = progress >= 100
        
        self._build_ui()
    
    def _build_ui(self):
        """Build the achievement widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Set frame style
        self.setFrameStyle(QFrame.Box)
        if self.is_unlocked:
            self.setStyleSheet("""
                QFrame {
                    border: 2px solid #4CAF50;
                    border-radius: 8px;
                    background-color: #E8F5E8;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame {
                    border: 2px solid #CCCCCC;
                    border-radius: 8px;
                    background-color: #F5F5F5;
                }
            """)
        
        # Top row: icon and name
        top_layout = QHBoxLayout()
        
        # Icon
        icon_label = QLabel(self.achievement_def.icon)
        icon_font = QFont()
        icon_font.setPointSize(24)
        icon_label.setFont(icon_font)
        icon_label.setFixedSize(40, 40)
        icon_label.setAlignment(Qt.AlignCenter)
        top_layout.addWidget(icon_label)
        
        # Name and description
        text_layout = QVBoxLayout()
        
        name_label = QLabel(self.achievement_def.name)
        name_font = QFont()
        name_font.setPointSize(name_font.pointSize() + 1)
        name_font.setBold(True)
        name_label.setFont(name_font)
        if not self.is_unlocked:
            name_label.setStyleSheet("color: #666666;")
        text_layout.addWidget(name_label)
        
        desc_label = QLabel(self.achievement_def.description)
        desc_label.setWordWrap(True)
        if not self.is_unlocked:
            desc_label.setStyleSheet("color: #888888;")
        text_layout.addWidget(desc_label)
        
        top_layout.addLayout(text_layout)
        top_layout.addStretch()
        
        layout.addLayout(top_layout)
        
        # Progress bar (if not unlocked)
        if not self.is_unlocked:
            progress_bar = QProgressBar()
            progress_bar.setMinimum(0)
            progress_bar.setMaximum(100)
            progress_bar.setValue(self.progress)
            progress_bar.setTextVisible(True)
            progress_bar.setFormat(f"{self.progress}%")
            layout.addWidget(progress_bar)
        else:
            # Unlocked date
            if self.unlocked_at:
                unlocked_label = QLabel(
                    self.tr("Unlocked: {}").format(
                        self.unlocked_at.strftime("%Y-%m-%d %H:%M")
                    )
                )
                unlocked_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
                layout.addWidget(unlocked_label)
        
        self.setMaximumHeight(120)
    
    def tr(self, text: str) -> str:
        """Translation helper."""
        return text


class StatsWidget(QWidget):
    """Widget showing user statistics."""
    
    def __init__(self, stats):
        super().__init__()
        self.stats = stats
        self._build_ui()
    
    def _build_ui(self):
        """Build the stats widget."""
        layout = QVBoxLayout(self)
        
        # Main stats
        main_group = QGroupBox(self.tr("Translation Statistics"))
        main_layout = QGridLayout(main_group)
        
        stats_data = [
            (self.tr("Total Translations"), str(self.stats.get("total_translations", 0))),
            (self.tr("Files Completed"), str(self.stats.get("files_completed", 0))),
            (self.tr("Languages Used"), str(len(self.stats.get("languages_used", [])))),
            (self.tr("File Formats"), str(len(self.stats.get("formats_used", [])))),
            (self.tr("Current Streak"), f"{self.stats.get('current_streak', 0)} days"),
            (self.tr("Best Streak"), f"{self.stats.get('best_streak', 0)} days"),
            (self.tr("Manual Translations"), str(self.stats.get("manual_translations", 0))),
            (self.tr("Auto Translations"), str(self.stats.get("auto_translations", 0))),
        ]
        
        for i, (label, value) in enumerate(stats_data):
            row = i // 2
            col = (i % 2) * 2
            
            label_widget = QLabel(f"{label}:")
            label_widget.setAlignment(Qt.AlignRight)
            main_layout.addWidget(label_widget, row, col)
            
            value_widget = QLabel(value)
            value_font = QFont()
            value_font.setBold(True)
            value_widget.setFont(value_font)
            main_layout.addWidget(value_widget, row, col + 1)
        
        layout.addWidget(main_group)
        
        # Languages and formats
        details_group = QGroupBox(self.tr("Details"))
        details_layout = QVBoxLayout(details_group)
        
        # Languages
        languages = self.stats.get("languages_used", [])
        if languages:
            lang_label = QLabel(self.tr("Languages: {}").format(", ".join(languages)))
            lang_label.setWordWrap(True)
            details_layout.addWidget(lang_label)
        
        # Formats
        formats = self.stats.get("formats_used", [])
        if formats:
            format_label = QLabel(self.tr("Formats: {}").format(", ".join(formats)))
            format_label.setWordWrap(True)
            details_layout.addWidget(format_label)
        
        layout.addWidget(details_group)
        layout.addStretch()
    
    def tr(self, text: str) -> str:
        """Translation helper."""
        return text


class AchievementsDialog(QDialog):
    """Dialog showing achievements and statistics."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Achievements"))
        self.setModal(True)
        self.resize(900, 700)
        
        self._achievement_manager = get_achievement_manager()
        
        self._build_ui()
        self._load_data()
    
    def _build_ui(self):
        """Build the dialog UI."""
        layout = QVBoxLayout(self)
        
        # Header with overall progress
        header_group = QGroupBox(self.tr("Achievement Progress"))
        header_layout = QVBoxLayout(header_group)
        
        summary = self._achievement_manager.get_summary()
        
        # Overall progress
        progress_layout = QHBoxLayout()
        
        progress_label = QLabel(self.tr("Overall Progress:"))
        progress_layout.addWidget(progress_label)
        
        overall_progress = QProgressBar()
        all_achievements = self._achievement_manager.get_available_achievements()
        unlocked = self._achievement_manager.get_unlocked_achievements()
        progress_value = int((len(unlocked) / len(all_achievements)) * 100) if all_achievements else 0
        overall_progress.setValue(progress_value)
        overall_progress.setTextVisible(True)
        overall_progress.setFormat(f"{len(unlocked)}/{len(all_achievements)} ({progress_value}%)")
        progress_layout.addWidget(overall_progress)
        
        header_layout.addLayout(progress_layout)
        
        # Quick stats
        quick_stats = QLabel(
            self.tr("Translations: {0} | Streak: {1} days | Languages: {2}").format(
                summary.get("total_translations", 0),
                summary.get("current_streak", 0),
                summary.get("languages_used", 0)
            )
        )
        quick_stats.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(quick_stats)
        
        layout.addWidget(header_group)
        
        # Tabs
        tabs = QTabWidget()
        
        # Achievements tab
        achievements_tab = self._build_achievements_tab()
        tabs.addTab(achievements_tab, self.tr("Achievements"))
        
        # Statistics tab
        stats_tab = self._build_statistics_tab()
        tabs.addTab(stats_tab, self.tr("Statistics"))
        
        layout.addWidget(tabs)
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        close_btn = QPushButton(self.tr("Close"))
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def _build_achievements_tab(self) -> QWidget:
        """Build the achievements tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Filter buttons
        filter_layout = QHBoxLayout()
        
        self._show_all_btn = QPushButton(self.tr("All"))
        self._show_all_btn.setCheckable(True)
        self._show_all_btn.setChecked(True)
        self._show_all_btn.clicked.connect(lambda: self._filter_achievements("all"))
        filter_layout.addWidget(self._show_all_btn)
        
        self._show_unlocked_btn = QPushButton(self.tr("Unlocked"))
        self._show_unlocked_btn.setCheckable(True)
        self._show_unlocked_btn.clicked.connect(lambda: self._filter_achievements("unlocked"))
        filter_layout.addWidget(self._show_unlocked_btn)
        
        self._show_locked_btn = QPushButton(self.tr("Locked"))
        self._show_locked_btn.setCheckable(True)
        self._show_locked_btn.clicked.connect(lambda: self._filter_achievements("locked"))
        filter_layout.addWidget(self._show_locked_btn)
        
        filter_layout.addStretch()
        layout.addLayout(filter_layout)
        
        # Achievements scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        self._achievements_container = QWidget()
        self._achievements_layout = QVBoxLayout(self._achievements_container)
        self._achievements_layout.setSpacing(10)
        
        scroll.setWidget(self._achievements_container)
        layout.addWidget(scroll)
        
        return widget
    
    def _build_statistics_tab(self) -> QWidget:
        """Build the statistics tab."""
        stats = self._achievement_manager.get_stats()
        return StatsWidget(stats)
    
    def _load_data(self):
        """Load achievement data."""
        self._all_achievements = self._achievement_manager.get_available_achievements()
        self._unlocked_achievements = {
            ach.id: ach for ach in self._achievement_manager.get_unlocked_achievements()
        }
        
        self._update_achievements_display()
    
    def _update_achievements_display(self):
        """Update the achievements display based on current filter."""
        # Clear existing widgets
        while self._achievements_layout.count():
            child = self._achievements_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Determine which achievements to show
        achievements_to_show = []
        
        if self._show_all_btn.isChecked():
            achievements_to_show = self._all_achievements
        elif self._show_unlocked_btn.isChecked():
            achievements_to_show = [
                ach_def for ach_def in self._all_achievements
                if ach_def.id in self._unlocked_achievements
            ]
        elif self._show_locked_btn.isChecked():
            achievements_to_show = [
                ach_def for ach_def in self._all_achievements
                if ach_def.id not in self._unlocked_achievements
            ]
        
        # Sort achievements: unlocked first, then by progress
        def sort_key(ach_def):
            is_unlocked = ach_def.id in self._unlocked_achievements
            progress = self._achievement_manager.get_progress(ach_def.id)
            return (not is_unlocked, -progress, ach_def.name)
        
        achievements_to_show.sort(key=sort_key)
        
        # Create widgets
        for ach_def in achievements_to_show:
            progress = self._achievement_manager.get_progress(ach_def.id)
            unlocked_ach = self._unlocked_achievements.get(ach_def.id)
            unlocked_at = unlocked_ach.unlocked_at if unlocked_ach else None
            
            widget = AchievementWidget(ach_def, progress, unlocked_at)
            self._achievements_layout.addWidget(widget)
        
        # Add stretch at the end
        self._achievements_layout.addStretch()
    
    @Slot()
    def _filter_achievements(self, filter_type: str):
        """Handle achievement filter change."""
        # Update button states
        self._show_all_btn.setChecked(filter_type == "all")
        self._show_unlocked_btn.setChecked(filter_type == "unlocked")
        self._show_locked_btn.setChecked(filter_type == "locked")
        
        # Update display
        self._update_achievements_display()