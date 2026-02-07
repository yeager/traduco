# LinguaEdit

A GTK4 translation file editor for **PO**, **TS**, and **JSON** i18n files.

![License](https://img.shields.io/badge/license-GPL--3.0--or--later-blue)
![Python](https://img.shields.io/badge/python-3.10+-green)
![Version](https://img.shields.io/badge/version-0.2.0-orange)
![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS%20%7C%20Windows-lightgrey)

<!-- ![Screenshot](docs/screenshot.png) -->

## Features

- **Multi-format editing** — PO/POT (gettext), Qt TS (XML), JSON (flat & nested)
- **Inline linting & quality score** — format specifier checks, whitespace, length ratio, punctuation
- **Pre-translation** — Lingva, MyMemory (free); OpenAI, Anthropic (paid)
- **Translation memory** — fuzzy lookup from previously translated entries
- **Spell checking** — via PyEnchant with configurable language
- **Column sorting** — click headers to sort by source, translation, or status
- **Toolbar icons** — symbolic icons for all actions
- **Diff viewer** — side-by-side comparison of changes
- **Search & filter** — filter entries by text, status, or lint issues
- **Batch translation** — pre-translate all untranslated entries at once
- **Drag-and-drop** — open files by dropping them on the window
- **Recent files** — quick access to last 20 opened files
- **Keyboard shortcuts** — Ctrl+S save, Ctrl+O open, Ctrl+F find, and more
- **Metadata viewer** — Last-Translator, PO-Revision-Date, language, etc.
- **Plural form editing** — full support for nplurals
- **Comment editing** — translator comments per entry
- **Character & word count** — live display in status bar
- **Dark/light theme** — follows system preference or manual toggle

### Platform Integration

- **GitHub PR workflow** — fetch POT, create branch, push translation, open PR
- **Transifex** — pull/push resources via API v3
- **Weblate** — pull/push translations via REST API
- **Crowdin** — pull/push files via API v2
- **Secure keystore** — API keys stored in platform keyring (libsecret / macOS Keychain)

### In-app Updates

Automatic update checking on macOS and Windows.

## Requirements

- Python 3.10+
- GTK4 and libadwaita
- PyGObject

### macOS

```bash
brew install gtk4 libadwaita pygobject3 enchant
```

### Linux (Ubuntu/Debian)

```bash
sudo apt install libgtk-4-dev libadwaita-1-dev python3-gi gir1.2-adw-1 libenchant-2-dev
```

### Linux (Fedora)

```bash
sudo dnf install gtk4-devel libadwaita-devel python3-gobject enchant2-devel
```

## Installation

```bash
pip install -e .

# With AI translation support:
pip install -e ".[ai]"
```

### Pre-built packages

- **macOS** — download `LinguaEdit-0.2.0-macOS.zip` from [Releases](https://github.com/yeager/linguaedit/releases)
- **Linux (.deb)** — available from [Yeager's APT repo](https://yeager.github.io/debian-repo/)
- **Windows** — build from source or use GitHub Actions artifacts

## Usage

```bash
# Launch GUI
linguaedit

# Open a file directly
linguaedit path/to/file.po
```

## Project Structure

```
linguaedit/
├── src/linguaedit/
│   ├── app.py              # Application entry point
│   ├── ui/
│   │   ├── window.py       # Main GTK4 window
│   │   ├── platform_dialog.py
│   │   └── sync_dialog.py
│   ├── parsers/
│   │   ├── po_parser.py    # PO/POT parser (polib)
│   │   ├── ts_parser.py    # Qt TS parser (XML)
│   │   └── json_parser.py  # JSON i18n parser
│   └── services/
│       ├── linter.py       # Translation linting & quality score
│       ├── translator.py   # Pre-translation engines
│       ├── spellcheck.py   # Spell checking (enchant)
│       ├── github.py       # GitHub PR workflow
│       ├── platforms.py    # Transifex, Weblate, Crowdin
│       ├── keystore.py     # Secure API key storage
│       ├── tm.py           # Translation memory
│       └── updater.py      # In-app update checker
├── po/                     # Translations for LinguaEdit itself
├── docs/                   # Documentation
└── pyproject.toml
```

## License

GPL-3.0-or-later — see [LICENSE](LICENSE)

## Author

Daniel Nylander <po@danielnylander.se>
