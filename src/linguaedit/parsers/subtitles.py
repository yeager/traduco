"""Subtitle parser — hantera SRT/VTT undertextfiler."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any, Union


@dataclass
class SubtitleEntry:
    """En enskild undertext."""
    index: int
    start_time: str
    end_time: str
    text: str
    translation: str = ""  # Översättning av undertexten
    fuzzy: bool = False    # Needs review / fuzzy flag
    cue_settings: str = ""  # För VTT
    note: str = ""  # För NOTE-kommentarer i VTT
    line_number: int = 0

    @property
    def timestamp(self) -> str:
        """Return formatted timestamp interval."""
        return f"{self.start_time} --> {self.end_time}"


@dataclass
class SubtitleFileData:
    """Subtitle fildata."""
    path: Path
    format: str  # "srt" eller "vtt"
    entries: List[SubtitleEntry] = field(default_factory=list)
    encoding: str = "utf-8"
    header: str = ""  # VTT header
    styles: List[str] = field(default_factory=list)  # VTT STYLE blocks
    notes: List[str] = field(default_factory=list)  # VTT NOTE blocks

    @property
    def total_count(self) -> int:
        return len(self.entries)

    @property
    def translated_count(self) -> int:
        return sum(1 for e in self.entries if e.translation)

    @property
    def untranslated_count(self) -> int:
        return sum(1 for e in self.entries if not e.translation)

    @property
    def percent_translated(self) -> float:
        if not self.entries:
            return 100.0
        return round(self.translated_count / len(self.entries) * 100, 1)


def _parse_timestamp_srt(timestamp: str) -> str:
    """Parsa SRT timestamp format (HH:MM:SS,mmm)."""
    return timestamp.replace(',', '.')


def _parse_timestamp_vtt(timestamp: str) -> str:
    """Parsa VTT timestamp format (HH:MM:SS.mmm)."""
    return timestamp


def _format_timestamp_srt(timestamp: str) -> str:
    """Formatera till SRT timestamp format."""
    return timestamp.replace('.', ',')


def _format_timestamp_vtt(timestamp: str) -> str:
    """Formatera till VTT timestamp format."""
    return timestamp


def _parse_srt_content(content: str) -> SubtitleFileData:
    """Parsa SRT-innehåll."""
    entries = []
    blocks = re.split(r'\n\s*\n', content.strip())
    
    for block_num, block in enumerate(blocks):
        if not block.strip():
            continue
            
        lines = block.strip().split('\n')
        if len(lines) < 3:
            continue
            
        try:
            # Index (första raden)
            index = int(lines[0].strip())
            
            # Timing (andra raden)
            timing_line = lines[1].strip()
            timing_match = re.match(r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})', timing_line)
            
            if not timing_match:
                continue
                
            start_time = _parse_timestamp_srt(timing_match.group(1))
            end_time = _parse_timestamp_srt(timing_match.group(2))
            
            # Text (resterande rader)
            text = '\n'.join(lines[2:])
            
            entry = SubtitleEntry(
                index=index,
                start_time=start_time,
                end_time=end_time,
                text=text,
                line_number=block_num + 1
            )
            entries.append(entry)
            
        except (ValueError, IndexError):
            continue
    
    return SubtitleFileData(
        path=Path(),
        format="srt",
        entries=entries
    )


def _parse_vtt_content(content: str) -> SubtitleFileData:
    """Parsa VTT-innehåll."""
    lines = content.split('\n')
    entries = []
    styles = []
    notes = []
    header = ""
    
    # Kontrollera VTT header
    if not lines or not lines[0].startswith('WEBVTT'):
        raise ValueError("Invalid VTT file: missing WEBVTT header")
    
    header = lines[0]
    
    i = 1
    while i < len(lines):
        line = lines[i].strip()
        
        # Skip tomma rader
        if not line:
            i += 1
            continue
        
        # STYLE block
        if line == 'STYLE':
            i += 1
            style_lines = []
            while i < len(lines) and lines[i].strip():
                style_lines.append(lines[i])
                i += 1
            styles.append('\n'.join(style_lines))
            continue
        
        # NOTE block
        if line.startswith('NOTE'):
            note_text = line[4:].strip()
            i += 1
            while i < len(lines) and lines[i].strip():
                note_text += '\n' + lines[i].strip()
                i += 1
            notes.append(note_text)
            continue
        
        # Cue (subtitle entry)
        # Kolla om raden innehåller timing
        timing_match = re.search(r'(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})', line)
        
        if timing_match:
            # Timing rad
            start_time = timing_match.group(1)
            end_time = timing_match.group(2)
            
            # Cue settings (efter timing)
            cue_settings = line[timing_match.end():].strip()
            
            # Cue ID (föregående rad om den inte innehöll timing)
            cue_id = ""
            if i > 1 and not re.search(r'\d{2}:\d{2}:\d{2}\.\d{3}', lines[i-1]):
                cue_id = lines[i-1].strip()
            
            # Text (följande rader tills tom rad)
            i += 1
            text_lines = []
            while i < len(lines) and lines[i].strip():
                text_lines.append(lines[i])
                i += 1
            
            text = '\n'.join(text_lines)
            
            # Använd entry index baserat på position
            index = len(entries) + 1
            
            entry = SubtitleEntry(
                index=index,
                start_time=start_time,
                end_time=end_time,
                text=text,
                cue_settings=cue_settings,
                line_number=i
            )
            entries.append(entry)
        
        i += 1
    
    return SubtitleFileData(
        path=Path(),
        format="vtt",
        entries=entries,
        header=header,
        styles=styles,
        notes=notes
    )


def parse_subtitles(path: Union[str, Path]) -> SubtitleFileData:
    """Parsa subtitle-fil (SRT eller VTT)."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    
    # Detektera format baserat på filändelse
    format_type = "vtt" if path.suffix.lower() == ".vtt" else "srt"
    
    # Läs fil med encoding-detektion
    content = ""
    encoding = "utf-8"
    
    for enc in ["utf-8", "utf-8-sig", "latin1", "cp1252"]:
        try:
            content = path.read_text(encoding=enc)
            encoding = enc
            break
        except UnicodeDecodeError:
            continue
    
    if not content:
        raise ValueError(f"Could not decode file: {path}")
    
    # Parsa baserat på format
    if format_type == "vtt":
        file_data = _parse_vtt_content(content)
    else:
        file_data = _parse_srt_content(content)
    
    file_data.path = Path(path) if not isinstance(path, Path) else path
    file_data.encoding = encoding
    
    return file_data


