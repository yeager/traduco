# Frequently Asked Questions

## General

### What platforms does LinguaEdit run on?

LinguaEdit runs on Linux, macOS, and Windows — anywhere Python 3.10+ and PySide6 are available.

### Is LinguaEdit free?

Yes. LinguaEdit is free software released under the GPL-3.0-or-later license. You can use, modify, and distribute it freely.

### How do I report a bug?

Open an issue on [GitHub](https://github.com/yeager/linguaedit/issues).

## Translation

### Which pre-translation engines are free?

**Lingva Translate** and **MyMemory** require no API key and are free to use. All other engines (OpenAI, Anthropic, DeepL, Google Cloud, Microsoft, Amazon, HuggingFace, LibreTranslate) require an API key and may incur costs.

### Where are API keys stored?

API keys are stored in your platform's secure keyring:

- **macOS:** Keychain
- **Linux:** libsecret (GNOME Keyring or KDE Wallet)
- **Fallback:** If no keyring is available, keys are stored with basic obfuscation in the configuration directory

### How does Translation Memory work?

LinguaEdit maintains a local TM database. As you translate, source–target pairs are saved automatically. When you open a new entry, the TM panel shows fuzzy matches from previous translations. You can also bulk-import translations using **Catalog → Feed file to TM**.

### Can I translate multiple files at once?

Yes. LinguaEdit supports tabbed editing — open multiple files in separate tabs and switch between them freely.

## File Formats

### My JSON file uses nested keys. Is that supported?

Yes. LinguaEdit's JSON parser handles both flat and nested key structures.

### Can I compile PO files to MO?

Yes. Use **Catalog → Compile translation** (Ctrl+Shift+B). This requires either the `polib` Python package or `msgfmt` (part of GNU gettext) to be installed.

### Can I compile TS files to QM?

Yes. Use **Catalog → Compile translation** (Ctrl+Shift+B). This requires `pyside6-lrelease` or `lrelease` to be installed.

## Platform Integration

### How do I connect to Transifex / Weblate / Crowdin?

Go to **Platforms → Platform settings** and enter your API credentials. Use the **Test Connection** button to verify the configuration, then **Save**.

### How do I pull or push translations?

Use the **Platforms → Pull from…** or **Platforms → Push to…** menus. Select a resource and language in the sync dialog.

## Troubleshooting

### Spell checking does not work

Ensure that `enchant` is installed on your system:

- **macOS:** `brew install enchant`
- **Ubuntu/Debian:** `sudo apt install libenchant-2-dev`
- **Fedora:** `sudo dnf install enchant2-devel`

Then install the Python bindings: `pip install pyenchant`.

### The application looks wrong on HiDPI displays

PySide6 supports HiDPI scaling natively. If you experience issues, try setting the environment variable:

```bash
export QT_SCALE_FACTOR=1.5
```

### File monitoring triggers unexpected reloads

LinguaEdit watches the open file for external changes. If another tool modifies the file frequently, the editor may reload. This behaviour is by design to keep the editor in sync with the file on disk.
