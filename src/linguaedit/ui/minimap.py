"""Minimap widget för översikt av översättningsstatus."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QFontMetrics, QMouseEvent


class MinimapWidget(QWidget):
    """Minimap som visar översikt av alla entries med färgkodning."""
    
    # Signal när användaren klickar för att hoppa till en position
    jump_to_entry = Signal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(80)
        self.setMaximumWidth(120)
        
        self._entries = []  # Lista med (source, target, is_fuzzy) tupler
        self._current_index = 0
        self._pixels_per_entry = 2
        self._font = QFont("Monaco", 7)  # Liten monospace font
        self._font_metrics = QFontMetrics(self._font)
        
        # Färger
        self._colors = {
            'translated': QColor(144, 238, 144),    # Ljusgrön
            'untranslated': QColor(255, 182, 193),  # Ljusröd
            'fuzzy': QColor(255, 255, 224),         # Ljusgul
            'current': QColor(65, 105, 225),        # Royal blue
            'background': QColor(248, 248, 248),    # Ljusgrå
        }
        
        self.setToolTip(self.tr("Minimap: Click to jump to entry"))
    
    def set_entries(self, entries: list[tuple[str, str, bool]]):
        """Ställ in entries för minimap."""
        self._entries = entries
        self._update_size()
        self.update()
    
    def set_current_index(self, index: int):
        """Markera nuvarande entry."""
        self._current_index = index
        self.update()
    
    def _update_size(self):
        """Uppdatera widget-storlek baserat på antal entries."""
        if not self._entries:
            return
            
        total_height = len(self._entries) * self._pixels_per_entry
        self.setMinimumHeight(total_height)
        self.setMaximumHeight(total_height)
    
    def paintEvent(self, event):
        """Rita minimap."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        rect = self.rect()
        
        # Bakgrund
        painter.fillRect(rect, QBrush(self._colors['background']))
        
        if not self._entries:
            return
        
        # Rita varje entry som en färgad rad
        entry_height = max(1, self._pixels_per_entry)
        
        for i, (source, target, is_fuzzy) in enumerate(self._entries):
            y = i * self._pixels_per_entry
            entry_rect = rect.adjusted(2, y, -2, y + entry_height)
            
            # Välj färg baserat på status
            if not target.strip():
                color = self._colors['untranslated']
            elif is_fuzzy:
                color = self._colors['fuzzy']
            else:
                color = self._colors['translated']
            
            painter.fillRect(entry_rect, QBrush(color))
            
            # Markera current entry
            if i == self._current_index:
                pen = QPen(self._colors['current'], 2)
                painter.setPen(pen)
                painter.drawRect(entry_rect)
        
        # Rita progress-indikator på sidan
        if self._entries:
            translated_count = sum(1 for _, target, is_fuzzy in self._entries 
                                 if target.strip() and not is_fuzzy)
            total_count = len(self._entries)
            progress = translated_count / total_count if total_count > 0 else 0
            
            progress_height = int(rect.height() * progress)
            progress_rect = rect.adjusted(rect.width() - 8, rect.height() - progress_height, 
                                        -2, -2)
            
            painter.fillRect(progress_rect, QBrush(self._colors['translated']))
            
            # Progress text
            painter.setFont(QFont("Arial", 8))
            painter.setPen(QPen(Qt.black))
            progress_text = f"{progress:.0%}"
            text_rect = self._font_metrics.boundingRect(progress_text)
            text_x = rect.width() - text_rect.width() - 4
            text_y = 15
            painter.drawText(text_x, text_y, progress_text)
    
    def mousePressEvent(self, event: QMouseEvent):
        """Hantera klick för att hoppa till entry."""
        if event.button() == Qt.LeftButton and self._entries:
            y = event.position().y()
            entry_index = int(y / self._pixels_per_entry)
            entry_index = max(0, min(entry_index, len(self._entries) - 1))
            
            self.jump_to_entry.emit(entry_index)
        
        super().mousePressEvent(event)
    
    def set_pixels_per_entry(self, pixels: int):
        """Ställ in hur många pixlar per entry."""
        self._pixels_per_entry = max(1, pixels)
        self._update_size()
        self.update()
    
    def set_color_theme(self, colors: dict):
        """Ställ in färgtema."""
        self._colors.update(colors)
        self.update()