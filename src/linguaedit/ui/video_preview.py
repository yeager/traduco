"""Video Preview Widget — professional dockable video player for subtitle translation.

Provides a QDockWidget-based video player with 16:9 aspect ratio, subtitle overlay,
transport controls, volume, speed control, and segment synchronisation.

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QSlider, QLabel, QStyle, QSizePolicy, QDockWidget,
    QComboBox, QCheckBox, QFrame, QToolButton,
)
from PySide6.QtCore import Qt, QUrl, Signal, QTimer, QSize, QRect
from PySide6.QtGui import QKeySequence, QShortcut, QFont, QPainter, QColor, QPen
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget


# ── Helpers ──────────────────────────────────────────────────────

def _ms_to_timestamp(ms: int) -> str:
    s = max(0, ms) // 1000
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _ms_to_timestamp_precise(ms: int) -> str:
    total_ms = max(0, ms)
    s, ms_part = divmod(total_ms, 1000)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms_part:03d}"


def _parse_time_to_ms(time_str: str) -> int:
    time_str = time_str.strip().replace(",", ".")
    parts = time_str.split(":")
    if len(parts) == 3:
        h, m, rest = parts
        if "." in rest:
            s, ms_part = rest.split(".", 1)
            ms_part = ms_part.ljust(3, "0")[:3]
        else:
            s, ms_part = rest, "0"
        return int(h) * 3600000 + int(m) * 60000 + int(s) * 1000 + int(ms_part)
    return 0


# ── Subtitle overlay (transparent widget on top of video) ───────

class _SubtitleOverlay(QWidget):
    """Transparent widget painted on top of the video surface."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._source_text = ""
        self._translation_text = ""
        self._font_size = 18

    def set_texts(self, source: str, translation: str):
        self._source_text = source
        self._translation_text = translation
        self.update()

    def set_font_size(self, size: int):
        self._font_size = max(10, min(48, size))
        self.update()

    def paintEvent(self, event):
        if not self._source_text and not self._translation_text:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        margin = 16
        bg = QColor(0, 0, 0, 190)

        lines = []
        if self._translation_text:
            # Show translation in yellow
            lines.append((self._translation_text, self._font_size, QColor(255, 255, 60)))
        elif self._source_text:
            # No translation — show source in red to indicate untranslated
            lines.append((self._source_text, self._font_size, QColor(255, 80, 80)))

        total_h = 0
        metrics = []
        for text, size, color in lines:
            font = QFont("Helvetica Neue", size)
            font.setPixelSize(size)
            font.setBold(True)
            p.setFont(font)
            fm = p.fontMetrics()
            br = fm.boundingRect(0, 0, w - 2 * margin - 20, 0,
                                 Qt.AlignCenter | Qt.TextWordWrap, text)
            metrics.append((text, font, color, br))
            total_h += br.height() + 8

        y = h - total_h - margin - 14
        for text, font, color, br in metrics:
            rect_h = br.height() + 12
            rx = margin
            rw = w - 2 * margin
            p.setPen(Qt.NoPen)
            p.setBrush(bg)
            p.drawRoundedRect(QRect(rx, int(y), rw, int(rect_h)), 6, 6)
            p.setFont(font)
            p.setPen(QColor(0, 0, 0, 220))
            for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
                p.drawText(rx + 10 + dx, int(y + 6 + dy), rw - 20, int(rect_h - 12),
                           Qt.AlignCenter | Qt.TextWordWrap, text)
            p.setPen(color)
            p.drawText(rx + 10, int(y + 6), rw - 20, int(rect_h - 12),
                       Qt.AlignCenter | Qt.TextWordWrap, text)
            y += rect_h + 3
        p.end()


# ── Video widget with subtitle overlay ──────────────────────────

