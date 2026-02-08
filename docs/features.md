# Features

## Inline Linting and Quality Score

LinguaEdit performs real-time quality checks as you type:

- **Format specifier validation** — Ensures printf-style (`%s`, `%d`) and Python-style (`{0}`, `{name}`) placeholders match between source and translation
- **Whitespace checks** — Detects leading/trailing whitespace mismatches
- **Newline count** — Warns if the number of newlines differs
- **Punctuation consistency** — Checks that ending punctuation (`.!?:;`) matches
- **Length ratio** — Flags suspiciously short or long translations

Run a full validation with **Catalog → Validate (Lint)** (Ctrl+Shift+V) to see the overall quality score.

## Pre-Translation

Translate untranslated entries automatically using one of the supported engines:

### Free Engines
- **Lingva Translate** — No API key required
- **MyMemory** — No API key required

### Paid Engines (API Key Required)
- **OpenAI** (GPT-4o-mini, etc.)
- **Anthropic** (Claude)
- **DeepL**
- **Google Cloud Translation**
- **Microsoft Translator**
- **Amazon Translate**

### Additional Engines
- **HuggingFace (NLLB)** — Open-source neural translation
- **LibreTranslate** — Self-hosted option

Configure engines via **Catalog → Pre-translate** (Ctrl+Shift+T) or manage API keys in the pre-translate dialog.

## Translation Memory (TM)

LinguaEdit maintains a local translation memory that stores previously translated pairs:

- **Automatic learning** — Translations are added to TM as you work
- **Fuzzy matching** — Suggestions appear in the side panel with similarity scores
- **Concordance search** — Search the entire TM database from the side panel
- **Bulk import** — Use **Catalog → Feed file to TM** to import all translations from a file

## Glossary Manager

Maintain project-specific glossaries for consistent terminology:

- **Add terms** — Define source → target term pairs
- **Glossary check** — Validate that glossary terms are used correctly throughout the file
- **Enforcement** — Violations are reported in the QA report

Access via **Catalog → Quality → Glossary**.

## QA Profiles

Apply predefined quality assurance rule sets:

- **Formal** — Checks for formal language conventions
- **Informal** — Checks for informal/casual language

Access via **Catalog → Quality → QA Profile**.

## Spell Checking

Built-in spell checking powered by PyEnchant:

- Press **F7** to check the current entry
- Suggestions are displayed inline

Requires `enchant` to be installed on your system.

## Translation Reports

Generate detailed HTML reports with:

- Translation statistics (total, translated, fuzzy, untranslated)
- Progress bar
- Quality score
- Lint issues
- Glossary violations

Export via **Catalog → Quality → Export report**.

## Platform Integration

### Transifex
- Pull and push translations via Transifex API v3
- Configure in **Platforms → Platform settings**

### Weblate
- Pull and push translations via Weblate REST API
- Configure in **Platforms → Platform settings**

### Crowdin
- Pull and push files via Crowdin API v2
- Configure in **Platforms → Platform settings**

### GitHub PR Workflow
- Fetch POT files from repositories
- Create branches, push translations, and open pull requests

## Git Integration

Built-in Git support accessible from the **Git** menu:

- **Status** — View modified, staged, and untracked files
- **Diff** — Side-by-side comparison of changes
- **Commit** — Stage and commit translation changes
- **Switch branch** — View and switch between branches

## Tabbed Editing

Open multiple translation files simultaneously in separate tabs. Each tab maintains its own:

- Undo/redo history
- Filter and sort settings
- Current entry position

## Drag and Drop

Drop translation files directly onto the LinguaEdit window to open them.

## Compare Language / Split View

Open a reference file (**View → Compare language**) to see translations from another language side by side.

## Auto-Propagate

Use **View → Auto-propagate** to automatically copy translations to all entries with identical source text.

## Consistency Check

**Catalog → Quality → Consistency check** identifies entries where the same source text has been translated differently.

## File Metadata Editor

View and edit file header metadata via **Catalog → File metadata**:

- PO: All header fields (Last-Translator, Language-Team, etc.)
- TS: Language and source language
- XLIFF: Version, source and target languages
- ARB: Locale
- YAML: Root key

## Themes

Choose between system default, light, and dark themes via **View → Theme**.

## In-App Updates

Automatic update checking on macOS and Windows. Check manually via **Help → Check for updates**.

## Secure Key Storage

API keys are stored securely in the platform keyring:

- **macOS** — Keychain
- **Linux** — libsecret (GNOME Keyring, KDE Wallet)
- **Fallback** — Basic obfuscation if no keyring is available
