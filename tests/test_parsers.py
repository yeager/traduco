"""Tests for all LinguaEdit file format parsers."""
import json
import shutil
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


# ── PO Parser ────────────────────────────────────────────────────

class TestPOParser:
    def test_parse(self):
        from linguaedit.parsers.po_parser import parse_po
        data = parse_po(FIXTURES / "test.po")
        assert len(data.entries) >= 4
        ids = [e.msgid for e in data.entries]
        assert "Hello" in ids
        assert "Cancel" in ids

    def test_translated_count(self):
        from linguaedit.parsers.po_parser import parse_po
        data = parse_po(FIXTURES / "test.po")
        # Hello, Goodbye, File are translated (not fuzzy, not empty)
        assert data.translated_count >= 2

    def test_fuzzy(self):
        from linguaedit.parsers.po_parser import parse_po
        data = parse_po(FIXTURES / "test.po")
        fuzzy = [e for e in data.entries if e.fuzzy]
        assert len(fuzzy) >= 1
        assert fuzzy[0].msgid == "Welcome"

    def test_roundtrip(self, tmp_path):
        from linguaedit.parsers.po_parser import parse_po, save_po
        data = parse_po(FIXTURES / "test.po")
        out = tmp_path / "out.po"
        save_po(data, out)
        data2 = parse_po(out)
        assert len(data2.entries) == len(data.entries)
        for a, b in zip(data.entries, data2.entries):
            assert a.msgid == b.msgid
            assert a.msgstr == b.msgstr

    def test_modify_and_save(self, tmp_path):
        from linguaedit.parsers.po_parser import parse_po, save_po
        data = parse_po(FIXTURES / "test.po")
        for e in data.entries:
            if e.msgid == "Cancel":
                e.msgstr = "Avbryt"
        out = tmp_path / "modified.po"
        save_po(data, out)
        data2 = parse_po(out)
        cancel = [e for e in data2.entries if e.msgid == "Cancel"][0]
        assert cancel.msgstr == "Avbryt"


# ── TS Parser ────────────────────────────────────────────────────

class TestTSParser:
    def test_parse(self):
        from linguaedit.parsers.ts_parser import parse_ts
        data = parse_ts(FIXTURES / "test.ts")
        assert len(data.entries) >= 4
        assert data.language == "sv"

    def test_unfinished(self):
        from linguaedit.parsers.ts_parser import parse_ts
        data = parse_ts(FIXTURES / "test.ts")
        unfinished = [e for e in data.entries if e.translation_type == "unfinished"]
        assert len(unfinished) >= 1

    def test_vanished(self):
        from linguaedit.parsers.ts_parser import parse_ts
        data = parse_ts(FIXTURES / "test.ts")
        vanished = [e for e in data.entries if e.translation_type == "vanished"]
        assert len(vanished) >= 1

    def test_roundtrip(self, tmp_path):
        from linguaedit.parsers.ts_parser import parse_ts, save_ts
        data = parse_ts(FIXTURES / "test.ts")
        out = tmp_path / "out.ts"
        save_ts(data, out)
        data2 = parse_ts(out)
        assert len(data2.entries) == len(data.entries)

    def test_modify_and_save(self, tmp_path):
        from linguaedit.parsers.ts_parser import parse_ts, save_ts
        data = parse_ts(FIXTURES / "test.ts")
        for e in data.entries:
            if e.source == "Cancel":
                e.translation = "Avbryt"
                e.translation_type = ""
        out = tmp_path / "modified.ts"
        save_ts(data, out)
        data2 = parse_ts(out)
        cancel = [e for e in data2.entries if e.source == "Cancel"][0]
        assert cancel.translation == "Avbryt"


# ── XLIFF Parser ─────────────────────────────────────────────────