class _VideoWithSubtitles(QVideoWidget):
    """QVideoWidget with a child overlay widget for subtitles."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._overlay = _SubtitleOverlay(self)
        self._overlay.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._overlay.setGeometry(self.rect())

    def set_texts(self, source: str, translation: str):
        self._overlay.set_texts(source, translation)

    def set_font_size(self, size: int):
        self._overlay.set_font_size(size)


# ── Segment progress slider ────────────────────────────────────

class _VideoSlider(QSlider):
    """Slider with optional segment highlight region."""

    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self._seg_start = -1
        self._seg_end = -1

    def set_segment_range(self, start_ms: int, end_ms: int):
        self._seg_start = start_ms
        self._seg_end = end_ms
        self.update()

    def clear_segment_range(self):
        self._seg_start = -1
        self._seg_end = -1
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._seg_start < 0 or self.maximum() <= 0:
            return
        p = QPainter(self)
        total = self.maximum()
        x1 = int(self._seg_start / total * self.width())
        x2 = int(self._seg_end / total * self.width())
        p.fillRect(x1, 0, max(x2 - x1, 2), self.height(), QColor(100, 180, 255, 80))
        p.end()


# ── Button style ────────────────────────────────────────────────

_BTN_SIZE = 36
_BTN_STYLE = """
    QPushButton, QToolButton {
        font-size: 16px;
        border: 1px solid palette(mid);
        border-radius: 6px;
        background: palette(button);
        color: palette(buttonText);
        padding: 2px;
    }
    QPushButton:hover, QToolButton:hover {
        background: palette(light);
    }
    QPushButton:pressed, QToolButton:pressed {
        background: palette(mid);
    }
    QPushButton:checked {
        background: #3daee9;
        color: white;
        border-color: #2d8bc9;
    }
