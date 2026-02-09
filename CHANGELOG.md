# CHANGELOG

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