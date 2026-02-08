# LinguaEdit User Guide

## Opening Files

LinguaEdit supports multiple translation file formats:

- **PO/POT** — GNU gettext format, the most common in open source
- **TS** — Qt Linguist XML format
- **JSON** — Flat or nested key-value JSON (used by i18next, react-intl, etc.)

Click the **Open** button or pass a file path as argument:

```bash
linguaedit translations/sv.po
```

## Editing Translations

1. Select an entry from the left panel
2. The source string appears in the top-right (read-only)
3. Type your translation in the bottom text area
4. Toggle **Fuzzy** if the translation needs review
5. Click **Save** (or Ctrl+S) to write changes

## Pre-Translation

LinguaEdit supports four translation engines:

| Engine    | Cost | API Key Required |
|-----------|------|-----------------|
| Lingva    | Free | No              |
| MyMemory  | Free | No (email optional) |
| OpenAI    | Paid | Yes             |
| Anthropic | Paid | Yes             |

- **Single entry:** Click "Pre-translate" below the editor
- **All untranslated:** Menu → Pre-translate all

## Linting & Quality Score

Menu → **Lint file** runs checks on all entries:

- Missing translations
- Fuzzy entries
- Format specifier mismatches (`%s`, `{0}`, etc.)
- Whitespace inconsistencies
- Punctuation mismatches
- Suspicious length ratios

The quality score (0–100%) reflects how clean the file is.

## Spell Checking

Click **Spell check** to check the current translation for spelling errors.
Requires PyEnchant and dictionaries for your target language.

```bash
# macOS
brew install enchant

# Install dictionaries
# Swedish: aspell-sv or hunspell-sv
```

## Metadata

Menu → **File metadata** shows PO header fields:

- `Last-Translator`
- `PO-Revision-Date`
- `Language-Team`
- `Content-Type`
- etc.

For TS files, shows language and source language.

## GitHub PR Workflow

Menu → **GitHub PR** enables you to:

1. Enter your GitHub personal access token
2. Specify the repo (owner/repo)
3. LinguaEdit fetches the latest POT file
4. Creates a branch with your translation
5. Opens a pull request

## Platform Integration

LinguaEdit can interact with:

- **Transifex** — list resources, download/upload translations
- **Weblate** — list translations, download/upload files
- **Crowdin** — list files, download builds

Configure API tokens in each platform's settings.

## Updates

On macOS and Windows, Menu → **Check for updates** queries GitHub Releases.
On Linux, use your package manager.
