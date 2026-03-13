# CHANGELOG

## [1.8.14-r2] — 2026-03-13

### Added
- **Cross-platform builds** — Official macOS .app bundle and Windows portable version
- **macOS DMG installer** — Ready-to-use drag-and-drop installer (64MB)
- **Windows portable ZIP** — Python-based portable version with batch launcher (1.5MB)
- **Professional packaging** — DEB/RPM packages with proper dependencies and desktop integration
- **GitHub repository integration** — DEB (Ubuntu/Debian) and RPM (Fedora/RHEL) repositories
- **Updated installation documentation** — Complete installation guide for all platforms

### Fixed
- **Man page generation** — Created during package build for proper documentation
- **Package metadata** — Corrected descriptions and dependencies across all formats
- **Repository publishing** — Automated package deployment to GitHub Pages repositories

### Distribution
- **macOS**: `LinguaEdit-1.8.14-macOS-arm64.dmg` (Apple Silicon native)
- **Windows**: `LinguaEdit-1.8.14-Windows-Portable.zip` (Python + requirements)
- **Linux DEB**: Available via `apt install linguaedit` from yeager repository
- **Linux RPM**: Available via `dnf install linguaedit` from yeager repository
- **Python PyPI**: Available via `pip install linguaedit` (cross-platform)

### Repository URLs
- DEB repo: https://yeager.github.io/debian-repo/
- RPM repo: https://yeager.github.io/rpm-repo/
- Source: https://github.com/yeager/linguaedit

## [1.8.14] — 2026-02-14

### Added
- **Drag & drop** — save dialog when dropping a file with unsaved changes
- **Drag & drop** — video file handling with subtitle track extraction
- **Windows DPAPI keystore** — native credential storage via ctypes (no keyring dependency)
- **.qm translations** compiled for all languages with actual translations

### Fixed
- **Transifex** — redirect handling fix for API calls
- **Crowdin** — ZIP extraction + `project_id` type coercion fix
- **Currency format** — `%1$` variables no longer falsely detected as currency symbols
- **Windows locale detection** — proper system language detection for UI language selection

### Changed
- **Small .qm exclusion** — translation files under 20 KB excluded from builds (empty/near-empty)
- Removed 11 empty translation files (.ts/.qm) with zero translated strings

## [1.8.13] — 2026-02-13

### Added
- **Browse buttons** for Transifex, Weblate, and Crowdin — list projects/orgs without manual input
- **Context column** for file types with context (TS/PO/XLIFF)
- **svlang integration** — svengelska detection + consistency checks for Swedish translations
- **Windows keyring verification** for credential storage

### Changed
- Default sort order changed to file order (ascending)
- Number localization lint changed to info severity

### Fixed
- Clean error messages from platform APIs (no more raw HTML dumps)
- 33 missing Swedish translations fixed (newline strings)
- Duplicate .ts messages cleaned up
- update_translations.py false positive fix

## [1.8.12] — 2026-02-13

### Changed
- **Flag icons** — replaced painted stripes with proper flag images from FlagKit (MIT). Works on all platforms including Windows.

## [1.8.11] — 2026-02-13

### Fixed
- **Flag icons on Windows** — Windows doesn't render flag emoji; now uses painted stripe flags instead (works everywhere)

## [1.8.10] — 2026-02-13

### Fixed
- **Windows translations** — PyInstaller bundle: translations dir lookup via `sys._MEIPASS`
- **Auto-detect language** — Welcome wizard now pre-selects system language instead of defaulting to English
- **i18n logging** — added debug logging for translation loading (helps diagnose issues)
- **macOS-only code guarded** — `defaults read` fallback only runs on macOS

## [1.8.9] — 2026-02-13

### Fixed
- **Flag icons on Windows** — use Segoe UI Emoji instead of Apple Color Emoji (Linux: Noto Color Emoji)
- **Translations on Windows** — improved translations directory discovery (importlib.resources + Windows site-packages path)

## [1.8.8] — 2026-02-13

### Fixed
- **Swedish translation** — 21 inconsistencies corrected (terminology, accelerators, formatting)
- **CI** — compile only non-empty translations, remove stale .qm before build

## [1.8.7] — 2026-02-13

### Added
- **Language picker** — dynamic selector with country flags, based on available .qm files
- **Transifex source sync** — CI workflow pushes new source strings automatically
- **Update checker** — startup background check for new GitHub releases
- **Weblate/Crowdin/Transifex** — platform browser with translation statistics

