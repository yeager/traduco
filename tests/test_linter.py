"""Tests for the LinguaEdit linter."""
import pytest


def _make_entry(msgid, msgstr, flags=None, index=0):
    return {"msgid": msgid, "msgstr": msgstr, "flags": flags or [], "index": index}


class TestLinter:
    def _lint(self, entries):
        from linguaedit.services.linter import lint_entries
        return lint_entries(entries)

    # ── Missing translation ──────────────────────────────────────

    def test_missing_translation(self):
        result = self._lint([_make_entry("Hello", "")])
        assert any("Untranslated" in i.message for i in result.issues)

    def test_translated_no_issue(self):
        result = self._lint([_make_entry("Hello", "Hej")])
        untrans = [i for i in result.issues if "Untranslated" in i.message]
        assert len(untrans) == 0

    # ── Fuzzy ────────────────────────────────────────────────────

    def test_fuzzy_detected(self):
        result = self._lint([_make_entry("Hello", "Hej", flags=["fuzzy"])])
        assert any("Fuzzy" in i.message for i in result.issues)

    # ── Printf placeholder mismatch ─────────────────────────────

    def test_printf_mismatch(self):
        result = self._lint([_make_entry("Hello %s", "Hej")])
        assert any("Format specifier" in i.message or "format" in i.message.lower() for i in result.issues)

    def test_printf_match_ok(self):
        result = self._lint([_make_entry("Hello %s", "Hej %s")])
        fmt_issues = [i for i in result.issues if "Format specifier" in i.message]
        assert len(fmt_issues) == 0

    # ── Python format mismatch ───────────────────────────────────

    def test_python_format_mismatch(self):
        result = self._lint([_make_entry("Hello {name}", "Hej")])
        assert any("format" in i.message.lower() for i in result.issues)

    def test_python_format_ok(self):
        result = self._lint([_make_entry("Hello {name}", "Hej {name}")])
        py_issues = [i for i in result.issues if "Python format" in i.message]
        assert len(py_issues) == 0

    def test_positional_format_mismatch(self):
        result = self._lint([_make_entry("Item {0} of {1}", "Objekt {0}")])
        assert any("format" in i.message.lower() for i in result.issues)

    # ── Length ratio ─────────────────────────────────────────────

    def test_suspicious_length_ratio(self):
        result = self._lint([_make_entry("Hello world", "H")])
        assert any("length ratio" in i.message.lower() for i in result.issues)

    def test_normal_length_ok(self):
        result = self._lint([_make_entry("Hello world", "Hej världen")])
        length_issues = [i for i in result.issues if "length ratio" in i.message.lower()]
        assert len(length_issues) == 0

    # ── HTML tag mismatch ────────────────────────────────────────

    def test_html_tag_mismatch(self):
        result = self._lint([_make_entry("<b>Hello</b>", "Hej")])
        assert any("HTML" in i.message or "tag" in i.message.lower() for i in result.issues)

    def test_html_tags_match_ok(self):
        result = self._lint([_make_entry("<b>Hello</b>", "<b>Hej</b>")])
        html_issues = [i for i in result.issues if "HTML" in i.message]
        assert len(html_issues) == 0

    # ── Punctuation ──────────────────────────────────────────────

    def test_ending_punctuation_mismatch(self):
        result = self._lint([_make_entry("Hello.", "Hej")])
        assert any("Ending" in i.message for i in result.issues)

    def test_ending_punctuation_ok(self):
        result = self._lint([_make_entry("Hello.", "Hej.")])
        punct_issues = [i for i in result.issues if "Ending" in i.message]
        assert len(punct_issues) == 0

    # ── Whitespace ───────────────────────────────────────────────

    def test_leading_whitespace_mismatch(self):
        result = self._lint([_make_entry(" Hello", "Hej")])
        assert any("whitespace" in i.message.lower() for i in result.issues)

    def test_trailing_whitespace_mismatch(self):
        result = self._lint([_make_entry("Hello ", "Hej")])
        assert any("whitespace" in i.message.lower() for i in result.issues)

    def test_newline_mismatch(self):
        result = self._lint([_make_entry("Hello\nWorld", "Hej")])
        assert any("Newline" in i.message for i in result.issues)

    # ── Score ────────────────────────────────────────────────────

    def test_perfect_score(self):
        result = self._lint([_make_entry("Hello", "Hej"), _make_entry("Bye", "Hejdå")])
        # Should be close to 100 (maybe not exactly due to case etc.)
        assert result.score >= 80.0

    def test_bad_score(self):
        entries = [_make_entry(f"String {i}", "") for i in range(10)]
        result = self._lint(entries)
        assert result.score < 10.0