def save_subtitles(file_data: SubtitleFileData, path: Optional[Path] = None) -> None:
    """Spara subtitle-fil."""
    if path:
        file_data.path = Path(path) if not isinstance(path, Path) else path
    
    if file_data.format == "vtt":
        _save_vtt(file_data)
    else:
        _save_srt(file_data)


def _save_srt(file_data: SubtitleFileData) -> None:
    """Spara SRT-format."""
    lines = []
    
    for entry in file_data.entries:
        # Write translation if available, otherwise source text
        text = entry.translation or entry.text or ""
        
        # Index
        lines.append(str(entry.index))
        
        # Timing
        start = _format_timestamp_srt(entry.start_time)
        end = _format_timestamp_srt(entry.end_time)
        lines.append(f"{start} --> {end}")
        
        lines.append(text)
        lines.append("")  # Tom rad mellan entries
    
    content = '\n'.join(lines)
    file_data.path.write_text(content, encoding=file_data.encoding)


def _save_vtt(file_data: SubtitleFileData) -> None:
    """Spara VTT-format."""
    lines = []
    
    # Header
    lines.append(file_data.header or "WEBVTT")
    lines.append("")
    
    # Styles
    for style in file_data.styles:
        lines.append("STYLE")
        lines.append(style)
        lines.append("")
    
    # Notes
    for note in file_data.notes:
        lines.append(f"NOTE {note}")
        lines.append("")
    
    # Cues
    for entry in file_data.entries:
        # Timing med cue settings
        timing_line = f"{entry.start_time} --> {entry.end_time}"
        if entry.cue_settings:
            timing_line += f" {entry.cue_settings}"
        lines.append(timing_line)
        
        # Write translation if available, otherwise source text
        text = entry.translation or entry.text or ""
        lines.append(text)
        lines.append("")  # Tom rad mellan cues
    
    content = '\n'.join(lines)
    file_data.path.write_text(content, encoding=file_data.encoding)