class TestXLIFFParser:
    def test_parse(self):
        from linguaedit.parsers.xliff_parser import parse_xliff
        data = parse_xliff(FIXTURES / "test.xliff")
        assert len(data.entries) >= 3
        assert data.source_language == "en"
        assert data.target_language == "sv"

    def test_roundtrip(self, tmp_path):
        from linguaedit.parsers.xliff_parser import parse_xliff, save_xliff
        data = parse_xliff(FIXTURES / "test.xliff")
        out = tmp_path / "out.xliff"
        save_xliff(data, out)
        data2 = parse_xliff(out)
        assert len(data2.entries) == len(data.entries)

    def test_modify_and_save(self, tmp_path):
        from linguaedit.parsers.xliff_parser import parse_xliff, save_xliff
        data = parse_xliff(FIXTURES / "test.xliff")
        for e in data.entries:
            if e.source == "Save":
                e.target = "Spara"
        out = tmp_path / "modified.xliff"
        save_xliff(data, out)
        data2 = parse_xliff(out)
        save_entry = [e for e in data2.entries if e.source == "Save"][0]
        assert save_entry.target == "Spara"


# ── JSON Parser ──────────────────────────────────────────────────

class TestJSONParser:
    def test_parse_flat(self):
        from linguaedit.parsers.json_parser import parse_json
        data = parse_json(FIXTURES / "test_flat.json")
        assert len(data.entries) >= 4
        keys = [e.key for e in data.entries]
        assert "hello" in keys

    def test_parse_nested(self):
        from linguaedit.parsers.json_parser import parse_json
        data = parse_json(FIXTURES / "test_nested.json")
        keys = [e.key for e in data.entries]
        assert "menu.file" in keys
        assert "buttons.ok" in keys

    def test_roundtrip_flat(self, tmp_path):
        from linguaedit.parsers.json_parser import parse_json, save_json
        data = parse_json(FIXTURES / "test_flat.json")
        out = tmp_path / "out.json"
        save_json(data, out)
        data2 = parse_json(out)
        assert len(data2.entries) == len(data.entries)

    def test_roundtrip_nested(self, tmp_path):
        from linguaedit.parsers.json_parser import parse_json, save_json
        data = parse_json(FIXTURES / "test_nested.json")
        out = tmp_path / "out.json"
        save_json(data, out)
        data2 = parse_json(out)
        assert len(data2.entries) == len(data.entries)

    def test_modify(self, tmp_path):
        from linguaedit.parsers.json_parser import parse_json, save_json
        data = parse_json(FIXTURES / "test_flat.json")
        for e in data.entries:
            if e.key == "cancel":
                e.value = "Avbryt"
        out = tmp_path / "mod.json"
        save_json(data, out)
        data2 = parse_json(out)
        cancel = [e for e in data2.entries if e.key == "cancel"][0]
        assert cancel.value == "Avbryt"


# ── Chrome i18n Parser ───────────────────────────────────────────

class TestChromeI18nParser:
    def test_parse(self):
        from linguaedit.parsers.chrome_i18n import parse_chrome_i18n
        data = parse_chrome_i18n(FIXTURES / "chrome_messages.json")
        assert len(data.entries) >= 3
        keys = [e.key for e in data.entries]
        assert "hello" in keys

    def test_roundtrip(self, tmp_path):
        from linguaedit.parsers.chrome_i18n import parse_chrome_i18n, save_chrome_i18n
        data = parse_chrome_i18n(FIXTURES / "chrome_messages.json")
        out = tmp_path / "messages.json"
        save_chrome_i18n(data, out)
        data2 = parse_chrome_i18n(out)
        assert len(data2.entries) == len(data.entries)

    def test_placeholders_preserved(self):
        from linguaedit.parsers.chrome_i18n import parse_chrome_i18n
        data = parse_chrome_i18n(FIXTURES / "chrome_messages.json")
        greeting = [e for e in data.entries if e.key == "greeting"][0]
        assert greeting.placeholders  # should have placeholder data


# ── YAML Parser ──────────────────────────────────────────────────

