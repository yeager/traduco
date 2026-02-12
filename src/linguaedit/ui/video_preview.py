"""Video Preview Widget — professional dockable video player for subtitle translation.

Provides a QDockWidget-based video player with 16:9 aspect ratio, subtitle overlay,
transport controls (play/pause/stop), AB-repeat, speed control, go-to-segment,
frame stepping, and segment synchronisation.

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QSlider, QLabel, QStyle, QSizePolicy, QDockWidget,
    QComboBox, QCheckBox, QToolButton, QFrame,
)
from PySide6.QtCore import Qt, QUrl, Slot, Signal, QTimer, QSize
from PySide6.QtGui import QKeySequence, QShortcut, QFont, QPainter, QColor, QIcon
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget


# ── Helpers ──────────────────────────────────────────────────────

def _ms_to_timestamp(ms: int) -> str:
    """Convert milliseconds to HH:MM:SS."""
    s = max(0, ms) // 1000
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _ms_to_timestamp_precise(ms: int) -> str:
    """Convert milliseconds to HH:MM:SS.mmm."""
    total_ms = max(0, ms)
    s, ms_part = divmod(total_ms, 1000)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms_part:03d}"


def _parse_time_to_ms(time_str: str) -> int:
    """Parse HH:MM:SS,mmm or HH:MM:SS.mmm to milliseconds."""
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


# ── 16:9 aspect ratio container ─────────────────────────────────

class _AspectRatioWidget(QWidget):
    """Container that maintains 16:9 aspect ratio for its child widget."""

    def __init__(self, child: QWidget, parent: QWidget = None):
        super().__init__(parent)
        self._child = child
        self._child.setParent(self)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w = self.width()
        h = self.height()
        # Target 16:9
        target_h = int(w * 9 / 16)
        if target_h <= h:
            # Width-constrained
            y_offset = (h - target_h) // 2
            self._child.setGeometry(0, y_offset, w, target_h)
        else:
            # Height-constrained
            target_w = int(h * 16 / 9)
            x_offset = (w - target_w) // 2
            self._child.setGeometry(x_offset, 0, target_w, h)

    def sizeHint(self):
        return QSize(480, 270)


# ── Subtitle overlay ────────────────────────────────────────────

class _SubtitleOverlay(QWidget):
    """Transparent overlay drawn on top of the video widget."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._source_text = ""
        self._translation_text = ""
        self._font_size = 16

    def set_texts(self, source: str, translation: str):
        self._source_text = source
        self._translation_text = translation
        self.update()

    def set_font_size(self, size: int):
        self._font_size = max(8, min(48, size))
        self.update()

    def paintEvent(self, event):
        if not self._source_text and not self._translation_text:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        margin = 12
        bg = QColor(0, 0, 0, 178)

        lines = []
        if self._source_text:
            lines.append((self._source_text, self._font_size - 2, QColor(180, 180, 180)))
        if self._translation_text:
            lines.append((self._translation_text, self._font_size, QColor(255, 255, 60)))

        total_h = 0
        metrics = []
        for text, size, color in lines:
            font = QFont()
            font.setPixelSize(size)
            font.setBold(True)
            p.setFont(font)
            fm = p.fontMetrics()
            br = fm.boundingRect(0, 0, w - 2 * margin, 0,
                                 Qt.AlignCenter | Qt.TextWordWrap, text)
            metrics.append((text, font, color, br))
            total_h += br.height() + 6

        y = h - total_h - margin - 10
        for text, font, color, br in metrics:
            rect_h = br.height() + 10
            # Draw shadow background
            p.fillRect(margin, int(y), w - 2 * margin, int(rect_h), bg)
            p.setFont(font)
            # Text shadow
            p.setPen(QColor(0, 0, 0, 200))
            p.drawText(margin + 1, int(y + 5 + 1), w - 2 * margin, int(rect_h - 10),
                        Qt.AlignCenter | Qt.TextWordWrap, text)
            # Text
            p.setPen(color)
            p.drawText(margin, int(y + 5), w - 2 * margin, int(rect_h - 10),
                        Qt.AlignCenter | Qt.TextWordWrap, text)
            y += rect_h + 2
        p.end()


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


# ── Main widget (inside dock) ──────────────────────────────────

