# Changelog
## 0.8.1 (2026-02-08)

### New Features
- HTML/PDF report generation (Catalog → Generate Report, Ctrl+Shift+R)
- Validation dialog: sortable columns, non-modal (edit while validating)
- Fuzzy auto-clear when editing translations
- Source code references shown below translation

### Improvements
- Left sidebar with quick actions (Open, Save, Validate, Compile, Pre-translate, Search, Settings)
- Sort by "Untranslated/errors first"
- File associations on Windows (Inno Setup), macOS (CFBundleDocumentTypes), Linux (.desktop MimeType)
- Windows installer (Inno Setup) with desktop icon and Start menu
- Linter messages fully translatable (9 lint types in 11 languages)
- 278 translated strings per language (3,058 total)
- Complete i18n: preferences, welcome dialog, lint messages, validation dialog

## 0.8.0 (2026-02-08)

### 🌐 11 Languages
- Swedish, German, French, Spanish, Portuguese (Brazil), Japanese, Chinese (Simplified), Korean, Polish, Danish, Norwegian Bokmål

### 📖 Documentation
- Full documentation in `docs/` — accessible from Help → Documentation

### 🎨 Theme Support
- Light, Dark, and System themes via View → Theme

### New Features
- Compile .mo/.qm (Catalog → Compile translation, Ctrl+Shift+B)
- Auto-compile on save (Settings → Translation)
- Editable file header/metadata dialog (Catalog → File metadata…)
- Column sorting (click any column header)
- GitHub Repository and Report a Bug links in Help menu
- Documentation link in Help menu

### Improvements
- All UI strings translatable (314+ strings)
- macOS: correct app name in menu bar (was "Python")
- Better row colors: theme-aware, subtle tints instead of harsh pink
- Fuzzy → "Luddig" in Swedish translation
- Lint messages translated
- pyobjc-framework-Cocoa for macOS app name fix
- Translations bundled inside Python package


All notable changes to LinguaEdit will be documented in this file.

## [0.4.1] — 2026-02-08

### Added

- **Full i18n for all menus and dialogs** — all menu items, metadata dialog, and donate dialog now use Qt translation system (self.tr())
- **Editable file header/metadata dialog** — edit PO metadata key-value pairs, TS/XLIFF language fields, ARB locale, YAML root key
- **Donate dialog** — GitHub Sponsors (yeager) + Swish with deep link

### Improved

- **Swedish translations** — 188 translated strings covering toolbar, menus, metadata dialog, donate dialog, and all UI elements
- **Menu structure** — added &Catalog, &Go, &Git menus with full keyboard shortcut support

### Fixed

- Menu strings that were hardcoded in English now properly translatable

## [0.4.0] — 2026-02-08

### Changed

- **Migrated from GTK4/libadwaita to PySide6 (Qt6)** — full UI rewrite
  - Cross-platform without system GTK dependencies
  - PyInstaller-friendly (no PyGObject crashes on macOS)
  - All dialogs, menus, toolbars, and status bar converted
- **Translations migrated from gettext PO to Qt TS format** — Qt Linguist workflow
- Replaced PyGObject dependency with PySide6>=6.5
- Added "About Qt" to Help menu
- Updated GitHub Actions workflow for PySide6 builds
- Updated .deb packaging for PySide6 dependencies

### Added

- **Toolbar with icons and text** — Open, Save, Undo, Redo, Previous, Next, Copy Source, Pre-translate, Validate (Qt.ToolButtonTextUnderIcon style)
- **App logo** — custom SVG/PNG icon (speech bubble + pen) used as window icon and in About dialog
- **macOS app name fix** — menu bar now shows "LinguaEdit" instead of "Python" (via NSBundle + setApplicationDisplayName)
- **Improved Swedish translations** — toolbar strings (Previous, Next, Copy Source, Validate) added and compiled
- **Donate section** — GitHub Sponsors (yeager) + Swish; removed Ko-fi/PayPal links
- **Screenshots** — main window and preferences dialog screenshots in `docs/screenshots/`

### Removed

- GTK4/libadwaita/PyGObject dependencies
- po/ directory (replaced by translations/*.ts/*.qm)

## [0.3.0] — 2026-02-07

### Added

- **5 new file format parsers** — XLIFF 1.2/2.0, Android XML (strings.xml),
  Flutter ARB, PHP arrays, and YAML
- **Tabbed editing** — open multiple files in tabs simultaneously
- **Glossary manager** — maintain project glossaries with term enforcement
- **QA profiles** — configurable quality assurance rule sets (formal, casual, strict)
- **Translation reports** — generate HTML/CSV summary reports with statistics
- **Git integration** — view file status, diffs, and staged changes from the editor
- **Persistent comments** — translator comments stored per-file across sessions
- **Export to multiple formats** — save translations to any supported format
- **Improved column sorting** — stable sort with secondary key support
- **Enhanced toolbar** — new icons for glossary, QA, report, and git actions

### Changed

- Bumped version to 0.3.0
- Updated parser registry to support all 8 file formats
- Modernized file-open dialog with format auto-detection

### Fixed

- Stable sort order when toggling column headers
- Proper encoding handling for PHP and YAML files
- XLIFF namespace handling for both v1.2 and v2.0

## [0.2.0] — 2026-02-07

### Added

- **14 UX improvements** — inline linting, format-specifier highlighting,
  translation memory (TM) with fuzzy lookup, diff viewer, drag-and-drop file
  opening, recent-files menu, search & filter bar, batch pre-translation,
  keyboard shortcuts throughout, progress bar, dark/light theme toggle,
  plural-form editing, comment editing, and character/word count display
- **Column sorting** — click any column header to sort the entry list
- **Toolbar icons** — symbolic icons for all toolbar actions (open, save, lint,
  translate, sync, settings)
- **Transifex integration** — pull/push resources via Transifex API v3
- **Weblate integration** — pull/push translations via Weblate REST API
- **Crowdin integration** — pull/push files via Crowdin API v2
- **Secure keystore** — API keys stored in platform keyring (libsecret/Keychain)
- **Sync dialog** — unified pull/push UI for all three platforms
- **Platform settings dialog** — configure API tokens per platform

### Changed

- Assigned application ID `se.danielnylander.LinguaEdit`

### Fixed

- Improved lint accuracy for plural forms and format specifiers
- Correct handling of nested JSON keys with dots

## [0.1.0] — 2026-02-07

### Initial Release

- Multi-format editing — PO/POT (gettext), Qt TS (XML), JSON (flat & nested)
- Linting & quality score — format specifier checks, whitespace, length ratio
- Pre-translation — Lingva and MyMemory (free), OpenAI and Anthropic (paid)
- Spell checking — via PyEnchant with configurable language
- Metadata viewer — Last-Translator, PO-Revision-Date, language, etc.
- GitHub PR integration — fetch POT, create branch, push translation, open PR
- Platform integration — Transifex, Weblate, Crowdin API support
- In-app updates — automatic update checking (macOS/Windows)
- Internationalized — Swedish translation included