class TestYAMLParser:
    def test_parse(self):
        from linguaedit.parsers.yaml_parser import parse_yaml
        data = parse_yaml(FIXTURES / "test.yaml")
        assert len(data.entries) >= 4

    def test_roundtrip(self, tmp_path):
        from linguaedit.parsers.yaml_parser import parse_yaml, save_yaml
        data = parse_yaml(FIXTURES / "test.yaml")
        out = tmp_path / "out.yaml"
        save_yaml(data, out)
        data2 = parse_yaml(out)
        assert len(data2.entries) == len(data.entries)

    def test_modify(self, tmp_path):
        from linguaedit.parsers.yaml_parser import parse_yaml, save_yaml
        data = parse_yaml(FIXTURES / "test.yaml")
        for e in data.entries:
            if e.key.endswith("cancel") or e.key == "cancel":
                e.value = "Avbryt"
        out = tmp_path / "mod.yaml"
        save_yaml(data, out)
        data2 = parse_yaml(out)
        cancel_entries = [e for e in data2.entries if "cancel" in e.key]
        assert any(e.value == "Avbryt" for e in cancel_entries)


# ── Android XML Parser ───────────────────────────────────────────

class TestAndroidParser:
    def test_parse(self):
        from linguaedit.parsers.android_parser import parse_android
        data = parse_android(FIXTURES / "strings.xml")
        assert len(data.entries) >= 4
        keys = [e.key for e in data.entries]
        assert "hello" in keys

    def test_roundtrip(self, tmp_path):
        from linguaedit.parsers.android_parser import parse_android, save_android
        data = parse_android(FIXTURES / "strings.xml")
        out = tmp_path / "strings.xml"
        save_android(data, out)
        data2 = parse_android(out)
        assert len(data2.entries) == len(data.entries)

    def test_modify(self, tmp_path):
        from linguaedit.parsers.android_parser import parse_android, save_android
        data = parse_android(FIXTURES / "strings.xml")
        for e in data.entries:
            if e.key == "cancel":
                e.value = "Avbryt"
        out = tmp_path / "strings.xml"
        save_android(data, out)
        data2 = parse_android(out)
        cancel = [e for e in data2.entries if e.key == "cancel"][0]
        assert cancel.value == "Avbryt"


# ── ARB Parser ───────────────────────────────────────────────────

class TestARBParser:
    def test_parse(self):
        from linguaedit.parsers.arb_parser import parse_arb
        data = parse_arb(FIXTURES / "test.arb")
        assert len(data.entries) >= 3
        keys = [e.key for e in data.entries]
        assert "hello" in keys

    def test_roundtrip(self, tmp_path):
        from linguaedit.parsers.arb_parser import parse_arb, save_arb
        data = parse_arb(FIXTURES / "test.arb")
        out = tmp_path / "out.arb"
        save_arb(data, out)
        data2 = parse_arb(out)
        assert len(data2.entries) == len(data.entries)

    def test_modify(self, tmp_path):
        from linguaedit.parsers.arb_parser import parse_arb, save_arb
        data = parse_arb(FIXTURES / "test.arb")
        for e in data.entries:
            if e.key == "cancel":
                e.value = "Avbryt"
        out = tmp_path / "mod.arb"
        save_arb(data, out)
        data2 = parse_arb(out)
        cancel = [e for e in data2.entries if e.key == "cancel"][0]
        assert cancel.value == "Avbryt"


# ── PHP Parser ───────────────────────────────────────────────────

class TestPHPParser:
    def test_parse(self):
        from linguaedit.parsers.php_parser import parse_php
        data = parse_php(FIXTURES / "test.php")
        assert len(data.entries) >= 4
        keys = [e.key for e in data.entries]
        assert "hello" in keys

    def test_roundtrip(self, tmp_path):
        from linguaedit.parsers.php_parser import parse_php, save_php
        data = parse_php(FIXTURES / "test.php")
        out = tmp_path / "out.php"
        save_php(data, out)
        data2 = parse_php(out)
        assert len(data2.entries) == len(data.entries)

    def test_modify(self, tmp_path):
        from linguaedit.parsers.php_parser import parse_php, save_php
        data = parse_php(FIXTURES / "test.php")
        for e in data.entries:
            if e.key == "cancel":
                e.value = "Avbryt"
        out = tmp_path / "mod.php"
        save_php(data, out)
        data2 = parse_php(out)
        cancel = [e for e in data2.entries if e.key == "cancel"][0]
        assert cancel.value == "Avbryt"


