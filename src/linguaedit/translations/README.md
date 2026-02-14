# Translations

LinguaEdit uses Qt's translation system (`.ts` files) and [Transifex](https://app.transifex.com/danielnylander/linguaedit/) for community translations.

## Current Status

| Language | Code | Status |
|----------|------|--------|
| English | `en` | ✅ Source language |
| Swedish | `sv` | ✅ 100% |

More languages are available on Transifex — contributions welcome!

## How to Contribute

### Via Transifex (recommended)

The easiest way to contribute translations:

1. Go to [app.transifex.com/danielnylander/linguaedit](https://app.transifex.com/danielnylander/linguaedit/)
2. Sign up / log in and request to join your language
3. Translate strings in the web editor — no tools needed
4. Translations are synced to this repo daily via GitHub Actions

### Via Pull Request

If you prefer working locally:

1. **Copy the template:**
   ```bash
   cp linguaedit_template.ts linguaedit_LANG.ts
   ```
   Replace `LANG` with your locale code (e.g., `de`, `fr`, `ja`, `zh_CN`).

2. **Translate the strings** using one of:
   - [Qt Linguist](https://doc.qt.io/qt-6/linguist-translators.html) (recommended)
   - [LinguaEdit](https://github.com/yeager/linguaedit) itself!
   - Any text editor (`.ts` files are XML)

3. **Submit a Pull Request** with your `linguaedit_LANG.ts` file

## Translation Guidelines

- Use **formal language** — avoid informal "you" where possible
- Keep keyboard shortcuts (e.g., `&File`) — the `&` marks the accelerator key
- Preserve format specifiers like `%1`, `%s`, `{name}`
- Don't translate technical terms that are universally understood (e.g., "XLIFF", "UTF-8")
- When in doubt, check how established software (Firefox, LibreOffice) translates the term

## How It Works

- **Source strings** are extracted from Python code into `linguaedit_template.ts`
- **Transifex** hosts the translation platform with 18 languages configured
- **GitHub Actions** syncs translations daily (pull from Transifex → commit `.ts` files)
- **CI** compiles all `.ts` → `.qm` on every build
- **LinguaEdit** auto-discovers available `.qm` files and shows them in the language picker with flags

## Compiling Translations

After editing locally, compile `.ts` → `.qm`:

```bash
pyside6-lrelease linguaedit_LANG.ts -qm linguaedit_LANG.qm
```

## Template

`linguaedit_template.ts` contains all 1,487 source strings. It is regenerated before each release using:

```bash
find src/linguaedit -name "*.py" | sort | xargs pyside6-lupdate -ts translations/linguaedit_template.ts
```
