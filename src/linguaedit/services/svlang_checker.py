"""svlang integration — Swedish QA checks (svengelska, consistency)."""

from __future__ import annotations

from linguaedit.services.linter import LintIssue

try:
    from svlang.checkers.svengelska import SvengelskaChecker
    from svlang.checkers.consistency import ConsistencyChecker
    HAS_SVLANG = True
except ImportError:
    HAS_SVLANG = False


def check_svengelska(text: str) -> list[dict]:
    """Check text for anglicisms. Returns list of {word, suggestion, position}."""
    if not HAS_SVLANG or not text:
        return []
    checker = SvengelskaChecker()
    return [
        {"word": hit.word, "suggestion": hit.suggestion, "position": hit.position}
        for hit in checker.check(text)
    ]


def check_consistency(entries: list[dict]) -> list[dict]:
    """Check for same source with different translations.

    Each entry dict must have: msgid, msgstr, index.
    Returns list of {source, translations, indices}.
    """
    if not HAS_SVLANG:
        return []
    checker = ConsistencyChecker()
    index_map: dict[str, list[int]] = {}
    for e in entries:
        msgid = e.get("msgid", "")
        msgstr = e.get("msgstr", "")
        idx = e.get("index", -1)
        if msgid and msgstr:
            checker.add(msgid, msgstr, str(idx))
            index_map.setdefault(msgid, []).append(idx)
    return [
        {
            "source": issue.source,
            "translations": dict(issue.translations),
            "indices": index_map.get(issue.source, []),
        }
        for issue in checker.check()
    ]


def run_svlang_checks(entries: list[dict], target_lang: str) -> list[LintIssue]:
    """Run all svlang checks on entries. Only runs for Swedish targets.

    Returns list of LintIssue to merge into the lint pipeline.
    """
    if not HAS_SVLANG:
        return []
    if not target_lang.startswith("sv"):
        return []

    issues: list[LintIssue] = []

    # Svengelska detection per entry
    for e in entries:
        msgstr = e.get("msgstr", "")
        idx = e.get("index", -1)
        msgid = e.get("msgid", "")
        if not msgstr:
            continue
        hits = check_svengelska(msgstr)
        for hit in hits:
            issues.append(LintIssue(
                "warning",
                f"Svengelska: \u201c{hit['word']}\u201d \u2192 {hit['suggestion']}",
                idx,
                msgid,
            ))

    # Consistency check
    for inc in check_consistency(entries):
        src = inc["source"]
        trans = list(inc["translations"].keys())
        for idx in inc["indices"]:
            issues.append(LintIssue(
                "warning",
                f"svlang: Inkonsekvent \u00f6vers\u00e4ttning f\u00f6r \u201c{src[:50]}\u201d ({len(trans)} varianter)",
                idx,
                src,
            ))

    return issues
