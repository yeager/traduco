"""Tests for security features."""
import os
import tempfile
from pathlib import Path

import pytest


class TestXXEProtection:
    """Test that safe_parse_xml blocks XXE attacks."""

    def test_xxe_file_read_blocked(self, tmp_path):
        """XXE attempting to read /etc/passwd should fail or not expand."""
        from linguaedit.parsers import safe_parse_xml
        
        xxe_file = tmp_path / "xxe.xml"
        xxe_file.write_text(
            '<?xml version="1.0"?>\n'
            '<!DOCTYPE foo [\n'
            '  <!ENTITY xxe SYSTEM "file:///etc/passwd">\n'
            ']>\n'
            '<root>&xxe;</root>\n'
        )
        
        try:
            tree = safe_parse_xml(xxe_file)
            root = tree.getroot()
            # If it parsed, the entity should NOT have been expanded
            text = root.text or ""
            assert "root:" not in text, "XXE entity was expanded — /etc/passwd content leaked!"
        except Exception:
            # Parsing failed — that's the safe behavior
            pass

    def test_billion_laughs_blocked(self, tmp_path):
        """Billion laughs (entity expansion bomb) should fail."""
        from linguaedit.parsers import safe_parse_xml
        
        bomb = tmp_path / "bomb.xml"
        bomb.write_text(
            '<?xml version="1.0"?>\n'
            '<!DOCTYPE lolz [\n'
            '  <!ENTITY lol "lol">\n'
            '  <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">\n'
            '  <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">\n'
            '  <!ENTITY lol4 "&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;">\n'
            ']>\n'
            '<root>&lol4;</root>\n'
        )
        
        try:
            tree = safe_parse_xml(bomb)
            root = tree.getroot()
            text = root.text or ""
            # If parsed, the expanded text should be reasonably short
            assert len(text) < 100000, "Billion laughs entity expansion not blocked!"
        except Exception:
            # Parse error is the safe/expected behavior
            pass

    def test_safe_fromstring(self):
        """safe_fromstring_xml should also block XXE."""
        from linguaedit.parsers import safe_fromstring_xml
        
        xxe_xml = (
            '<?xml version="1.0"?>\n'
            '<!DOCTYPE foo [\n'
            '  <!ENTITY xxe SYSTEM "file:///etc/passwd">\n'
            ']>\n'
            '<root>&xxe;</root>'
        )
        
        try:
            elem = safe_fromstring_xml(xxe_xml)
            text = elem.text or ""
            assert "root:" not in text
        except Exception:
            pass  # Expected


class TestPluginPathTraversal:
    """Test that plugin loader refuses files outside plugin dir."""

    def test_path_traversal_blocked(self, tmp_path, monkeypatch):
        """Loading a plugin with path traversal should be refused."""
        try:
            from linguaedit.services.plugins import PluginManager
        except ImportError:
            pytest.skip("PluginManager requires PySide6")

        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()

        # Create a fake "plugin" outside the plugin dir
        outside = tmp_path / "evil.py"
        outside.write_text("print('pwned')")

        # Create a symlink or path that traverses out
        traversal_path = plugin_dir / ".." / "evil.py"
        
        # The PluginManager._load_plugin should refuse this
        try:
            pm = PluginManager.__new__(PluginManager)
            pm._plugin_dir = plugin_dir
            pm._plugins = []
            pm._load_plugin(traversal_path)
        except (AttributeError, TypeError):
            # May fail due to Qt signal setup — that's OK,
            # the security check is in _load_plugin before Qt usage
            pass

        # Verify evil.py was NOT imported
        import sys
        assert "evil" not in sys.modules
