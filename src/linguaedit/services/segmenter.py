"""Text segmentation service — split and merge translation entries."""

from __future__ import annotations

import re
from typing import List, Tuple


class TextSegmenter:
    """Service for segmenting long strings at sentence boundaries."""
    
    # Sentence boundary patterns
    SENTENCE_ENDINGS = re.compile(r'[.!?]+(?:\s+|$)')
    
    # Common abbreviations that shouldn't trigger splits
    ABBREVIATIONS = {
        'en': {
            'mr.', 'mrs.', 'ms.', 'dr.', 'prof.', 'inc.', 'ltd.', 'corp.',
            'co.', 'vs.', 'etc.', 'e.g.', 'i.e.', 'cf.', 'n.b.', 'p.s.',
            'a.m.', 'p.m.', 'b.c.', 'a.d.', 'u.s.', 'u.k.', 'u.s.a.',
        },
        'sv': {
            'dr.', 'prof.', 'ab.', 'kb.', 'bl.a.', 'dvs.', 't.ex.', 'osv.',
            'o.s.v.', 'ca.', 'ca', 'kr.', 'st.', 'kl.', 'nr.', 'm.m.',
        },
        'de': {
            'dr.', 'prof.', 'gmbh.', 'z.b.', 'bzw.', 'usw.', 'd.h.', 'etc.',
            'ca.', 'u.a.', 'o.ä.', 'v.chr.', 'n.chr.', 'mrd.', 'mio.',
        },
        'fr': {
            'dr.', 'prof.', 'm.', 'mme.', 'mlle.', 'etc.', 'ex.', 'cf.',
            'p.ex.', 'c.-à-d.', 'av.', 'ap.', 'j.-c.', 'n.b.', 'p.s.',
        },
        'es': {
            'dr.', 'dra.', 'prof.', 'sra.', 'sr.', 'srta.', 'etc.', 'ej.',
            'p.ej.', 'vs.', 'cía.', 's.a.', 'ltd.', 'n.b.', 'p.d.',
        },
    }
    
    @classmethod
    def split_at_sentences(cls, text: str, language: str = 'en') -> List[str]:
        """Split text at sentence boundaries, respecting abbreviations.
        
        Args:
            text: The text to split
            language: Language code for abbreviation detection
            
        Returns:
            List of sentences/segments
        """
        if not text.strip():
            return [text]
        
        # Get abbreviations for language
        abbrevs = cls.ABBREVIATIONS.get(language.lower(), cls.ABBREVIATIONS['en'])
        
        segments = []
        current_segment = ""
        
        # Split on potential sentence boundaries
        parts = cls.SENTENCE_ENDINGS.split(text)
        delimiters = cls.SENTENCE_ENDINGS.findall(text)
        
        for i, part in enumerate(parts):
            current_segment += part
            
            # Add delimiter if available
            if i < len(delimiters):
                delimiter = delimiters[i]
                current_segment += delimiter
                
                # Check if this is really a sentence boundary
                if cls._is_sentence_boundary(current_segment, abbrevs):
                    segments.append(current_segment.strip())
                    current_segment = ""
        
        # Add remaining text
        if current_segment.strip():
            segments.append(current_segment.strip())
        
        # Remove empty segments
        return [seg for seg in segments if seg.strip()]
    
    @classmethod
    def _is_sentence_boundary(cls, text: str, abbreviations: set) -> bool:
        """Check if the end of text represents a real sentence boundary."""
        # Trim whitespace and get last few words
        text = text.strip()
        if not text:
            return False
        
        # Look for abbreviations at the end
        words = text.lower().split()
        if len(words) >= 2:
            last_word = words[-2]  # Word before the delimiter
            if any(last_word.endswith(abbr.rstrip('.')) for abbr in abbreviations):
                return False
        
        # If text is very short, probably not a real sentence boundary
        if len(text.strip()) < 10:
            return False
        
        return True
    
    @classmethod
    def can_merge_segments(cls, segment1: str, segment2: str) -> bool:
        """Check if two segments can be safely merged."""
        # Don't merge if either is empty
        if not segment1.strip() or not segment2.strip():
            return False
        
        # Don't merge very long segments
        combined_length = len(segment1) + len(segment2)
        if combined_length > 1000:  # Arbitrary limit
            return False
        
        # Don't merge if first segment doesn't end with sentence punctuation
        first_trimmed = segment1.rstrip()
        if not first_trimmed or first_trimmed[-1] not in '.!?':
            return True  # These probably should be merged
        
        return True
    
    @classmethod
    def merge_segments(cls, segments: List[str]) -> str:
        """Merge a list of segments into a single string."""
        if not segments:
            return ""
        
        result = []
        for i, segment in enumerate(segments):
            segment = segment.strip()
            if not segment:
                continue
            
            if i == 0:
                result.append(segment)
            else:
                # Add appropriate spacing
                if result and not result[-1].endswith(' '):
                    result.append(' ')
                result.append(segment)
        
        return ''.join(result)
    
    @classmethod
    def suggest_split_points(cls, text: str, language: str = 'en') -> List[int]:
        """Suggest character positions where text could be split.
        
        Returns list of character indices after which splitting would make sense.
        """
        split_points = []
        
        # Find all sentence endings
        for match in cls.SENTENCE_ENDINGS.finditer(text):
            end_pos = match.end()
            # Don't suggest splits at the very end
            if end_pos < len(text) - 1:
                split_points.append(end_pos - 1)
        
        # Also suggest splits at paragraph breaks
        for match in re.finditer(r'\n\s*\n', text):
            split_points.append(match.start())
        
        # Remove duplicates and sort
        return sorted(set(split_points))
    
    @classmethod
    def is_suitable_for_splitting(cls, text: str, min_length: int = 100) -> bool:
        """Check if text is long enough and suitable for splitting."""
        if len(text) < min_length:
            return False
        
        # Check if text contains multiple sentences
        sentence_count = len(cls.SENTENCE_ENDINGS.findall(text))
        return sentence_count >= 2


