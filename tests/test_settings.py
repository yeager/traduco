"""Tests for Settings service."""
import json
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolate_settings(tmp_path, monkeypatch):
    """Use temp settings file."""
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr("linguaedit.services.settings._SETTINGS_FILE", settings_file)
    # Reset singleton
    from linguaedit.services.settings import Settings
    Settings.reset_instance()
    yield settings_file
    Settings.reset_instance()


class TestSettings:
    def test_get_singleton(self):
        from linguaedit.services.settings import Settings
        s1 = Settings.get()
        s2 = Settings.get()
        assert s1 is s2

    def test_defaults(self):
        from linguaedit.services.settings import Settings, DEFAULTS
        s = Settings.get()
        for key, default_val in DEFAULTS.items():
            val = s.get_value(key)
            # Language may be auto-detected, skip
            if key in ("language", "target_language"):
                continue
            assert val == default_val, f"Default mismatch for {key}: {val} != {default_val}"

    def test_get_value(self):
        from linguaedit.services.settings import Settings
        s = Settings.get()
        assert s.get_value("editor_font_size") == 12
        assert s.get_value("nonexistent", "fallback") == "fallback"

    def test_set_value(self):
        from linguaedit.services.settings import Settings
        s = Settings.get()
        s.set_value("editor_font_size", 16)
        assert s.get_value("editor_font_size") == 16

    def test_bracket_access(self):
        from linguaedit.services.settings import Settings
        s = Settings.get()
        assert s["editor_font_size"] == 12
        s["editor_font_size"] = 20
        assert s["editor_font_size"] == 20

    def test_save_and_load(self, isolate_settings):
        from linguaedit.services.settings import Settings
        s = Settings.get()
        s.set_value("translator_name", "Dansen")
        s.save()
        assert isolate_settings.exists()
        # Reset and reload
        Settings.reset_instance()
        s2 = Settings.get()
        assert s2.get_value("translator_name") == "Dansen"

    def test_last_translator(self):
        from linguaedit.services.settings import Settings
        s = Settings.get()
        s.set_value("translator_name", "Dansen")
        s.set_value("translator_email", "dansen@test.se")
        assert s.last_translator == "Dansen <dansen@test.se>"
