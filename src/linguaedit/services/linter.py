"""Translation linting and quality score."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class LintIssue:
    severity: str  # "error", "warning", "info"
    message: str
    entry_index: int = -1
    msgid: str = ""


@dataclass
class LintResult:
    issues: list[LintIssue] = field(default_factory=list)
    score: float = 100.0  # quality percentage

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")


def lint_entries(entries: list[dict]) -> LintResult:
    """Lint a list of translation entries.

    Each entry dict must have: msgid, msgstr, flags (list), index (int).
    Returns LintResult with issues and quality score.
    """
    issues: list[LintIssue] = []
    total = len(entries)
    if total == 0:
        return LintResult(issues=[], score=100.0)

    penalty = 0.0

    for e in entries:
        idx = e.get("index", -1)
        msgid = e.get("msgid", "")
        msgstr = e.get("msgstr", "")
        flags = e.get("flags", [])

        if not msgid:
            continue

        # Missing translation
        if not msgstr:
            issues.append(LintIssue("warning", "Untranslated", idx, msgid))
            penalty += 1.0
            continue

        # Fuzzy
        if "fuzzy" in flags:
            issues.append(LintIssue("info", "Fuzzy", idx, msgid))
            penalty += 0.5

        # Trailing/leading whitespace mismatch
        if msgid.startswith(" ") != msgstr.startswith(" "):
            issues.append(LintIssue("warning", "Leading whitespace mismatch", idx, msgid))
            penalty += 0.3
        if msgid.endswith(" ") != msgstr.endswith(" "):
            issues.append(LintIssue("warning", "Trailing whitespace mismatch", idx, msgid))
            penalty += 0.3

        # Newline mismatch
        src_nl = msgid.count("\n")
        dst_nl = msgstr.count("\n")
        if src_nl != dst_nl:
            issues.append(LintIssue("warning", f"Newline count mismatch ({src_nl} vs {dst_nl})", idx, msgid))
            penalty += 0.3

        # Printf format specifier mismatch
        src_fmt = set(re.findall(r'%[\d$]*[sdiufxXoecpg%]', msgid))
        dst_fmt = set(re.findall(r'%[\d$]*[sdiufxXoecpg%]', msgstr))
        if src_fmt != dst_fmt:
            issues.append(LintIssue("error", f"Format specifier mismatch: {src_fmt} vs {dst_fmt}", idx, msgid))
            penalty += 2.0

        # Python format specifier mismatch
        src_py = set(re.findall(r'\{[^}]*\}', msgid))
        dst_py = set(re.findall(r'\{[^}]*\}', msgstr))
        if src_py != dst_py:
            issues.append(LintIssue("error", f"Python format mismatch: {src_py} vs {dst_py}", idx, msgid))
            penalty += 2.0

        # Punctuation mismatch (ending)
        if msgid and msgstr:
            for p in ".!?:;":
                if msgid.endswith(p) and not msgstr.endswith(p):
                    issues.append(LintIssue("info", f"Ending '{p}' missing in translation", idx, msgid))
                    penalty += 0.1
                    break

        # Suspicious length ratio
        if len(msgid) > 5 and len(msgstr) > 0:
            ratio = len(msgstr) / len(msgid)
            if ratio > 3.0 or ratio < 0.2:
                issues.append(LintIssue("warning", f"Suspicious length ratio: {ratio:.1f}x", idx, msgid))
                penalty += 0.5

    score = max(0.0, 100.0 - (penalty / total) * 100.0)
    return LintResult(issues=issues, score=round(score, 1))
