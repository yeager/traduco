"""QA profiles for formal/informal translation checks."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

PROFILES_FILE = Path.home() / ".config" / "linguaedit" / "qa_profiles.json"


@dataclass
class QARule:
    """A single QA rule."""
    name: str
    pattern: str  # regex pattern to flag
    message: str
    severity: str = "warning"  # "error", "warning", "info"


@dataclass
class QAProfile:
    """A QA profile with rules."""
    name: str
    description: str = ""
    rules: list[QARule] = field(default_factory=list)


@dataclass
class QAViolation:
    """A QA profile violation."""
    rule_name: str
    message: str
    entry_index: int
    severity: str = "warning"


# Built-in profiles
_BUILTIN_PROFILES = {
    "formal": QAProfile(
        name="formal",
        description="Formal language rules (Swedish)",
        rules=[
            QARule("no-du", r"\bdu\b", "Use formal 'ni' instead of 'du'", "warning"),
            QARule("no-dig", r"\bdig\b", "Use formal 'er' instead of 'dig'", "warning"),
            QARule("no-din", r"\bdin\b", "Use formal 'er' instead of 'din'", "warning"),
            QARule("no-ditt", r"\bditt\b", "Use formal 'ert' instead of 'ditt'", "warning"),
            QARule("no-dina", r"\bdina\b", "Use formal 'era' instead of 'dina'", "warning"),
            QARule("no-slang", r"\b(kolla|fixa|grej|snabb|kul)\b", "Avoid informal language", "info"),
        ],
    ),
    "informal": QAProfile(
        name="informal",
        description="Informal language rules (Swedish)",
        rules=[
            QARule("no-ni", r"\bNi\b", "Use informal 'du' instead of 'Ni'", "warning"),
            QARule("no-er-formal", r"\bEr\b", "Use informal 'dig/din' instead of 'Er'", "info"),
            QARule("no-stiff", r"\b(vederbörande|härvid|tillika)\b", "Avoid overly formal language", "info"),
        ],
    ),
}


def get_profiles() -> dict[str, QAProfile]:
    """Get all QA profiles (built-in + custom)."""
    profiles = dict(_BUILTIN_PROFILES)
    if PROFILES_FILE.exists():
        try:
            data = json.loads(PROFILES_FILE.read_text("utf-8"))
            for name, pdata in data.items():
                rules = [QARule(**r) for r in pdata.get("rules", [])]
                profiles[name] = QAProfile(
                    name=name, description=pdata.get("description", ""),
                    rules=rules,
                )
        except Exception:
            pass
    return profiles


def check_profile(profile_name: str, entries: list[dict]) -> list[QAViolation]:
    """Check entries against a QA profile.

    Each entry: {"index": int, "msgstr": str}
    """
    profiles = get_profiles()
    profile = profiles.get(profile_name)
    if not profile:
        return []

    violations = []
    for entry in entries:
        idx = entry.get("index", -1)
        msgstr = entry.get("msgstr", "")
        if not msgstr:
            continue
        for rule in profile.rules:
            if re.search(rule.pattern, msgstr, re.IGNORECASE):
                violations.append(QAViolation(
                    rule_name=rule.name, message=rule.message,
                    entry_index=idx, severity=rule.severity,
                ))
    return violations
