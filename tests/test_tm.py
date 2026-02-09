"""Tests for Translation Memory service."""
import os
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def isolate_tm(tmp_path, monkeypatch):
    """Use a temp DB for each test."""
    test_db = tmp_path / "tm.db"
    test_dir = tmp_path
    monkeypatch.setattr("linguaedit.services.tm.TM_DIR", test_dir)
    monkeypatch.setattr("linguaedit.services.tm.TM_DB", test_db)
    yield test_db


class TestTranslationMemory:
    def test_add_and_lookup_exact(self):
        from linguaedit.services.tm import add_to_tm, lookup_tm
        add_to_tm("Hello", "Hej", "en", "sv")
        matches = lookup_tm("Hello", "en", "sv", threshold=0.9)
        assert len(matches) >= 1
        assert matches[0].target == "Hej"
        assert matches[0].similarity >= 0.99

    def test_add_empty_ignored(self):
        from linguaedit.services.tm import add_to_tm, lookup_tm
        add_to_tm("", "", "en", "sv")
        add_to_tm("  ", "  ", "en", "sv")
        matches = lookup_tm("", "en", "sv")
        assert len(matches) == 0

    def test_fuzzy_matching(self):
        from linguaedit.services.tm import add_to_tm, lookup_tm
        add_to_tm("Hello world", "Hej världen", "en", "sv")
        matches = lookup_tm("Hello World!", "en", "sv", threshold=0.7)
        assert len(matches) >= 1
        assert matches[0].similarity >= 0.7

    def test_no_match_below_threshold(self):
        from linguaedit.services.tm import add_to_tm, lookup_tm
        add_to_tm("Hello world", "Hej världen", "en", "sv")
        matches = lookup_tm("Completely different string", "en", "sv", threshold=0.9)
        assert len(matches) == 0

    def test_language_pair_isolation(self):
        from linguaedit.services.tm import add_to_tm, lookup_tm
        add_to_tm("Hello", "Hej", "en", "sv")
        add_to_tm("Hello", "Hallo", "en", "de")
        sv_matches = lookup_tm("Hello", "en", "sv")
        de_matches = lookup_tm("Hello", "en", "de")
        assert sv_matches[0].target == "Hej"
        assert de_matches[0].target == "Hallo"

    def test_update_existing(self):
        from linguaedit.services.tm import add_to_tm, lookup_tm
        add_to_tm("Hello", "Hej", "en", "sv")
        add_to_tm("Hello", "Hallå", "en", "sv")
        matches = lookup_tm("Hello", "en", "sv")
        assert len(matches) == 1
        assert matches[0].target == "Hallå"

    def test_feed_file(self):
        from linguaedit.services.tm import feed_file_to_tm, lookup_tm
        pairs = [("Hello", "Hej"), ("Goodbye", "Hejdå"), ("Save", "Spara")]
        count = feed_file_to_tm(pairs, "en", "sv", "test.po")
        assert count == 3
        matches = lookup_tm("Save", "en", "sv")
        assert len(matches) >= 1
        assert matches[0].target == "Spara"

    def test_persistence(self, isolate_tm):
        from linguaedit.services.tm import add_to_tm, _init_db
        import sqlite3
        add_to_tm("Hello", "Hej", "en", "sv")
        # Verify data is in DB file
        conn = sqlite3.connect(isolate_tm)
        rows = conn.execute("SELECT source, target FROM translation_memory").fetchall()
        conn.close()
        assert len(rows) >= 1
        assert ("Hello", "Hej") in rows
