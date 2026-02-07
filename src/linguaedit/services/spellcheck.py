"""Spell checking via PyEnchant."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SpellIssue:
    word: str
    suggestions: list[str] = field(default_factory=list)
    offset: int = 0


def check_text(text: str, language: str = "en_US") -> list[SpellIssue]:
    """Check spelling in text. Returns list of misspelled words with suggestions."""
    try:
        import enchant
    except ImportError:
        return []  # silently skip if not installed

    try:
        d = enchant.Dict(language)
    except enchant.errors.DictNotFoundError:
        return []

    issues = []
    # Simple word tokenization
    import re
    for m in re.finditer(r"[a-zA-ZàáâãäåæçèéêëìíîïðñòóôõöùúûüýþÿÀ-ÖØ-öø-ÿ]+", text):
        word = m.group()
        if len(word) < 2:
            continue
        if not d.check(word):
            suggestions = d.suggest(word)[:5]
            issues.append(SpellIssue(word=word, suggestions=suggestions, offset=m.start()))
    return issues


def available_languages() -> list[str]:
    """Return list of available spell check languages."""
    try:
        import enchant
        return enchant.list_languages()
    except ImportError:
        return []
