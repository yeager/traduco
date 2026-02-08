# LinguaEdit

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![GitHub Release](https://img.shields.io/github/v/release/yeager/linguaedit)
![License](https://img.shields.io/badge/license-GPL--3.0-blue)
![Python](https://img.shields.io/badge/python-3.10+-green)
![Qt6](https://img.shields.io/badge/Qt-6-green)
![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS%20%7C%20Windows-lightgrey)

**Professional translation file editor built with Qt6/PySide6**

*Screenshots coming soon - see the complete feature list below for all capabilities*

## ✨ Features for Translators

### 📝 Multi-format Support
Edit translation files in multiple formats:
- **PO/POT** (GNU Gettext)
- **TS** (Qt Linguist XML)
- **XLIFF** 1.2 & 2.0
- **JSON** (flat & nested i18n)
- **YAML** (i18n files)
- **Android XML** (strings.xml)
- **ARB** (Flutter Application Resource Bundle)
- **PHP** (array format)

### 🔍 Smart Search & Replace
- Advanced search with **regex support**
- Replace across all translation units
- Filter by translation status
- Search in source text, translations, or comments
- Case-sensitive and whole-word options

### 🧠 Translation Memory
- **SQLite-based** translation memory
- **Fuzzy matching** algorithm
- Learn from your previous translations
- Suggest similar translations automatically
- Import/export TM databases

### 📚 Glossary & Terminology
- Built-in **glossary manager**
- **Consistency checking** across translations
- Term enforcement and suggestions
- Project-specific terminologies
- Import/export glossaries

### ✅ Smart Quality Assurance
Advanced linting for translation quality:
- **Format string validation** (printf, .NET, etc.)
- **HTML tag consistency** checking
- **Keyboard accelerator** validation (&File, etc.)
- **Duplicate translation** detection
- **Case consistency** checking
- **Whitespace** validation
- Quality score calculation

### 📊 Statistics & Reports
- Generate **HTML and PDF reports**
- Translation progress statistics
- Word count and completion rates
- Quality metrics overview
- Export data for project management

### 🔄 Batch Operations
- **Bulk fuzzy matching** from TM
- **Search & replace all** across files
- **Pre-translation** with AI services
- **Mass status updates**
- **Batch validation** runs

### 💬 Translator Workflow
- **Translator comments** for each string
- **Fuzzy/untranslated** status tracking
- **Previous/Next** navigation
- **Copy source to target**
- **History** of changes per entry

### 📂 Project Management
- **Multi-file project view**
- **Per-file status** overview
- Recent files quick access
- **Tabbed editing** interface
- **Drag-and-drop** file opening

### 🔀 File Comparison
- **Side-by-side diff view**
- Compare different file versions
- **Git integration** for version control
- **Change highlighting**

### 🌐 Online Synchronization
Integrate with translation platforms:
- **Weblate** (pull/push via REST API)
- **Transifex** (API v3 integration)
- **Crowdin** (API v2 support)
- **GitHub PR workflow**
- Secure API key storage

### 🎨 Beautiful Interface
Choose from 5 professional themes:
- **Light** - Clean and bright
- **Dark** - Easy on the eyes
- **Solarized Dark** - Developer favorite
- **Nord** - Arctic inspired
- **Monokai** - Syntax highlighting style

### 🌍 Multilingual Interface
LinguaEdit itself is available in 11 languages:
- 🇸🇪 **Svenska** (Swedish)
- 🇩🇪 **Deutsch** (German)  
- 🇫🇷 **Français** (French)
- 🇪🇸 **Español** (Spanish)
- 🇵🇹 **Português** (Portuguese)
- 🇯🇵 **日本語** (Japanese)
- 🇨🇳 **中文** (Chinese)
- 🇰🇷 **한국어** (Korean)
- 🇵🇱 **Polski** (Polish)
- 🇩🇰 **Dansk** (Danish)
- 🇳🇴 **Norsk** (Norwegian)

### ⌨️ Keyboard Shortcuts for Everything
Work efficiently with full keyboard support:

| Shortcut | Action |
|----------|--------|
| **Ctrl+O** | Open file |
| **Ctrl+S** | Save file |
| **Ctrl+H** | Find and Replace |
| **Ctrl+I** | Go to entry |
| **Ctrl+D** | Toggle Done status |
| **Ctrl+Shift+B** | Batch operations |
| **Ctrl+Shift+H** | Translation Memory |
| **Ctrl+Shift+O** | Online sync |
| **Ctrl+Shift+R** | Generate report |
| **Ctrl+Shift+V** | Validate all |

## 🚀 Installation

### Package Managers
```bash
# Python package managers
pip install linguaedit
pipx install linguaedit

# macOS Homebrew (coming soon)
brew install linguaedit
```

### Linux Packages

#### Debian/Ubuntu (APT Repository)
```bash
echo "deb https://yeager.github.io/debian-repo stable main" | sudo tee /etc/apt/sources.list.d/yeager.list
wget -O - https://yeager.github.io/debian-repo/key.gpg | sudo apt-key add -
sudo apt update
sudo apt install linguaedit
```

#### RPM-based (RHEL, Fedora, openSUSE)
```bash
# Add RPM repository
sudo tee /etc/yum.repos.d/yeager.repo << EOF
[yeager]
name=Yeager's RPM Repository
baseurl=https://yeager.github.io/rpm-repo
enabled=1
gpgcheck=0
EOF

sudo yum install linguaedit
# or on Fedora/openSUSE:
sudo dnf install linguaedit
```

### Windows & macOS Installers
Download platform-specific installers from [GitHub Releases](https://github.com/yeager/linguaedit/releases):
- **Windows**: `LinguaEdit-1.0.0-Windows-x64.exe`
- **macOS**: `LinguaEdit-1.0.0-macOS.dmg`

## 🛠️ Development

### Requirements
- Python 3.10+
- Qt6/PySide6
- Git (for repository features)

### Build from Source
```bash
git clone https://github.com/yeager/linguaedit.git
cd linguaedit
pip install -e ".[dev]"
linguaedit
```

## 🤝 Contributing

LinguaEdit is open source (GPL-3.0) and welcomes contributions:

- 🐛 **Bug reports** - Use GitHub Issues
- 💡 **Feature requests** - Discuss in GitHub Discussions  
- 🔄 **Pull requests** - Follow the contributing guide
- 🌍 **Translations** - Help translate LinguaEdit itself

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

## 👤 Credits

**Created by Daniel Nylander**  
Professional translator and open source developer

- 📧 Email: po@danielnylander.se
- 🐙 GitHub: [@yeager](https://github.com/yeager)
- 🌐 Website: https://danielnylander.se

## 💝 Support Development

If LinguaEdit helps your translation work, consider supporting its development:

- ⭐ **Star the project** on GitHub
- 💖 **GitHub Sponsors**: [github.com/sponsors/yeager](https://github.com/sponsors/yeager)
- 📱 **Swish** (Sweden): +46702526206

Your support helps keep LinguaEdit free and open source for the translation community!

---

## 📄 License

GPL-3.0-or-later - see [LICENSE](LICENSE) file for details.