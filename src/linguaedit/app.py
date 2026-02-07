"""LinguaEdit GTK4 application entry point."""

from __future__ import annotations

import sys
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio

from linguaedit import APP_ID
from linguaedit.ui.window import LinguaEditWindow


class LinguaEditApp(Adw.Application):
    """Main application class."""

    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_OPEN)
        self.connect("activate", self._on_activate)
        self.connect("open", self._on_open)

    def _on_activate(self, app):
        win = LinguaEditWindow(app)
        win.present()

    def _on_open(self, app, files, n_files, hint):
        win = LinguaEditWindow(app)
        if files:
            win._load_file(files[0].get_path())
        win.present()


def main():
    app = LinguaEditApp()
    app.run(sys.argv)


if __name__ == "__main__":
    main()