class VideoPreviewWidget(QWidget):
    """Embedded video player for subtitle translation workflow."""

    # Emitted when user wants prev/next segment
    request_prev_segment = Signal()
    request_next_segment = Signal()
    # Emitted to request jumping to the subtitle entry at current playback time
    request_goto_current_time = Signal(int)  # position_ms

    _SPEEDS = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0]

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumSize(320, 220)

        # State
        self._video_path: Optional[Path] = None
        self._seg_start_ms = -1
        self._seg_end_ms = -1
        self._loop_enabled = False
        self._auto_pause = False
        self._subtitle_entries = []  # list of (start_ms, end_ms, source, translation)

        # ── Layout ──
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Video widget inside 16:9 aspect ratio container
        self._video_widget = QVideoWidget()
        self._video_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._subtitle_overlay = _SubtitleOverlay(self._video_widget)
        self._aspect_container = _AspectRatioWidget(self._video_widget, self)

        main_layout.addWidget(self._aspect_container, 1)

        # ── Slider row ──
        self._slider = _VideoSlider(Qt.Horizontal)
        self._slider.setRange(0, 0)
        self._slider.sliderMoved.connect(self._on_slider_seek)
        self._slider.setFixedHeight(18)
        main_layout.addWidget(self._slider)

        # ── Segment info row ──
        seg_row = QHBoxLayout()
        seg_row.setContentsMargins(6, 2, 6, 0)
        self._segment_label = QLabel("")
        self._segment_label.setStyleSheet(
            "font-family: Menlo, Consolas, monospace; font-size: 10px; color: #8899aa;"
        )
        seg_row.addWidget(self._segment_label)
        seg_row.addStretch()
        self._time_label = QLabel("00:00:00 / 00:00:00")
        self._time_label.setStyleSheet(
            "font-family: Menlo, Consolas, monospace; font-size: 11px;"
        )
        seg_row.addWidget(self._time_label)
        main_layout.addLayout(seg_row)

        # ── Transport controls ──
        controls = QHBoxLayout()
        controls.setContentsMargins(4, 4, 4, 4)
        controls.setSpacing(4)
        style = self.style()

        # Stop
        self._stop_btn = QPushButton()
        self._stop_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaStop))
        self._stop_btn.setFixedSize(28, 28)
        self._stop_btn.setToolTip(self.tr("Stop"))
        self._stop_btn.clicked.connect(self._stop)
        controls.addWidget(self._stop_btn)

        # Play/Pause
        self._play_btn = QPushButton()
        self._play_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self._play_btn.setFixedSize(28, 28)
        self._play_btn.setToolTip(self.tr("Play / Pause (Space)"))
        self._play_btn.clicked.connect(self._toggle_play)
        controls.addWidget(self._play_btn)

        # Frame step back
        self._step_back_btn = QPushButton("⏪")
        self._step_back_btn.setFixedSize(28, 28)
        self._step_back_btn.setToolTip(self.tr("Step back 1 second (Shift+Left)"))
        self._step_back_btn.clicked.connect(lambda: self._seek_relative(-1000))
        controls.addWidget(self._step_back_btn)

        # Frame step forward
        self._step_fwd_btn = QPushButton("⏩")
        self._step_fwd_btn.setFixedSize(28, 28)
        self._step_fwd_btn.setToolTip(self.tr("Step forward 1 second (Shift+Right)"))
        self._step_fwd_btn.clicked.connect(lambda: self._seek_relative(1000))
        controls.addWidget(self._step_fwd_btn)

        # Separator
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.VLine)
        sep1.setFixedHeight(20)
        controls.addWidget(sep1)

        # Go to current segment
        self._goto_seg_btn = QPushButton("⏎")
        self._goto_seg_btn.setFixedSize(28, 28)
        self._goto_seg_btn.setToolTip(self.tr("Go to current subtitle entry (G)"))
        self._goto_seg_btn.clicked.connect(self._goto_current_segment)
        controls.addWidget(self._goto_seg_btn)

        # Previous segment
        self._prev_btn = QPushButton("⏮")
        self._prev_btn.setFixedSize(28, 28)
        self._prev_btn.setToolTip(self.tr("Previous entry (Ctrl+Left)"))
        self._prev_btn.clicked.connect(self.request_prev_segment.emit)
        controls.addWidget(self._prev_btn)

        # Next segment
        self._next_btn = QPushButton("⏭")
        self._next_btn.setFixedSize(28, 28)
        self._next_btn.setToolTip(self.tr("Next entry (Ctrl+Right)"))
        self._next_btn.clicked.connect(self.request_next_segment.emit)
        controls.addWidget(self._next_btn)

        # Separator
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.VLine)
        sep2.setFixedHeight(20)
        controls.addWidget(sep2)

        # AB-repeat
        self._loop_btn = QPushButton("A⇄B")
        self._loop_btn.setFixedHeight(28)
        self._loop_btn.setCheckable(True)
        self._loop_btn.setToolTip(self.tr("Loop current segment (L)"))
        self._loop_btn.toggled.connect(self._on_loop_toggled)
        controls.addWidget(self._loop_btn)

        # Auto-pause
        self._auto_pause_cb = QCheckBox(self.tr("Auto-pause"))
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
        self._speed_combo.setFixedWidth(60)
        self._speed_combo.setToolTip(self.tr("Playback speed"))
        controls.addWidget(self._speed_combo)

        # Font size for subtitles
        self._font_up_btn = QPushButton("A+")
        self._font_up_btn.setFixedSize(28, 28)
        self._font_up_btn.setToolTip(self.tr("Increase subtitle font size"))
        self._font_up_btn.clicked.connect(lambda: self._change_font_size(2))
        controls.addWidget(self._font_up_btn)

        self._font_down_btn = QPushButton("A−")
        self._font_down_btn.setFixedSize(28, 28)
        self._font_down_btn.setToolTip(self.tr("Decrease subtitle font size"))
        self._font_down_btn.clicked.connect(lambda: self._change_font_size(-2))
        controls.addWidget(self._font_down_btn)

        main_layout.addLayout(controls)

        # ── Media player ──
        self._player = QMediaPlayer()
        self._audio = QAudioOutput()
        self._player.setAudioOutput(self._audio)
        self._player.setVideoOutput(self._video_widget)
        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.playbackStateChanged.connect(self._on_state_changed)

        # Subtitle sync timer — updates overlay based on playback position
        self._sub_timer = QTimer(self)
        self._sub_timer.setInterval(100)
        self._sub_timer.timeout.connect(self._update_subtitle_at_position)

        # ── Keyboard shortcuts ──
        self._setup_shortcuts()

    # ── Shortcuts ──

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

    # ── Public API ──

    def open_video(self, path: Path):
        """Load a video file."""
        self._video_path = path
        self._player.setSource(QUrl.fromLocalFile(str(path)))

    def set_subtitle_entries(self, entries: list):
        """Set all subtitle entries for time-synced overlay.
        
        entries: list of (start_ms, end_ms, source_text, translation_text)
        """
        self._subtitle_entries = entries

    def seek_to_time(self, time_str: str):
        """Seek to a timestamp like '00:01:23,456'."""
        ms = _parse_time_to_ms(time_str)
        if ms >= 0:
            self._player.setPosition(ms)
            if self._player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
                self._player.play()

    def seek_to_ms(self, ms: int):
        """Seek to a position in milliseconds."""
        self._player.setPosition(ms)
        if self._player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
            self._player.play()

    def set_segment(self, start_time: str, end_time: str, source: str, translation: str):
        """Set current segment for overlay, loop, and progress highlight."""
        self._seg_start_ms = _parse_time_to_ms(start_time)
        self._seg_end_ms = _parse_time_to_ms(end_time)
        self._slider.set_segment_range(self._seg_start_ms, self._seg_end_ms)
        self._subtitle_overlay.set_texts(source, translation)
        # Update segment info label
        duration_ms = self._seg_end_ms - self._seg_start_ms
        self._segment_label.setText(
            f"▶ {_ms_to_timestamp_precise(self._seg_start_ms)} → "
            f"{_ms_to_timestamp_precise(self._seg_end_ms)}  "
            f"({duration_ms / 1000:.1f}s)"
        )

    def show_subtitle(self, text: str):
        """Legacy: show single subtitle text."""
        self._subtitle_overlay.set_texts("", text)

    def set_subtitle_font_size(self, size: int):
        self._subtitle_overlay.set_font_size(size)

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
        """Stop playback and reset to beginning."""
        self._player.stop()
        self._player.setPosition(0)
        self._sub_timer.stop()
        self._subtitle_overlay.set_texts("", "")

    def _goto_current_segment(self):
        """Jump to the subtitle entry matching current playback position."""
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
        # AB-repeat
        if self._loop_enabled and self._seg_end_ms > 0 and position >= self._seg_end_ms:
            self._player.setPosition(self._seg_start_ms)
        # Auto-pause
        elif self._auto_pause and self._seg_end_ms > 0 and position >= self._seg_end_ms:
            self._player.pause()
            self._sub_timer.stop()

    def _update_subtitle_at_position(self):
        """Update subtitle overlay based on current playback position."""
        if not self._subtitle_entries:
            return
        pos = self._player.position()
        for start_ms, end_ms, source, translation in self._subtitle_entries:
            if start_ms <= pos <= end_ms:
                self._subtitle_overlay.set_texts(source, translation)
                return
        # No subtitle at current position — clear
        self._subtitle_overlay.set_texts("", "")

    def _on_duration_changed(self, duration: int):
        self._slider.setRange(0, duration)

    def _on_state_changed(self, state):
        style = self.style()
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self._play_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaPause))
            self._sub_timer.start()
        else:
            self._play_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
            if state == QMediaPlayer.PlaybackState.StoppedState:
                self._sub_timer.stop()

    def _on_loop_toggled(self, checked: bool):
        self._loop_enabled = checked
        self._loop_btn.setStyleSheet(
            "background-color: #3daee9; color: white;" if checked else ""
        )

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

    def _change_font_size(self, delta: int):
        """Adjust subtitle overlay font size."""
        current = self._subtitle_overlay._font_size
        self._subtitle_overlay.set_font_size(current + delta)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Overlay fills the video widget
        self._subtitle_overlay.setGeometry(
            0, 0, self._video_widget.width(), self._video_widget.height()
        )

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
        # Sensible minimum for 16:9 + controls
        self.setMinimumWidth(400)
        self.setMinimumHeight(300)

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