class EntrySegmenter:
    """High-level interface for segmenting translation entries."""
    
    @staticmethod
    def split_entry(source_text: str, target_text: str, 
                   source_lang: str = 'en', target_lang: str = 'sv') -> List[Tuple[str, str]]:
        """Split a translation entry into multiple entries.
        
        Returns list of (source, target) tuples.
        """
        # Split source text
        source_segments = TextSegmenter.split_at_sentences(source_text, source_lang)
        
        # If source doesn't split well, return original
        if len(source_segments) <= 1:
            return [(source_text, target_text)]
        
        # Split target text
        target_segments = TextSegmenter.split_at_sentences(target_text, target_lang)
        
        # Try to align source and target segments
        # Simple approach: if same number of segments, pair them up
        if len(source_segments) == len(target_segments):
            return list(zip(source_segments, target_segments))
        
        # If different numbers, try to distribute target over source
        result = []
        target_index = 0
        
        for i, source_seg in enumerate(source_segments):
            if target_index < len(target_segments):
                target_seg = target_segments[target_index]
                target_index += 1
            else:
                # No more target segments, use empty string
                target_seg = ""
            
            result.append((source_seg, target_seg))
        
        # Add any remaining target segments as new entries with empty source
        while target_index < len(target_segments):
            result.append(("", target_segments[target_index]))
            target_index += 1
        
        return result
    
    @staticmethod
    def merge_entries(entries: List[Tuple[str, str]]) -> Tuple[str, str]:
        """Merge multiple translation entries into one.
        
        Args:
            entries: List of (source, target) tuples
            
        Returns:
            (merged_source, merged_target) tuple
        """
        if not entries:
            return ("", "")
        
        sources = [entry[0] for entry in entries if entry[0].strip()]
        targets = [entry[1] for entry in entries if entry[1].strip()]
        
        merged_source = TextSegmenter.merge_segments(sources)
        merged_target = TextSegmenter.merge_segments(targets)
        
        return (merged_source, merged_target)