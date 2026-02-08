# Editing Translations

## Interface Layout

LinguaEdit follows a layout inspired by POedit and Qt Linguist:

```
┌─────────────────────────────────────────────────────────────┐
│ Menu bar                                                     │
│ Toolbar                                                      │
├─────────────────────────────────────────────────┬───────────┤
│ Entry table (source | translation | status)     │ TM / Side │
│                                                 │ panel     │
├─────────────────────────────────────────────────┤           │
│ Source (read-only)                              │           │
│ Translation (editable)                          │           │
│ [Needs work] checkbox                           │           │
├─────────────────────────────────────────────────┴───────────┤
│ Status bar                                                   │
└─────────────────────────────────────────────────────────────┘
```

## Opening Files

Use any of the following methods:

- **File → Open** (Ctrl+O)
- Drag and drop a file onto the window
- Pass a file path on the command line: `linguaedit file.po`
- Select from **File → Recent Files**

Multiple files can be open simultaneously in separate tabs.

## Translating Entries

1. Select an entry in the table. The source text appears in the read-only panel above, and the translation editor below.
2. Type your translation in the editor.
3. Press **Ctrl+Enter** to save the current entry and advance to the next one.

### Marking Entries as Fuzzy

Check the **Needs work** checkbox (or press Ctrl+U) to mark an entry as fuzzy. Fuzzy entries are highlighted in the table and excluded from the "translated" count.

### Copying Source Text

Press **Ctrl+B** or click **Copy Source** to copy the source text into the translation editor. This is useful as a starting point for editing.

### Plural Forms

For PO files with plural forms, LinguaEdit displays separate tabs for each plural form (`msgstr[0]`, `msgstr[1]`, etc.).

## Filtering and Searching

### Filter by Status

Use the filter dropdown above the entry table to display:

- All strings
- Untranslated only
- Fuzzy / Needs work only
- Translated only
- Strings with warnings

### Search

Type in the search field to filter entries by source or translation text.

### Search and Replace

Press **Ctrl+H** to open the search and replace panel. Supports plain text and regular expressions.

## Sorting

Use the sort dropdown to reorder entries by:

- File order (default)
- Source text (A→Z or Z→A)
- Translation text (A→Z or Z→A)
- Status (untranslated first)
- Length
- Reference

## Saving

Press **Ctrl+S** or click the **Save** button. LinguaEdit writes back to the original file format.

If **Auto-compile on save** is enabled in Preferences, the file is also compiled automatically (PO→MO, TS→QM).

## Compiling

Use **Catalog → Compile translation** (Ctrl+Shift+B) to compile:

- **PO files** → `.mo` (requires `polib` or `msgfmt`)
- **TS files** → `.qm` (requires `pyside6-lrelease` or `lrelease`)

## Undo and Redo

LinguaEdit maintains per-entry undo/redo stacks:

- **Undo** — Ctrl+Z
- **Redo** — Ctrl+Shift+Z (or Ctrl+Y)

## File Monitoring

If the file is modified externally, LinguaEdit detects the change and reloads it automatically.
