# LinguaEdit API Reference

## Parsers

### `linguaedit.parsers.po_parser`

- `parse_po(path) → POFileData` — Parse a PO/POT file
- `save_po(data, path=None)` — Save a PO file
- `POFileData` — entries, metadata, translated_count, percent_translated
- `TranslationEntry` — msgid, msgstr, flags, fuzzy, occurrences

### `linguaedit.parsers.ts_parser`

- `parse_ts(path) → TSFileData` — Parse a Qt TS file
- `save_ts(data, path=None)` — Save a TS file
- `TSEntry` — source, translation, context_name, translation_type

### `linguaedit.parsers.json_parser`

- `parse_json(path) → JSONFileData` — Parse a JSON i18n file
- `save_json(data, path=None)` — Save a JSON file
- Supports flat and nested key-value structures

## Services

### `linguaedit.services.linter`

- `lint_entries(entries) → LintResult` — Lint translation entries
- `LintResult` — issues, score, error_count, warning_count

### `linguaedit.services.translator`

- `translate(text, engine, **kwargs) → str` — Translate text
- Engines: `lingva`, `mymemory`, `openai`, `anthropic`

### `linguaedit.services.spellcheck`

- `check_text(text, language) → list[SpellIssue]`
- `available_languages() → list[str]`

### `linguaedit.services.github`

- `fetch_pot_file(config, pot_path, branch) → str`
- `create_branch(config, branch_name, from_branch)`
- `push_file(config, file_path, content, branch, message)`
- `create_pull_request(config, title, body, head, base) → str`

### `linguaedit.services.platforms`

- Transifex: `transifex_list_resources`, `transifex_download`
- Weblate: `weblate_list_translations`, `weblate_download`, `weblate_upload`
- Crowdin: `crowdin_list_files`, `crowdin_download_build`

### `linguaedit.services.updater`

- `check_for_updates() → Optional[dict]` — Check GitHub releases (skips Linux)
