# Translations

LinguaEdit uses Qt's translation system (`.ts` files).

## Current Languages

| Language | File | Status |
|----------|------|--------|
| Swedish (sv) | `linguaedit_sv.ts` | ✅ Maintained |

## How to Contribute a Translation

1. **Copy the template:**
   ```bash
   cp linguaedit_template.ts linguaedit_LANG.ts
   ```
   Replace `LANG` with your language code (e.g., `de`, `fr`, `ja`, `zh_CN`).

2. **Translate the strings** using one of:
   - [Qt Linguist](https://doc.qt.io/qt-6/linguist-translators.html) (recommended)
   - [LinguaEdit](https://github.com/yeager/linguaedit) itself!
   - Any text editor (`.ts` files are XML)

3. **Submit a Pull Request** with:
   - Your `linguaedit_LANG.ts` file
   - Add your language to the table above

## Translation Guidelines

- Use **formal language** — avoid informal "you" where possible
- Keep keyboard shortcuts (e.g., `&File`) — the `&` marks the accelerator key
- Preserve format specifiers like `%1`, `%s`, `{name}`
- Don't translate technical terms that are universally understood (e.g., "XLIFF", "UTF-8")
- When in doubt, check how established software (Firefox, LibreOffice) translates the term in your language

## Compiling Translations

After editing, compile `.ts` → `.qm`:

```bash
pyside6-lrelease linguaedit_LANG.ts -qm linguaedit_LANG.qm
```

## Template

`linguaedit_template.ts` contains all extractable strings from the source code. It is regenerated before each release using:

```bash
find src/linguaedit -name "*.py" | sort | xargs pyside6-lupdate -ts translations/linguaedit_template.ts
```