"""


# ── Main widget (inside dock) ──────────────────────────────────

class VideoPreviewWidget(QWidget):
    """Embedded video player for subtitle translation workflow."""

    request_prev_segment = Signal()
    request_next_segment = Signal()
    request_goto_current_time = Signal(int)

    _SPEEDS = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0]

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumSize(360, 260)

        # State
        self._video_path: Optional[Path] = None
        self._seg_start_ms = -1
        self._seg_end_ms = -1
        self._loop_enabled = False
        self._auto_pause = False
        self._subtitle_entries = []
        self._sub_font_size = 18

        # ── Layout ──
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Video widget (with built-in subtitle painting)
        self._video_widget = _VideoWithSubtitles()
        self._video_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        main_layout.addWidget(self._video_widget, 1)

        # ── Slider ──
        self._slider = _VideoSlider(Qt.Horizontal)
        self._slider.setRange(0, 0)
        self._slider.sliderMoved.connect(self._on_slider_seek)
        self._slider.setFixedHeight(20)
        self._slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 6px;
                background: palette(dark);
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                width: 14px;
                height: 14px;
                margin: -4px 0;
                background: #3daee9;
                border-radius: 7px;
            }
            QSlider::sub-page:horizontal {
                background: #3daee9;
                border-radius: 3px;
            }
        """)
        main_layout.addWidget(self._slider)

        # ── Info row ──
        info_row = QHBoxLayout()
        info_row.setContentsMargins(8, 2, 8, 2)
        self._segment_label = QLabel("")
        self._segment_label.setStyleSheet(
            "font-family: Menlo, Consolas, monospace; font-size: 10px; color: palette(light);"
        )
        info_row.addWidget(self._segment_label)
        info_row.addStretch()
        self._time_label = QLabel("00:00:00 / 00:00:00")
        self._time_label.setStyleSheet(
            "font-family: Menlo, Consolas, monospace; font-size: 11px;"
        )
        info_row.addWidget(self._time_label)
        main_layout.addLayout(info_row)

        # ── Transport controls ──
        controls = QHBoxLayout()
        controls.setContentsMargins(6, 4, 6, 6)
        controls.setSpacing(5)

        # Stop
        self._stop_btn = QPushButton("⏹")
        self._stop_btn.setFixedSize(_BTN_SIZE, _BTN_SIZE)
        self._stop_btn.setToolTip(self.tr("Stop (S)"))
        self._stop_btn.clicked.connect(self._stop)
        controls.addWidget(self._stop_btn)

        # Play/Pause
        self._play_btn = QPushButton("▶")
        self._play_btn.setFixedSize(_BTN_SIZE + 4, _BTN_SIZE + 4)
        self._play_btn.setToolTip(self.tr("Play / Pause (Space)"))
        self._play_btn.setStyleSheet(_BTN_STYLE + """
            QPushButton { font-size: 20px; }
        """)
        self._play_btn.clicked.connect(self._toggle_play)
        controls.addWidget(self._play_btn)

        # Step back
        self._step_back_btn = QPushButton("⏪")
        self._step_back_btn.setFixedSize(_BTN_SIZE, _BTN_SIZE)
        self._step_back_btn.setToolTip(self.tr("Back 1s (Shift+←)"))
        self._step_back_btn.clicked.connect(lambda: self._seek_relative(-1000))
        controls.addWidget(self._step_back_btn)

        # Step forward
        self._step_fwd_btn = QPushButton("⏩")
        self._step_fwd_btn.setFixedSize(_BTN_SIZE, _BTN_SIZE)
        self._step_fwd_btn.setToolTip(self.tr("Forward 1s (Shift+→)"))
        self._step_fwd_btn.clicked.connect(lambda: self._seek_relative(1000))
        controls.addWidget(self._step_fwd_btn)

        # Separator
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.VLine)
        sep1.setFixedHeight(24)
        controls.addWidget(sep1)

        # Previous entry
        self._prev_btn = QPushButton("⏮")
        self._prev_btn.setFixedSize(_BTN_SIZE, _BTN_SIZE)
        self._prev_btn.setToolTip(self.tr("Previous entry (Ctrl+←)"))
        self._prev_btn.clicked.connect(self.request_prev_segment.emit)
        controls.addWidget(self._prev_btn)

        # Go to current subtitle
        self._goto_btn = QPushButton("⎆")
        self._goto_btn.setFixedSize(_BTN_SIZE, _BTN_SIZE)
        self._goto_btn.setToolTip(self.tr("Go to current subtitle (G)"))
        self._goto_btn.clicked.connect(self._goto_current_segment)
        controls.addWidget(self._goto_btn)

        # Next entry
        self._next_btn = QPushButton("⏭")
        self._next_btn.setFixedSize(_BTN_SIZE, _BTN_SIZE)
        self._next_btn.setToolTip(self.tr("Next entry (Ctrl+→)"))
        self._next_btn.clicked.connect(self.request_next_segment.emit)
        controls.addWidget(self._next_btn)

        # Separator
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.VLine)
        sep2.setFixedHeight(24)
        controls.addWidget(sep2)

        # AB-repeat
        self._loop_btn = QPushButton("A⇄B")
        self._loop_btn.setFixedSize(_BTN_SIZE + 10, _BTN_SIZE)
        self._loop_btn.setCheckable(True)
        self._loop_btn.setToolTip(self.tr("Loop segment (L)"))
        self._loop_btn.toggled.connect(self._on_loop_toggled)
        controls.addWidget(self._loop_btn)

        # Auto-pause
        self._auto_pause_cb = QCheckBox(self.tr("Pause"))
        self._auto_pause_cb.setToolTip(self.tr("Pause at segment end"))
        self._auto_pause_cb.toggled.connect(self._on_auto_pause_toggled)
        controls.addWidget(self._auto_pause_cb)

        controls.addStretch(1)

        # Speed
        self._speed_combo = QComboBox()
        for s in self._SPEEDS:
            self._speed_combo.addItem(f"{s}x", s)
        self._speed_combo.setCurrentIndex(self._SPEEDS.index(1.0))
        self._speed_combo.currentIndexChanged.connect(self._on_speed_changed)
        self._speed_combo.setFixedWidth(64)
        self._speed_combo.setToolTip(self.tr("Playback speed"))
        controls.addWidget(self._speed_combo)

        main_layout.addLayout(controls)

        # ── Volume row ──
        vol_row = QHBoxLayout()
        vol_row.setContentsMargins(6, 0, 6, 6)
        vol_row.setSpacing(5)

        self._vol_label = QLabel("🔊")
        self._vol_label.setStyleSheet("font-size: 16px;")
        vol_row.addWidget(self._vol_label)

        self._vol_slider = QSlider(Qt.Horizontal)
        self._vol_slider.setRange(0, 100)
        self._vol_slider.setValue(80)
        self._vol_slider.setFixedHeight(18)
        self._vol_slider.setToolTip(self.tr("Volume"))
        self._vol_slider.valueChanged.connect(self._on_volume_changed)
        self._vol_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 4px;
                background: palette(dark);
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                width: 12px;
                height: 12px;
                margin: -4px 0;
                background: palette(light);
                border-radius: 6px;
            }
            QSlider::sub-page:horizontal {
                background: palette(light);
                border-radius: 2px;
            }
        """)
        vol_row.addWidget(self._vol_slider, 1)

        self._mute_btn = QPushButton("🔇")
        self._mute_btn.setFixedSize(28, 28)
        self._mute_btn.setToolTip(self.tr("Mute (M)"))
        self._mute_btn.clicked.connect(self._toggle_mute)
        vol_row.addWidget(self._mute_btn)

        # Font size controls
        sep3 = QFrame()
        sep3.setFrameShape(QFrame.VLine)
        sep3.setFixedHeight(20)
        vol_row.addWidget(sep3)

        self._font_down_btn = QPushButton("A−")
        self._font_down_btn.setFixedSize(28, 28)
        self._font_down_btn.setToolTip(self.tr("Smaller subtitles"))
        self._font_down_btn.clicked.connect(lambda: self._change_font_size(-2))
        vol_row.addWidget(self._font_down_btn)

        self._font_up_btn = QPushButton("A+")
        self._font_up_btn.setFixedSize(28, 28)
        self._font_up_btn.setToolTip(self.tr("Larger subtitles"))
        self._font_up_btn.clicked.connect(lambda: self._change_font_size(2))
        vol_row.addWidget(self._font_up_btn)

        main_layout.addLayout(vol_row)

        # Apply button styling
        self.setStyleSheet(_BTN_STYLE)

        # ── Media player ──
        self._player = QMediaPlayer()
        self._audio = QAudioOutput()
        self._audio.setVolume(0.8)
        self._player.setAudioOutput(self._audio)
        self._player.setVideoOutput(self._video_widget)
        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.playbackStateChanged.connect(self._on_state_changed)
        self._muted = False

        # Subtitle sync timer
        self._sub_timer = QTimer(self)
        self._sub_timer.setInterval(80)
        self._sub_timer.timeout.connect(self._update_subtitle_at_position)

        self._setup_shortcuts()

    def _setup_shortcuts(self):
        QShortcut(QKeySequence(Qt.Key_Space), self, self._toggle_play)
        QShortcut(QKeySequence(Qt.Key_Left), self, lambda: self._seek_relative(-5000))
        QShortcut(QKeySequence(Qt.Key_Right), self, lambda: self._seek_relative(5000))
        QShortcut(QKeySequence("Shift+Left"), self, lambda: self._seek_relative(-1000))
        QShortcut(QKeySequence("Shift+Right"), self, lambda: self._seek_relative(1000))
        QShortcut(QKeySequence("Ctrl+Left"), self, self.request_prev_segment.emit)
        QShortcut(QKeySequence("Ctrl+Right"), self, self.request_next_segment.emit)
        QShortcut(QKeySequence(Qt.Key_Plus), self, self._speed_up)
        QShortcut(QKeySequence(Qt.Key_Minus), self, self._speed_down)
        QShortcut(QKeySequence(Qt.Key_Equal), self, self._speed_up)
        QShortcut(QKeySequence(Qt.Key_G), self, self._goto_current_segment)
        QShortcut(QKeySequence(Qt.Key_L), self, lambda: self._loop_btn.toggle())
        QShortcut(QKeySequence(Qt.Key_S), self, self._stop)
        QShortcut(QKeySequence(Qt.Key_M), self, self._toggle_mute)

    # ── Public API ──

    def open_video(self, path: Path):
        self._video_path = path
        self._player.setSource(QUrl.fromLocalFile(str(path)))

    def set_subtitle_entries(self, entries: list):
        """entries: list of (start_ms, end_ms, source_text, translation_text)"""
        self._subtitle_entries = entries

    def seek_to_time(self, time_str: str):
        ms = _parse_time_to_ms(time_str)
        if ms >= 0:
            self._player.setPosition(ms)
            if self._player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
                self._player.play()

    def seek_to_ms(self, ms: int):
        self._player.setPosition(ms)
        if self._player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
            self._player.play()

    def set_segment(self, start_time: str, end_time: str, source: str, translation: str):
        self._seg_start_ms = _parse_time_to_ms(start_time)
        self._seg_end_ms = _parse_time_to_ms(end_time)
        self._slider.set_segment_range(self._seg_start_ms, self._seg_end_ms)
        self._video_widget.set_texts(source, translation)
        duration_ms = self._seg_end_ms - self._seg_start_ms
        self._segment_label.setText(
            f"▶ {_ms_to_timestamp_precise(self._seg_start_ms)} → "
            f"{_ms_to_timestamp_precise(self._seg_end_ms)}  "
            f"({duration_ms / 1000:.1f}s)"
        )

    def show_subtitle(self, text: str):
        self._video_widget.set_texts("", text)

    def set_subtitle_font_size(self, size: int):
        self._sub_font_size = size
        self._video_widget.set_font_size(size)

    def has_video(self) -> bool:
        return self._video_path is not None

    # ── Private slots ──

    def _toggle_play(self):
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
            self._sub_timer.stop()
        else:
            self._player.play()
            self._sub_timer.start()

    def _stop(self):
        self._player.stop()
        self._player.setPosition(0)
        self._sub_timer.stop()
        self._video_widget.set_texts("", "")

    def _goto_current_segment(self):
        pos = self._player.position()
        self.request_goto_current_time.emit(pos)

    def _seek_relative(self, delta_ms: int):
        pos = max(0, self._player.position() + delta_ms)
        self._player.setPosition(pos)

    def _on_slider_seek(self, position: int):
        self._player.setPosition(position)

    def _on_position_changed(self, position: int):
        self._slider.setValue(position)
        total = self._player.duration()
        self._time_label.setText(
            f"{_ms_to_timestamp(position)} / {_ms_to_timestamp(total)}"
        )
        if self._loop_enabled and self._seg_end_ms > 0 and position >= self._seg_end_ms:
            self._player.setPosition(self._seg_start_ms)
        elif self._auto_pause and self._seg_end_ms > 0 and position >= self._seg_end_ms:
            self._player.pause()
            self._sub_timer.stop()

    def _update_subtitle_at_position(self):
        if not self._subtitle_entries:
            return
        pos = self._player.position()
        for start_ms, end_ms, source, translation in self._subtitle_entries:
            if start_ms <= pos <= end_ms:
                self._video_widget.set_texts(source, translation)
                return
        self._video_widget.set_texts("", "")

    def _on_duration_changed(self, duration: int):
        self._slider.setRange(0, duration)

    def _on_state_changed(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self._play_btn.setText("⏸")
            self._sub_timer.start()
        else:
            self._play_btn.setText("▶")
            if state == QMediaPlayer.PlaybackState.StoppedState:
                self._sub_timer.stop()

    def _on_loop_toggled(self, checked: bool):
        self._loop_enabled = checked

    def _on_auto_pause_toggled(self, checked: bool):
        self._auto_pause = checked

    def _on_speed_changed(self, index: int):
        speed = self._speed_combo.currentData()
        if speed:
            self._player.setPlaybackRate(speed)

    def _speed_up(self):
        idx = min(self._speed_combo.currentIndex() + 1, self._speed_combo.count() - 1)
        self._speed_combo.setCurrentIndex(idx)

    def _speed_down(self):
        idx = max(self._speed_combo.currentIndex() - 1, 0)
        self._speed_combo.setCurrentIndex(idx)

    def _on_volume_changed(self, value: int):
        self._audio.setVolume(value / 100.0)
        if value == 0:
            self._vol_label.setText("🔇")
        elif value < 50:
            self._vol_label.setText("🔉")
        else:
            self._vol_label.setText("🔊")

    def _toggle_mute(self):
        self._muted = not self._muted
        self._audio.setMuted(self._muted)
        if self._muted:
            self._vol_label.setText("🔇")
            self._mute_btn.setText("🔊")
        else:
            self._on_volume_changed(self._vol_slider.value())
            self._mute_btn.setText("🔇")

    def _change_font_size(self, delta: int):
        self._sub_font_size = max(10, min(48, self._sub_font_size + delta))
        self._video_widget.set_font_size(self._sub_font_size)

    def closeEvent(self, event):
        self._player.stop()
        self._sub_timer.stop()
        super().closeEvent(event)


# ── Dock wrapper ────────────────────────────────────────────────

class VideoDockWidget(QDockWidget):
    """QDockWidget wrapper around VideoPreviewWidget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("VideoDock")
        self.setWindowTitle(self.tr("Video Preview"))
        self.setAllowedAreas(
            Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea
        )
        self._player_widget = VideoPreviewWidget(self)
        self.setWidget(self._player_widget)
        self.setMinimumWidth(420)
        self.setMinimumHeight(340)

    @property
    def player(self) -> VideoPreviewWidget:
        return self._player_widget

    def open_video(self, path: Path):
        self._player_widget.open_video(path)
        self.setWindowTitle(self.tr("Video Preview") + f" — {path.name}")
        self.show()
        self.raise_()

    def closeEvent(self, event):
        self._player_widget.closeEvent(event)
        super().closeEvent(event)