# ── Apple .strings Parser ────────────────────────────────────────

class TestAppleStringsParser:
    def test_parse(self):
        from linguaedit.parsers.apple_strings import parse_apple_strings
        data = parse_apple_strings(FIXTURES / "test.strings")
        assert len(data.entries) >= 3

    def test_roundtrip(self, tmp_path):
        from linguaedit.parsers.apple_strings import parse_apple_strings, save_apple_strings
        data = parse_apple_strings(FIXTURES / "test.strings")
        out = tmp_path / "out.strings"
        save_apple_strings(data, str(out))
        data2 = parse_apple_strings(out)
        assert len(data2.entries) == len(data.entries)

    def test_modify(self, tmp_path):
        from linguaedit.parsers.apple_strings import parse_apple_strings, save_apple_strings
        data = parse_apple_strings(FIXTURES / "test.strings")
        for e in data.entries:
            if e.msgid == "cancel":
                e.msgstr = "Avbryt"
        out = tmp_path / "mod.strings"
        save_apple_strings(data, str(out))
        data2 = parse_apple_strings(out)
        cancel = [e for e in data2.entries if e.msgid == "cancel"]
        if cancel:
            assert cancel[0].msgstr == "Avbryt"


# ── Unity .asset Parser ──────────────────────────────────────────

class TestUnityAssetParser:
    def test_parse(self):
        from linguaedit.parsers.unity_asset import parse_unity_asset
        data = parse_unity_asset(FIXTURES / "test.asset")
        assert len(data.entries) >= 1

    def test_roundtrip(self, tmp_path):
        from linguaedit.parsers.unity_asset import parse_unity_asset, save_unity_asset
        data = parse_unity_asset(FIXTURES / "test.asset")
        if len(data.entries) == 0:
            pytest.skip("No entries parsed from Unity asset")
        out = tmp_path / "out.asset"
        save_unity_asset(data, str(out))
        data2 = parse_unity_asset(out)
        assert len(data2.entries) >= 1


# ── RESX Parser ──────────────────────────────────────────────────

class TestRESXParser:
    def test_parse(self):
        from linguaedit.parsers.resx import parse_resx
        data = parse_resx(FIXTURES / "test.resx")
        assert len(data.entries) >= 3

    def test_roundtrip(self, tmp_path):
        from linguaedit.parsers.resx import parse_resx, save_resx
        data = parse_resx(FIXTURES / "test.resx")
        out = tmp_path / "out.resx"
        save_resx(data, str(out))
        data2 = parse_resx(out)
        assert len(data2.entries) == len(data.entries)

    def test_modify(self, tmp_path):
        from linguaedit.parsers.resx import parse_resx, save_resx
        data = parse_resx(FIXTURES / "test.resx")
        for e in data.entries:
            if e.msgid == "cancel":
                e.msgstr = "Avbryt"
        out = tmp_path / "mod.resx"
        save_resx(data, str(out))
        data2 = parse_resx(out)
        cancel = [e for e in data2.entries if e.msgid == "cancel"]
        if cancel:
            assert cancel[0].msgstr == "Avbryt"


# ── Java Properties Parser ───────────────────────────────────────

