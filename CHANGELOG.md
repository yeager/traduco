# Changelog

All notable changes to Traduco will be documented in this file.

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

- **Renamed from LexiLoom to Traduco** — new application ID
  `se.danielnylander.Traduco`, updated all references

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
