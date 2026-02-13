"""FFmpeg integration — extract subtitle tracks from video files.

Provides detection of ffmpeg/ffprobe, subtitle track enumeration,
and extraction to common subtitle formats (SRT, VTT, ASS/SSA, SUB).

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import json
import os
import sys
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


def _get_subprocess_kwargs() -> dict:
    """Return platform-specific kwargs to hide console windows on Windows."""
    kwargs: dict = {}
    if sys.platform == "win32":
        # CREATE_NO_WINDOW = 0x08000000
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0  # SW_HIDE
        kwargs["startupinfo"] = si
        kwargs["creationflags"] = 0x08000000
    return kwargs


@dataclass
class SubtitleTrack:
    """Metadata for a single subtitle stream inside a video container."""
    index: int
    stream_index: int
    codec_name: str
    language: str
    title: str
    forced: bool = False
    default: bool = False

    @property
    def display_label(self) -> str:
        parts: list[str] = []
        if self.title:
            parts.append(self.title)
        if self.language:
            parts.append(f"[{self.language}]")
        parts.append(f"({self.codec_name})")
        if self.default:
            parts.append("*default*")
        if self.forced:
            parts.append("*forced*")
        return " ".join(parts) or f"Track {self.index}"


# Supported output formats and their ffmpeg codec names
SUBTITLE_FORMATS = {
    ".srt": "srt",
    ".vtt": "webvtt",
    ".ass": "ass",
    ".ssa": "ass",
    ".sub": "subrip",
}

SUPPORTED_VIDEO_EXTENSIONS = {
    ".mkv", ".mp4", ".avi", ".mov", ".webm", ".ts", ".m2ts",
    ".flv", ".wmv", ".ogv", ".mpg", ".mpeg", ".3gp",
}


def _find_on_path_or_common(name: str) -> Optional[str]:
    """Find executable on PATH, falling back to common install locations on Windows."""
    found = shutil.which(name)
    if found:
        return found
    if sys.platform == "win32":
        # Common Windows install locations for ffmpeg
        for base in [
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\ffmpeg\bin"),
            os.path.expandvars(r"%ProgramFiles%\ffmpeg\bin"),
            os.path.expandvars(r"%ProgramFiles(x86)%\ffmpeg\bin"),
            r"C:\ffmpeg\bin",
            os.path.expandvars(r"%USERPROFILE%\scoop\shims"),
            os.path.expandvars(r"%ChocolateyInstall%\bin"),
        ]:
            candidate = os.path.join(base, f"{name}.exe")
            if os.path.isfile(candidate):
                return candidate
    return None


def find_ffmpeg() -> Optional[str]:
    """Return the absolute path to ffmpeg, or *None* if not found."""
    return _find_on_path_or_common("ffmpeg")


def find_ffprobe() -> Optional[str]:
    """Return the absolute path to ffprobe, or *None* if not found."""
    return _find_on_path_or_common("ffprobe")


def is_ffmpeg_available() -> bool:
    """Check whether both ffmpeg and ffprobe are on PATH."""
    return find_ffmpeg() is not None and find_ffprobe() is not None


def get_subtitle_tracks(video_path: Path) -> List[SubtitleTrack]:
    """Probe *video_path* and return a list of subtitle streams."""
    ffprobe = find_ffprobe()
    if not ffprobe:
        raise RuntimeError("ffprobe not found")

    cmd = [
        ffprobe,
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        "-select_streams", "s",
        str(video_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, **_get_subprocess_kwargs())
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr.strip()}")

    data = json.loads(result.stdout)
    tracks: list[SubtitleTrack] = []

    for stream in data.get("streams", []):
        tags = stream.get("tags", {})
        disposition = stream.get("disposition", {})
        tracks.append(SubtitleTrack(
            index=len(tracks),
            stream_index=stream.get("index", 0),
            codec_name=stream.get("codec_name", "unknown"),
            language=tags.get("language", ""),
            title=tags.get("title", ""),
            forced=bool(disposition.get("forced", 0)),
            default=bool(disposition.get("default", 0)),
        ))

    return tracks


def extract_subtitle(
    video_path: Path,
    track: SubtitleTrack,
    output_path: Path,
    output_format: str = ".srt",
    progress_callback: Optional[callable] = None,
    duration: float = 0.0,
) -> Path:
    """Extract a single subtitle track to *output_path*.

    *output_format* should be one of the keys in ``SUBTITLE_FORMATS``
    (e.g. ``".srt"``, ``".vtt"``).

    If *progress_callback* is provided, it is called with a float 0.0–1.0
    representing extraction progress. *duration* (seconds) is needed for
    progress calculation.
    """
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found")

    codec = SUBTITLE_FORMATS.get(output_format, "srt")

    cmd = [
        ffmpeg,
        "-y",
        "-progress", "pipe:1",
        "-i", str(video_path),
        "-map", f"0:{track.stream_index}",
        "-c:s", codec,
        str(output_path),
    ]

    if progress_callback and duration > 0:
        import re as _re
        import threading

        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            **_get_subprocess_kwargs(),
        )

        # Read stderr in background thread to prevent pipe deadlock on Windows
        stderr_lines: list[str] = []

        def _drain_stderr():
            try:
                for line in proc.stderr:
                    stderr_lines.append(line)
            except Exception:
                pass

        t = threading.Thread(target=_drain_stderr, daemon=True)
        t.start()

        for line in proc.stdout:
            m = _re.match(r'out_time_ms=(\d+)', line.strip())
            if m:
                current_ms = int(m.group(1))
                pct = min(current_ms / (duration * 1_000_000), 1.0)
                progress_callback(pct)
        try:
            proc.wait(timeout=300)
        except subprocess.TimeoutExpired:
            proc.kill()
            raise RuntimeError("ffmpeg extraction timed out after 300 seconds")
        t.join(timeout=5)
        if proc.returncode != 0:
            stderr = "".join(stderr_lines)
            raise RuntimeError(f"ffmpeg extraction failed: {stderr.strip()}")
    else:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, **_get_subprocess_kwargs())
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg extraction failed: {result.stderr.strip()}")

    return output_path


def get_video_duration(video_path: Path) -> float:
    """Return the duration of the video in seconds."""
    ffprobe = find_ffprobe()
    if not ffprobe:
        raise RuntimeError("ffprobe not found")

    cmd = [
        ffprobe,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        str(video_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, **_get_subprocess_kwargs())
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr.strip()}")

    data = json.loads(result.stdout)
    return float(data.get("format", {}).get("duration", 0))
