"""FFmpeg integration — extract subtitle tracks from video files.

Provides detection of ffmpeg/ffprobe, subtitle track enumeration,
and extraction to common subtitle formats (SRT, VTT, ASS/SSA, SUB).

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


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


def find_ffmpeg() -> Optional[str]:
    """Return the absolute path to ffmpeg, or *None* if not found."""
    return shutil.which("ffmpeg")


def find_ffprobe() -> Optional[str]:
    """Return the absolute path to ffprobe, or *None* if not found."""
    return shutil.which("ffprobe")


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

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
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
) -> Path:
    """Extract a single subtitle track to *output_path*.

    *output_format* should be one of the keys in ``SUBTITLE_FORMATS``
    (e.g. ``".srt"``, ``".vtt"``).
    """
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found")

    codec = SUBTITLE_FORMATS.get(output_format, "srt")

    cmd = [
        ffmpeg,
        "-y",
        "-i", str(video_path),
        "-map", f"0:{track.stream_index}",
        "-c:s", codec,
        str(output_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
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

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr.strip()}")

    data = json.loads(result.stdout)
    return float(data.get("format", {}).get("duration", 0))
