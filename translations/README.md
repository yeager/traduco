# Translating LinguaEdit 🌍

Want to help translate LinguaEdit into your language? Awesome!

## How to contribute

1. **Copy the template:**
   ```bash
   cp linguaedit_template.ts linguaedit_XX.ts
   ```
   Replace `XX` with your [language code](https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes) (e.g. `de`, `fr`, `ja`, `pt_BR`).

2. **Translate** using one of:
   - **LinguaEdit itself** — open your `.ts` file and start translating!
   - **Qt Linguist** — `linguist linguaedit_XX.ts`
   - Any text editor (it's XML)

3. **Compile** (optional — we'll do this before release):
   ```bash
   pyside6-lrelease linguaedit_XX.ts -qm linguaedit_XX.qm
   ```

4. **Submit a PR** with your `.ts` file.

## Current translations

| Language | Code | Status |
|----------|------|--------|
| Swedish  | `sv` | ✅ Complete (590/590) |

## Guidelines

- Use **formal language** (e.g. Swedish "Visa" not "Kolla")
- Keep keyboard shortcuts (& accelerators) intact
- Preserve `%s`, `%d`, `{0}` format placeholders exactly
- Test your translations if possible: `LANGUAGE=xx linguaedit`

## Files

- `linguaedit_template.ts` — Empty template with all 590 strings
- `linguaedit_sv.ts` — Swedish (reference translation)

## Questions?

Open an issue or reach out at https://github.com/yeager/linguaedit/issues
