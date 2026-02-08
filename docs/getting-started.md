# Getting Started

## Requirements

- Python 3.10 or later
- PySide6 (Qt 6)

## Installation

### From PyPI (pip)

```bash
pip install linguaedit

# With AI translation support (OpenAI, Anthropic):
pip install linguaedit[ai]
```

### From Source

```bash
git clone https://github.com/yeager/linguaedit.git
cd linguaedit
pip install -e .
```

### Platform-Specific Dependencies

#### macOS

```bash
brew install enchant
pip install PySide6
```

#### Ubuntu / Debian

```bash
sudo apt install libenchant-2-dev
pip install PySide6
```

#### Fedora / RHEL

```bash
sudo dnf install enchant2-devel
pip install PySide6
```

### Pre-Built Packages

- **macOS** — Download from [GitHub Releases](https://github.com/yeager/linguaedit/releases)
- **Linux (.deb)** — Available from [Yeager's APT repository](https://yeager.github.io/debian-repo/)
- **Windows** — Build from source or use GitHub Actions artefacts

## First Launch

Start LinguaEdit from the command line:

```bash
# Launch the GUI
linguaedit

# Open a file directly
linguaedit path/to/file.po
```

### Welcome Wizard

On first launch, a setup wizard will guide you through:

1. **Personal information** — Your name, email, and preferred locale
2. **Translation settings** — Default translation engine, source and target languages, formality level
3. **Appearance** — Theme (system, light, or dark) and editor font size

These settings can be changed at any time via **Edit → Preferences** (Ctrl+,).

## Opening Your First File

After completing the wizard, you can open a translation file in several ways:

- **File → Open** (Ctrl+O) — Browse for a file
- **Drag and drop** — Drop a file onto the LinguaEdit window
- **Command line** — Pass the file path as an argument
- **Recent files** — Access previously opened files from **File → Recent Files**

LinguaEdit supports the following file extensions: `.po`, `.pot`, `.ts`, `.json`, `.xliff`, `.xlf`, `.xml`, `.arb`, `.php`, `.yml`, `.yaml`.