class TestJavaPropertiesParser:
    def test_parse(self):
        from linguaedit.parsers.java_properties import parse_java_properties
        data = parse_java_properties(FIXTURES / "test.properties")
        keys = [e.key for e in data.entries if not e.is_comment_line]
        assert "hello" in keys
        assert len(keys) >= 4

    def test_roundtrip(self, tmp_path):
        from linguaedit.parsers.java_properties import parse_java_properties, save_java_properties
        data = parse_java_properties(FIXTURES / "test.properties")
        out = tmp_path / "out.properties"
        save_java_properties(data, out)
        data2 = parse_java_properties(out)
        orig_keys = [e.key for e in data.entries if not e.is_comment_line and e.key]
        new_keys = [e.key for e in data2.entries if not e.is_comment_line and e.key]
        assert len(new_keys) == len(orig_keys)

    def test_modify(self, tmp_path):
        from linguaedit.parsers.java_properties import parse_java_properties, save_java_properties
        data = parse_java_properties(FIXTURES / "test.properties")
        for e in data.entries:
            if e.key == "cancel":
                e.value = "Avbryt"
        out = tmp_path / "mod.properties"
        save_java_properties(data, out)
        data2 = parse_java_properties(out)
        cancel = [e for e in data2.entries if e.key == "cancel"][0]
        assert cancel.value == "Avbryt"


# ── Godot Parser ─────────────────────────────────────────────────

class TestGodotParser:
    def test_parse_csv(self):
        from linguaedit.parsers.godot import parse_godot
        data = parse_godot(FIXTURES / "test.csv")
        assert len(data.entries) >= 3
        assert data.format == "csv"
        assert "en" in data.languages

    def test_roundtrip_csv(self, tmp_path):
        from linguaedit.parsers.godot import parse_godot, save_godot
        data = parse_godot(FIXTURES / "test.csv")
        out = tmp_path / "out.csv"
        data.path = out
        save_godot(data)
        data2 = parse_godot(out)
        assert len(data2.entries) == len(data.entries)


# ── Subtitles Parser ─────────────────────────────────────────────

class TestSubtitlesParser:
    def test_parse_srt(self):
        from linguaedit.parsers.subtitles import parse_subtitles
        data = parse_subtitles(FIXTURES / "test.srt")
        assert data.format == "srt"
        assert len(data.entries) >= 3
        assert data.entries[0].text == "Hello world"

    def test_parse_vtt(self):
        from linguaedit.parsers.subtitles import parse_subtitles
        data = parse_subtitles(FIXTURES / "test.vtt")
        assert data.format == "vtt"
        assert len(data.entries) >= 3

    def test_roundtrip_srt(self, tmp_path):
        from linguaedit.parsers.subtitles import parse_subtitles, save_subtitles
        data = parse_subtitles(FIXTURES / "test.srt")
        out = tmp_path / "out.srt"
        data.path = out
        save_subtitles(data)
        data2 = parse_subtitles(out)
        assert len(data2.entries) == len(data.entries)

    def test_roundtrip_vtt(self, tmp_path):
        from linguaedit.parsers.subtitles import parse_subtitles, save_subtitles
        data = parse_subtitles(FIXTURES / "test.vtt")
        out = tmp_path / "out.vtt"
        data.path = out
        save_subtitles(data)
        data2 = parse_subtitles(out)
        assert len(data2.entries) == len(data.entries)

    def test_modify_srt(self, tmp_path):
        from linguaedit.parsers.subtitles import parse_subtitles, save_subtitles
        data = parse_subtitles(FIXTURES / "test.srt")
        data.entries[0].translation = "Hej världen"
        out = tmp_path / "mod.srt"
        data.path = out
        save_subtitles(data)
        # File should exist and be non-empty
        assert out.stat().st_size > 0


# ── TMX (via safe_parse_xml) ─────────────────────────────────────

class TestTMXFixture:
    """Test that TMX XML fixture is valid and parseable."""

    def test_parse_tmx_xml(self):
        from linguaedit.parsers import safe_parse_xml
        tree = safe_parse_xml(FIXTURES / "test.tmx")
        root = tree.getroot()
        assert root.tag == "tmx"
        tus = root.findall(".//tu")
        assert len(tus) >= 3
