"""Video Subtitle Extraction Dialog — extract and preview subtitles from video files.

Provides a dialog for:
- Opening video files and listing subtitle tracks
- Extracting subtitles to common formats (SRT, VTT, ASS)
- A preview player with basic playback controls
- FFmpeg missing: installation guidance dialog

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QFileDialog, QMessageBox, QGroupBox,
    QProgressBar, QProgressDialog, QSlider, QWidget, QDialogButtonBox,
    QApplication, QStyle,
)
from PySide6.QtCore import Qt, QUrl, QTimer, Signal
from PySide6.QtGui import QDesktopServices, QIcon

from linguaedit.services.ffmpeg import (
    is_ffmpeg_available, find_ffmpeg, get_subtitle_tracks,
    extract_subtitle, get_video_duration, SubtitleTrack,
    SUBTITLE_FORMATS, SUPPORTED_VIDEO_EXTENSIONS,
)


class FFmpegMissingDialog(QDialog):
    """Dialog shown when ffmpeg is not found on the system.

    Offers four actions:
    - Show installation instructions
    - Browse for ffmpeg binary
    - Retry detection
    - Cancel
    """

    ffmpeg_found = Signal(str)  # emits the path when located

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("FFmpeg Required"))
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)

        # Header
        header = QLabel(self.tr(
            "<h3>FFmpeg could not be found</h3>"
            "<p>LinguaEdit needs <b>ffmpeg</b> and <b>ffprobe</b> to "
            "extract subtitles from video files.</p>"
        ))
        header.setWordWrap(True)
        layout.addWidget(header)

        # Installation instructions
        info_group = QGroupBox(self.tr("Installation Instructions"))
        info_layout = QVBoxLayout(info_group)

        if sys.platform == "darwin":
            install_text = self.tr(
                "<b>macOS (Homebrew):</b><br>"
                "<code>brew install ffmpeg</code><br><br>"
                "<b>macOS (MacPorts):</b><br>"
                "<code>sudo port install ffmpeg</code>"
            )
        elif sys.platform == "win32":
            install_text = self.tr(
                "<b>Windows (winget):</b><br>"
                "<code>winget install FFmpeg</code><br><br>"
                "<b>Windows (Chocolatey):</b><br>"
                "<code>choco install ffmpeg</code><br><br>"
                "<b>Manual download:</b><br>"
                '<a href="https://ffmpeg.org/download.html">ffmpeg.org/download.html</a>'
            )
        else:
            install_text = self.tr(
                "<b>Ubuntu/Debian:</b><br>"
                "<code>sudo apt install ffmpeg</code><br><br>"
                "<b>Fedora:</b><br>"
                "<code>sudo dnf install ffmpeg</code><br><br>"
                "<b>Arch Linux:</b><br>"
                "<code>sudo pacman -S ffmpeg</code>"
            )

        info_label = QLabel(install_text)
        info_label.setWordWrap(True)
        info_label.setOpenExternalLinks(True)
        info_label.setTextFormat(Qt.RichText)
        info_layout.addWidget(info_label)
        layout.addWidget(info_group)

        # Action buttons
        btn_layout = QHBoxLayout()

        browse_btn = QPushButton(self.tr("Browse for ffmpeg…"))
        browse_btn.clicked.connect(self._on_browse)
        btn_layout.addWidget(browse_btn)

        retry_btn = QPushButton(self.tr("Retry"))
        retry_btn.clicked.connect(self._on_retry)
        btn_layout.addWidget(retry_btn)

        download_btn = QPushButton(self.tr("Open Download Page"))
        download_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://ffmpeg.org/download.html"))
        )
        btn_layout.addWidget(download_btn)

        btn_layout.addStretch()

        cancel_btn = QPushButton(self.tr("Cancel"))
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    def _on_browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, self.tr("Select ffmpeg binary"), "",
            self.tr("Executable files (*)"),
        )
        if path:
            # Validate it's actually ffmpeg
            import subprocess
            try:
                result = subprocess.run(
                    [path, "-version"], capture_output=True, text=True, timeout=5,
                )
                if "ffmpeg" in result.stdout.lower():
                    self.ffmpeg_found.emit(path)
                    self.accept()
                else:
                    QMessageBox.warning(
                        self, self.tr("Invalid File"),
                        self.tr("The selected file does not appear to be ffmpeg."),
                    )
            except Exception:
                QMessageBox.warning(
                    self, self.tr("Error"),
                    self.tr("Could not run the selected file."),
                )

    def _on_retry(self):
        if is_ffmpeg_available():
            self.ffmpeg_found.emit(find_ffmpeg())
            self.accept()
        else:
            QMessageBox.information(
                self, self.tr("Not Found"),
                self.tr("FFmpeg could still not be found in the system path."),
            )


class VideoSubtitleDialog(QDialog):
    """Main dialog for extracting subtitles from video files."""

    subtitle_extracted = Signal(str)  # emits the path to extracted subtitle file

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Extract Subtitles from Video"))
        self.setMinimumSize(600, 500)

        self._video_path: Optional[Path] = None
        self._tracks: list[SubtitleTrack] = []
        self._duration: float = 0.0

        layout = QVBoxLayout(self)

        # ── Video file selection ──
        file_group = QGroupBox(self.tr("Video File"))
        file_layout = QHBoxLayout(file_group)

        self._file_label = QLabel(self.tr("No file selected"))
        self._file_label.setStyleSheet("color: gray;")
        file_layout.addWidget(self._file_label, 1)

        browse_btn = QPushButton(self.tr("Browse…"))
        browse_btn.clicked.connect(self._on_browse_video)
        file_layout.addWidget(browse_btn)

        layout.addWidget(file_group)

        # ── Subtitle track selection ──
        track_group = QGroupBox(self.tr("Subtitle Tracks"))
        track_layout = QVBoxLayout(track_group)

        self._track_combo = QComboBox()
        self._track_combo.setEnabled(False)
        track_layout.addWidget(self._track_combo)

        self._track_info = QLabel("")
        self._track_info.setWordWrap(True)
        self._track_info.setStyleSheet("color: gray; font-size: 11px;")
        track_layout.addWidget(self._track_info)

        layout.addWidget(track_group)

        # ── Output format ──
        format_group = QGroupBox(self.tr("Output Format"))
        format_layout = QHBoxLayout(format_group)

        format_layout.addWidget(QLabel(self.tr("Format:")))
        self._format_combo = QComboBox()
        self._format_combo.addItem("SRT (.srt)", ".srt")
        self._format_combo.addItem("WebVTT (.vtt)", ".vtt")
        self._format_combo.addItem("ASS/SSA (.ass)", ".ass")
        format_layout.addWidget(self._format_combo)
        format_layout.addStretch()

        layout.addWidget(format_group)

        # ── Preview area ──
        preview_group = QGroupBox(self.tr("Preview"))
        preview_layout = QVBoxLayout(preview_group)

        # Preview text area
        self._preview_label = QLabel(self.tr("Select a video file to preview subtitles"))
        self._preview_label.setWordWrap(True)
        self._preview_label.setAlignment(Qt.AlignTop)
        self._preview_label.setMinimumHeight(120)
        self._preview_label.setStyleSheet(
            "QLabel { background: palette(base); border: 1px solid palette(mid); "
            "padding: 8px; font-family: Menlo, Courier New, monospace; }"
        )
        preview_layout.addWidget(self._preview_label)

        # Playback controls
        controls = QHBoxLayout()

        style = self.style()
        self._play_btn = QPushButton()
        self._play_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self._play_btn.setToolTip(self.tr("Play / Pause"))
        self._play_btn.setEnabled(False)
        self._play_btn.clicked.connect(self._on_play_pause)
        controls.addWidget(self._play_btn)

        self._stop_btn = QPushButton()
        self._stop_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaStop))
        self._stop_btn.setToolTip(self.tr("Stop"))
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._on_stop)
        controls.addWidget(self._stop_btn)

        self._time_slider = QSlider(Qt.Horizontal)
        self._time_slider.setEnabled(False)
        self._time_slider.setRange(0, 1000)
        self._time_slider.valueChanged.connect(self._on_slider_changed)
        controls.addWidget(self._time_slider, 1)

        self._time_label = QLabel("00:00:00 / 00:00:00")
        controls.addWidget(self._time_label)

        preview_layout.addLayout(controls)
        layout.addWidget(preview_group)

        # ── Progress ──
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        # ── Buttons ──
        btn_layout = QHBoxLayout()

        self._extract_btn = QPushButton(self.tr("Extract and Open"))
        self._extract_btn.setEnabled(False)
        self._extract_btn.clicked.connect(self._on_extract)
        btn_layout.addWidget(self._extract_btn)

        self._save_btn = QPushButton(self.tr("Extract and Save As…"))
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._on_save_as)
        btn_layout.addWidget(self._save_btn)

        btn_layout.addStretch()

        cancel_btn = QPushButton(self.tr("Close"))
        cancel_btn.clicked.connect(self.close)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

        # Playback timer
        self._playback_timer = QTimer()
        self._playback_timer.setInterval(100)
        self._playback_timer.timeout.connect(self._on_playback_tick)
        self._playback_position = 0.0
        self._is_playing = False
        self._extracted_entries: list = []

    def open_video(self, path: Path):
        """Programmatically open a video file (called from main window)."""
        if not is_ffmpeg_available():
            dlg = FFmpegMissingDialog(self)
            if dlg.exec() != QDialog.Accepted:
                return
        self._video_path = path
        self._load_video_tracks()

    def _on_browse_video(self):
        """Open file dialog for video selection."""
        # Check ffmpeg first
        if not is_ffmpeg_available():
            dlg = FFmpegMissingDialog(self)
            if dlg.exec() != QDialog.Accepted:
                return

        exts = " ".join(f"*{ext}" for ext in sorted(SUPPORTED_VIDEO_EXTENSIONS))
        path, _ = QFileDialog.getOpenFileName(
            self, self.tr("Select Video File"), "",
            self.tr("Video files (%s);;All files (*)") % exts,
        )
        if not path:
            return

        self._video_path = Path(path)
        self._load_video_tracks()

    def _load_video_tracks(self):
        self._file_label.setText(self._video_path.name)
        self._file_label.setStyleSheet("")

        try:
            self._tracks = get_subtitle_tracks(self._video_path)
            self._duration = get_video_duration(self._video_path)
        except Exception as e:
            QMessageBox.critical(
                self, self.tr("Error"),
                self.tr("Could not read the video file:\n%s") % str(e),
            )
            return

        self._track_combo.clear()
        if not self._tracks:
            self._track_combo.addItem(self.tr("No subtitle tracks found"))
            self._track_combo.setEnabled(False)
            self._extract_btn.setEnabled(False)
            self._save_btn.setEnabled(False)
            self._track_info.setText(self.tr(
                "This video file contains no embedded subtitle tracks."
            ))
            return

        for track in self._tracks:
            self._track_combo.addItem(track.display_label, track.index)

        self._track_combo.setEnabled(True)
        self._extract_btn.setEnabled(True)
        self._save_btn.setEnabled(True)
        self._track_info.setText(
            self.tr("%d subtitle tracks found. Duration: %s") % (
                len(self._tracks),
                self._format_time(self._duration),
            )
        )

        # Auto-extract first track for preview
        self._preview_track(0)

    def _preview_track(self, track_index: int):
        """Extract track to temp file and show preview with progress."""
        if not self._video_path or track_index >= len(self._tracks):
            return

        track = self._tracks[track_index]

        progress_dlg = QProgressDialog(
            self.tr("Extracting preview…"),
            self.tr("Cancel"),
            0, 100,
            self,
        )
        progress_dlg.setWindowTitle(self.tr("Extracting"))
        progress_dlg.setWindowModality(Qt.WindowModal)
        progress_dlg.setMinimumDuration(0)
        progress_dlg.setValue(0)
        self._preview_cancelled = False

        def _on_cancel():
            self._preview_cancelled = True

        progress_dlg.canceled.connect(_on_cancel)

        def _on_progress(pct: float):
            if self._preview_cancelled:
                return
            progress_dlg.setValue(int(pct * 100))
            QApplication.processEvents()

        try:
            tmp = tempfile.NamedTemporaryFile(suffix=".srt", delete=False)
            tmp.close()
            extract_subtitle(
                self._video_path, track, Path(tmp.name), ".srt",
                progress_callback=_on_progress,
                duration=self._duration,
            )
            progress_dlg.setValue(100)
            progress_dlg.close()

            if self._preview_cancelled:
                return

            content = Path(tmp.name).read_text("utf-8", errors="replace")
            lines = content.strip().split("\n")
            preview_lines = lines[:30]
            preview = "\n".join(preview_lines)
            if len(lines) > 30:
                preview += f"\n\n… ({len(lines)} lines total)"
            self._preview_label.setText(preview)

            # Parse entries for playback simulation
            self._extracted_entries = self._parse_srt_for_preview(content)
            self._play_btn.setEnabled(True)
            self._stop_btn.setEnabled(True)
            self._time_slider.setEnabled(True)

        except RuntimeError as e:
            progress_dlg.close()
            QMessageBox.warning(
                self, self.tr("Extraction Error"),
                self.tr("Could not extract the subtitle:\n%s") % str(e),
            )
            self._preview_label.setText(self.tr("Preview failed: %s") % str(e))
        except Exception as e:
            progress_dlg.close()
            self._preview_label.setText(self.tr("Preview failed: %s") % str(e))

    def _parse_srt_for_preview(self, content: str) -> list:
        """Parse SRT content for timeline preview."""
        import re
        entries = []
        blocks = re.split(r'\n\s*\n', content.strip())
        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) < 3:
                continue
            timing = re.match(
                r'(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})',
                lines[1].strip(),
            )
            if timing:
                g = timing.groups()
                start = int(g[0]) * 3600 + int(g[1]) * 60 + int(g[2]) + int(g[3]) / 1000
                end = int(g[4]) * 3600 + int(g[5]) * 60 + int(g[6]) + int(g[7]) / 1000
                text = '\n'.join(lines[2:])
                entries.append((start, end, text))
        return entries

    def _on_play_pause(self):
        """Toggle playback simulation."""
        if self._is_playing:
            self._playback_timer.stop()
            self._is_playing = False
            self._play_btn.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
            )
        else:
            self._playback_timer.start()
            self._is_playing = True
            self._play_btn.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause)
            )

    def _on_stop(self):
        """Stop playback simulation."""
        self._playback_timer.stop()
        self._is_playing = False
        self._playback_position = 0.0
        self._play_btn.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        )
        self._time_slider.setValue(0)
        self._update_preview_at_time(0.0)

    def _on_playback_tick(self):
        """Advance playback position."""
        self._playback_position += 0.1
        if self._duration > 0 and self._playback_position > self._duration:
            self._on_stop()
            return

        if self._duration > 0:
            slider_val = int((self._playback_position / self._duration) * 1000)
            self._time_slider.blockSignals(True)
            self._time_slider.setValue(slider_val)
            self._time_slider.blockSignals(False)

        self._update_preview_at_time(self._playback_position)

    def _on_slider_changed(self, value: int):
        """Handle manual slider movement."""
        if self._duration > 0:
            self._playback_position = (value / 1000.0) * self._duration
            self._update_preview_at_time(self._playback_position)

    def _update_preview_at_time(self, time_sec: float):
        """Show the subtitle text active at the given time."""
        self._time_label.setText(
            f"{self._format_time(time_sec)} / {self._format_time(self._duration)}"
        )

        active_text = ""
        for start, end, text in self._extracted_entries:
            if start <= time_sec <= end:
                active_text = text
                break

        if active_text:
            self._preview_label.setText(
                f'<div style="text-align:center; font-size:16px; padding:20px;">'
                f'{active_text}</div>'
            )
            self._preview_label.setTextFormat(Qt.RichText)
        else:
            self._preview_label.setText("")

    def _on_extract(self):
        """Extract subtitle and signal to open in editor."""
        result_path = self._do_extract()
        if result_path:
            self.subtitle_extracted.emit(str(result_path))
            self.accept()

    def _on_save_as(self):
        """Extract subtitle and save to user-chosen location."""
        fmt = self._format_combo.currentData()
        ext_filter = {
            ".srt": "SubRip (*.srt)",
            ".vtt": "WebVTT (*.vtt)",
            ".ass": "Advanced SubStation Alpha (*.ass)",
        }.get(fmt, "Subtitle files (*.*)")

        save_path, _ = QFileDialog.getSaveFileName(
            self, self.tr("Save Subtitle As"), "", ext_filter,
        )
        if save_path:
            result = self._do_extract(Path(save_path))
            if result:
                QMessageBox.information(
                    self, self.tr("Done"),
                    self.tr("The subtitle has been saved to:\n%s") % str(result),
                )

    def _do_extract(self, output_path: Optional[Path] = None) -> Optional[Path]:
        """Perform the actual extraction with progress feedback."""
        if not self._video_path or not self._tracks:
            return None

        track_idx = self._track_combo.currentData()
        if track_idx is None:
            return None

        track = self._tracks[track_idx]
        fmt = self._format_combo.currentData()

        if output_path is None:
            output_path = self._video_path.with_suffix(fmt)

        progress_dlg = QProgressDialog(
            self.tr("Extracting subtitles…"),
            self.tr("Cancel"),
            0, 100,
            self,
        )
        progress_dlg.setWindowTitle(self.tr("Extracting"))
        progress_dlg.setWindowModality(Qt.WindowModal)
        progress_dlg.setMinimumDuration(0)
        progress_dlg.setValue(0)
        self._extract_cancelled = False

        def _on_cancel():
            self._extract_cancelled = True

        progress_dlg.canceled.connect(_on_cancel)

        def _on_progress(pct: float):
            if self._extract_cancelled:
                return
            progress_dlg.setValue(int(pct * 100))
            QApplication.processEvents()

        try:
            result = extract_subtitle(
                self._video_path, track, output_path, fmt,
                progress_callback=_on_progress,
                duration=self._duration,
            )
            progress_dlg.setValue(100)
            progress_dlg.close()
            return result
        except Exception as e:
            progress_dlg.close()
            QMessageBox.critical(
                self, self.tr("Extraction Error"),
                self.tr("Could not extract the subtitle:\n%s") % str(e),
            )
            return None

    @staticmethod
    def _format_time(seconds: float) -> str:
        """Format seconds as HH:MM:SS."""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"