### Changed
- **Translations** — consolidated to single `src/linguaedit/translations/` directory
- **Language picker** — only shows languages with actual translations (skips empty .qm)
- **CI** — Transifex workflow now pushes source strings before pulling translations
- **1,522 source strings** (up from 1,282)

### Fixed
- **Quit** — now prompts to save unsaved changes
- **Stats** — counter and row color update correctly after editing translations

## [1.8.6] — 2026-02-13

### Changed
- **Pre-translate** — runs in background QThread (UI no longer freezes)
- **Pre-translate** — API key field added directly in dialog (no need for separate dialog)
- **Pre-translate** — source language auto-detection (Auto-detect option in dropdown)
- **Transifex** — integration for community translations (18 languages, daily sync via GitHub Actions)
- **i18n** — all Swedish source strings in code replaced with English (proper i18n)
- **CI** — .ts/.qm build automation for all languages

## [1.8.5] — 2026-02-13

### Changed
- **Pre-translate** — show API error dialog with skip/continue/stop options
- **Pre-translate** — keep completed translations on cancel (don't discard)
- **Pre-translate** — progress dialog with ETA and cancel button

### Fixed
- **Lingva** — update dead `lingva.ml` URL to working `translate.plausibility.cloud` instance
- **i18n** — move pre-translate strings to correct `LinguaEditWindow` context
- **i18n** — fix context placement for 36 strings + add `update_translations.py`
- **i18n** — fix 4 missing `\n` in translations + add 12 new strings
- **i18n** — Redaktör → Redigerare (editor)
- **keystore** — remove `-T ''` flag from macOS Keychain storage (was blocking all apps)

## [1.8.4] — 2026-02-13

### Fixed
- **i18n** — translate 51 missing strings (menu accelerators, preferences, dialogs)
- **i18n** — fix 50 DeepL mistranslations (Error→"Gilla", Bold→"Boll", TMX→"Toronto-börsen", etc.)
- **i18n** — fix accelerator translations mangled by DeepL (`&` translated as "Och")
- **i18n** — wrap 2 OCR dialog strings in `self.tr()`

## [1.8.3] — 2026-02-13

### Changed
- **CI** — added `lrelease` step to compile translations in all GitHub Actions builds (macOS, Windows, Linux)

### Fixed
- **FFmpeg** — fix Windows pipe deadlock by draining stderr in background thread
- **FFmpeg** — search common Windows install paths (Chocolatey, Scoop, Program Files) when not on PATH

## [1.8.2] — 2026-02-13

### Changed
- **Video subtitle overlay** — rewritten to use QGraphicsView + QGraphicsVideoItem; subtitles are now actually visible on the video
- **Subtitle color logic** — yellow for translated or no-translations-yet, red only for untranslated when file has other translations
- **Video overlay resync** — overlay resyncs automatically after editing translations
- **Subtitle column widths** — 20% time / 40% source / 40% translation
- **Default columns** — auto-size for #/tags/status, equal stretch for source and translation
- **i18n** — 14 newly wrapped strings in `self.tr()`
- **Complete Swedish translation** — updated via DeepL (1,337 strings)
- **Mass operations** — subtitles case added to `_set_entry_translation`

## [1.8.1] — 2026-02-13

### Added
- **Complete Swedish translation** — expanded from 285 to 1,323 translated strings

### Changed
- **Video subtitle overlay** — shows only translation text in yellow; untranslated segments show source in red
- **Translation .qm files in git** — compiled translations now tracked in repository (previously gitignored)

### Fixed
- **macOS icon** — fixed icon display issues on macOS

## [1.8.0] — 2026-02-13

### Added
- **Live-update translation column** — tree view updates in real-time while typing
- **Extended selection** — Shift+click range and Ctrl+click multi-select in tree view
- **Resizable column headers** — all tree view columns can be resized by dragging
- **Incomplete subtitle warning** — warns when saving subtitle file with untranslated entries
- **Unity MonoBehaviour parser** — support for Unity localization tables with SharedData/TableData pattern

### Changed
- **Video preview rewrite** — 16:9 aspect ratio, full transport controls, subtitle overlay painted on video widget, volume control
- **Side panel auto-hide** — hides string info, TM, reference, context, preview when video dock is visible
- **Subtitle save fallback** — SRT/VTT save now falls back to source text when no translation exists (fixes roundtrip)
- Replaced `QThread` with daemon `threading.Thread` for machine translation (fixes SIGABRT crash)
- Disabled Qt accessibility on macOS to prevent SIGSEGV in `libqcocoa.dylib`
- Fixed `locale.getdefaultlocale()` deprecation warning for Python 3.13+

### Fixed
- **QThread crash** — proper cleanup of MT thread before creating new one
- **Subtitle overlay** — use child widget on QVideoWidget for reliable overlay display
- **Dark mode contrast** — MT Suggestions and context panel text now visible in dark mode
- **Save/Save As** — use Path objects consistently for file paths
- **Video subtitle extraction** — progress dialog no longer disappears; removed auto-copy source
- **Multi-selection crash** — fixed crash when selecting multiple entries
- **App icon** — fixed icon display on macOS and Windows
- **Swedish .qm translation** — now properly included in package
- **SubtitleEntry attributes** — fixed character counter and stats using wrong attribute names
- **Unity asset roundtrip** — fixed YAML parsing for Unity-specific tags and document format
- **SRT roundtrip** — fixed empty entries being dropped on save/reload cycle
- **Settings test** — target_language auto-detection from system locale

## [1.7.0] — 2026-02-11

### Added
- **Resizable source text view** — drag the splitter between source and translation to adjust heights
- Larger default source text area (150px vs 90px), supports up to 300px

## [1.6.0] — 2026-02-11

### Added
- **Save As toolbar button** — quick access to Save As directly from the main toolbar
- **TM matches marked fuzzy** — Translation Memory matches and quick TM actions now auto-mark entries as fuzzy until manually approved

### Changed
- All auto-applied translations (MT, TM, batch) consistently marked as fuzzy

## [1.5.0] — 2026-02-10

### Added
- **Save As…** (Ctrl+Shift+S) — file dialog with suggested filename and directory
- **Simple Mode** (Ctrl+Shift+L) — minimal UI: hides sidebar, context panel, minimap, quick actions toolbar

### Changed
- **Default sort: Untranslated first** — entries now sorted by status (untranslated → errors → fuzzy → translated) by default
- **Machine translation always marks fuzzy** — MT-applied entries are marked as "needs work" until manually approved

## [1.4.0] — 2026-02-10

### Added
- Save confirmation dialog when closing tabs with unsaved changes
- Scrollbars on comment and plural editor fields
- FFmpeg subtitle extraction now shows progress bar with cancel support
- FFmpeg error handling with user-friendly warning dialogs

### Fixed
- Fuzzy toggle button now works correctly for TS files (no longer auto-cleared on save)
- Fuzzy toggle button now works correctly for SDLXLIFF/MQXLIFF files (confirmed flag respects fuzzy state)
- Side panel can now be freely resized (removed maximum width constraint)
- FFmpeg timeout reduced from 120s to 30s for faster error recovery

### Changed
- Side panel minimum width reduced to 200px for more flexible layouts

## v1.3.2 — "Rock Solid" (2026-02-09)

### Bug Fixes
- Fuzzy toggle now works correctly for TS files (was using `entry.type` instead of `entry.translation_type`)
- FFmpeg subtitle extraction shows progress dialog instead of blank window
- FFmpeg extraction has timeout handling and error reporting

### Improvements
- Scrollbars on all text areas (source, translation, comment)
- Unsaved changes dialog when closing or opening new file
- Window geometry and splitter positions saved/restored via QSettings
- 90 unit tests added (parsers, linter, TM, settings, security)

### Known Issues
- Unity .asset parser doesn't handle `!u!` YAML tags

## v1.3.1 — "Polished & Translated" (2026-02-09)

### Bug Fixes
- Fixed TM autocomplete crash (`lookup_tm()` keyword argument mismatch)
- Fixed Concordance dialog crash (`Settings.get()` vs `get_value()`)
- Fixed AI Review crash with TS files (used PO-specific attributes)
- Fixed `pyside6-lupdate` missing strings inside f-strings

### Improvements
- Compile button shows visual status: green ✓ (success), red ✗ (error), neutral (not compiled)
- Compile icon resets to neutral when translation text is edited
- Modern rounded arrow icons for Undo/Redo (orange) and Previous/Next (blue chevrons)
- File open dialog remembers last used directory
- Swedish translation 100% complete (1257/1257 strings)
- 6 professional screenshots added to README and website

## 1.3.0 (2026-02-09) — Secure, Polished & Video-Ready

### Security
- **Cross-platform credential storage** — macOS Keychain, Windows Credential Locker, Linux Secret Service, AES-encrypted fallback
- **Security status in Preferences** — shows which backend is active with 🔒/⚠️ indicator

### Video & Subtitles
- **Auto video preview** — opening a subtitle file automatically shows the matching video
- **Extraction prompt with progress bar** — percentage-based progress when extracting subtitles from video
- **Editable timestamps** — subtitle time intervals as a dedicated editable column
- **Non-modal preview** — video plays alongside the editor

### Bug Fixes
- **Fuzzy click fixed** — column index mismatch (was writing to col 3 instead of col 5)
- **Fuzzy toggle for TS/XLIFF** — now works for all file formats, not just PO

### Packaging
- **Ubuntu 25.10 compatible** — removed python3-pyside6 dependency, improved postinst with pip fallbacks
- **Better install docs** — separate sections for Linux, macOS, and Windows

## 1.2.1 (2026-02-09) — Full Swedish Translation

### Updated
- Swedish translation: **100% coverage** (1023 strings)
- Updated POT template with all extractable strings
- File type associations for macOS and Linux (.desktop + MIME XML)

## 1.2.0 (2026-02-09) — The Translator's Dream

### Editor & UX
- **Zen Translation Mode** (Ctrl+Shift+Z) — distraction-free source → translation workflow
- **Horizontal layout toggle** — editor on right or below (View menu)
- **Inline MT suggestions** — DeepL/OpenAI suggestions appear as you translate
- **Spell check** — red wavy underlines with suggestions and custom dictionary
- **Poedit-style shortcuts** — Alt+Enter (next untranslated), Ctrl+Shift+Up/Down (prev/next fuzzy)
- **Tab navigation flow** — Tab saves and moves to next, Ctrl+Enter to next untranslated
- **Save flash animation** — green border flash confirming save
- **Colored entry borders** — red (untranslated), orange (fuzzy), green (translated)
- **Auto-collapsing side panel** — hides when empty, thin tab bar when collapsed
- **Context-aware toolbar** — right-click to customize, overflow menu for less-used actions
- **Dark theme** — comprehensive 200-line QSS dark theme
- **"Reviewed" status filter** — filter entries by review status

### File Formats
- **SDLXLIFF** (Trados) parser with segment definitions and confirmation status
- **MQXLIFF** (memoQ) parser with namespace detection and segment properties
- **File type associations** — double-click .po/.ts/.xliff etc. to open in LinguaEdit (macOS + Linux)

### Tools
- **Project Dashboard** (Ctrl+D) — per-language progress bars, pie/bar charts, CSV export
- **Git-based diff** (Ctrl+Shift+D) — compare with previous commits, detect outdated translations
- **Batch Machine Translate** (Ctrl+Alt+T) — one-click MT for all untranslated with preview

## 1.1.0 (2026-02-09) — Video Subtitle Extraction

### Added
- **FFmpeg video subtitle extraction** — extract subtitles from video files (.mkv, .mp4, .avi, etc.)
- **FFmpeg missing dialog** — user-friendly dialog when FFmpeg is not installed, with options to get install info, browse manually, retry, or cancel
- **Video subtitle stream selection** — pick which subtitle track to extract from multi-stream videos
- **Enhanced sidebar** — large icons for better navigation and visibility
- **Increased Source/Translation margins** — more readable editing area

## 1.0.0 (2026-02-08) — The Everything Release

LinguaEdit 1.0.0 marks a major milestone with 55+ new features, 15+ supported file formats, and comprehensive translation tools for professionals and hobbyists alike.

### 🎯 Editor Enhancements
- **Search & Replace (Ctrl+H)** with regex support, case sensitivity, and whole word matching
- **Translation Memory (SQLite)** with fuzzy matching and auto-learning from your translations
- **Batch editing (Ctrl+Shift+B)** for bulk fuzzy fixes and search/replace across all entries
- **Autocomplete from TM suggestions** speeds up repetitive translation work
- **Inline editing** - double-click any entry in the list to edit directly
- **Plural forms editor** with CLDR rules for proper localization
- **Translator comments editing** for better context and collaboration
- **Propagate identical translations** across entries with same source text
- **Focus mode (Ctrl+Shift+F)** shows only untranslated or fuzzy entries
- **Fullscreen mode (F11)** for distraction-free translation
- **Syntax highlighting** for HTML tags, format strings, and escape sequences
- **Drag & drop files** for quick opening

### ✅ Quality Assurance
- **Glossary system** with consistency checking across your project
- **Enhanced linter** detecting HTML tag mismatches, missing accelerator keys, duplicates, case mismatches, CLDR validation, and number localization issues  
- **AI Review (Ctrl+Shift+A)** with offline heuristic fallback for quality scoring
- **Confidence score** per translation entry with visual indicators
- **Back-translation verification** to catch meaning drift
- **Regex tester** for format string validation
- **Layout simulator** with pixel width checking for UI text
- **Unicode inspector** for character encoding issues

### 📊 Reports & Statistics
- **HTML/PDF reports** with quality scores, progress charts, and detailed metrics
- **Statistics dialog (Ctrl+I)** with word counts, character counts, and completion rates
- **Burndown chart** showing translation progress over time
- **Locale map** - world map visualization with translation status by region

### 📁 File Format Support
- **PO (gettext)** - GNU gettext portable object files
- **TS (Qt Linguist)** - Qt translation source files  
- **XLIFF** - XML Localization Interchange File Format
- **JSON** - Generic JSON translation files
- **YAML** - YAML-based translation files
- **Android XML** - Android string resources
- **ARB** - Application Resource Bundle (Flutter/Dart)
- **PHP** - PHP array-based translation files
- **Apple .strings/.stringsdict** - iOS/macOS localization files
- **Unity .asset** - Unity game engine localization
- **RESX (.NET)** - Microsoft .NET resource files
- **Java .properties** - Java properties files
- **Chrome i18n JSON** - Chrome extension localization
- **Godot .csv/.tres** - Godot game engine translation files
- **Subtitles .srt/.vtt** - Subtitle file support
- **TMX import/export** - Translation Memory eXchange format

### 🔄 Integration & Workflow
- **Weblate/Transifex/Crowdin sync** for cloud-based translation platforms
- **Git integration** - commit and push directly from the application
- **Email translations** to Translation Project coordinator
- **Gettext msgmerge** integration for updating translation files
- **Source code context** from local files or GitHub repositories
- **OCR screenshot text extraction** for translating UI elements

### 🔖 Workflow & Productivity
- **Bookmarks (Ctrl+B, F2)** for marking important entries and quick navigation
- **Tags and filters** per entry for custom organization
- **Review mode** with approve/reject workflow for translation teams
- **Macro recording/playback** for automating repetitive tasks
- **Pomodoro timer** built-in for focused translation sessions
- **Watch mode** - auto-reload files when changed externally
- **Quick actions (Ctrl+.)** for common operations
- **Pinned entries** - keep important translations visible

### 🎨 Customization & Themes
- **5 beautiful themes**: Light, Dark, Solarized Dark, Nord, and Monokai
- **Plugin system** (`~/.local/share/linguaedit/plugins/`) for custom extensions
- **Character counter** with configurable length limits
- **TTS preview** - hear your translations spoken aloud
- **Gamification system** with achievements and progress tracking
- **File header editor (Ctrl+Shift+H)** for metadata management
- **Project view (Ctrl+Shift+O)** for multi-file project management
- **Preview panel** showing formatted output
- **Minimap** for quick navigation in large files
- **Diff view (Ctrl+D)** comparing source and target languages

### 🛠️ Technical Improvements
- **Performance optimizations** for large translation files (10,000+ entries)
- **Memory usage improvements** with lazy loading and caching
- **Crash recovery** with auto-save and session restore
- **Export optimizations** for faster file generation
- **Database indexing** for faster Translation Memory searches
- **Multi-threading** for non-blocking UI operations

### 🌍 Localization
- **Swedish translation** - Native svenska språkstöd
- **German translation** - Deutsche Übersetzung (partial)
- **French translation** - Traduction française (partial) 
- **Spanish translation** - Traducción en español (partial)
- **Right-to-left (RTL) support** for Arabic, Hebrew, and other RTL languages

### 🐛 Bug Fixes
- Fixed memory leaks in large file processing
- Resolved Unicode handling issues in file saving
- Fixed crash when opening corrupted translation files  
- Improved error handling for network operations
- Fixed search highlighting in dark themes
- Resolved export formatting issues for various file types
- Fixed keyboard shortcuts in macOS
- Improved file locking to prevent data corruption
- Fixed drag and drop on Windows and Linux
- Resolved Qt6 compatibility issues

### 🔧 Infrastructure  
- **CI/CD pipeline** with automated testing and building
- **Cross-platform builds** for Windows, macOS, and Linux
- **Flatpak packaging** for Linux distributions
- **Windows installer** with proper uninstall support
- **macOS app bundle** with code signing
- **AppImage support** for universal Linux compatibility

---

**Migration from 0.8.x**: This release includes automatic migration of settings and translation memories. Your existing projects will be upgraded seamlessly.

**Breaking Changes**: Plugin API has been updated - plugins written for 0.8.x will need minor updates.

**Download**: Available on GitHub Releases, Flathub, and package managers.

**Contributors**: Special thanks to all beta testers and translators who helped make this release possible.

---

*Total additions since v0.8.0: 55+ features, 15+ file formats, 12 languages, 1,000+ commits*