# Supported Formats

LinguaEdit supports eight translation file formats. Each format is parsed and saved using a dedicated parser that preserves file structure and metadata.

## PO / POT (GNU gettext)

- **Extensions:** `.po`, `.pot`
- **Features:** Full metadata editing, plural forms (nplurals), translator comments, extracted comments, references, flags, fuzzy state, previous msgid
- **Compilation:** PO → MO via `polib` or `msgfmt`

PO is the most feature-rich format in LinguaEdit. All entry metadata (context, references, flags, comments) is displayed in the String Info panel.

## Qt TS (XML)

- **Extension:** `.ts`
- **Features:** Context names, source locations (file:line), comments, translation type (unfinished/vanished), numerus forms
- **Compilation:** TS → QM via `pyside6-lrelease` or `lrelease`

## XLIFF 1.2 / 2.0

- **Extensions:** `.xliff`, `.xlf`
- **Features:** Translation unit IDs, notes, state attributes (new/translated/final), source and target language metadata

XLIFF is the OASIS standard for localisation interchange. LinguaEdit supports both version 1.2 and 2.0.

## JSON (Flat and Nested)

- **Extension:** `.json`
- **Features:** Flat key-value pairs and nested structures

JSON i18n files are commonly used in web applications (e.g., i18next, react-intl). Keys are displayed in the Context field of the String Info panel.

## YAML

- **Extensions:** `.yml`, `.yaml`
- **Features:** Root key detection, nested key support

YAML i18n files are used by frameworks such as Ruby on Rails. The root key (typically a locale code) is editable via the metadata dialog.

## Android XML (strings.xml)

- **Extension:** `.xml`
- **Features:** String resources with `name` attributes, XML comments

LinguaEdit detects Android string resource files and parses `<string>` elements. Comments above entries are preserved.

## Flutter ARB (Application Resource Bundle)

- **Extension:** `.arb`
- **Features:** Key-value pairs, `@key` metadata (description, placeholders), locale attribute

ARB files are the standard localisation format for Flutter/Dart applications.

## PHP Arrays

- **Extension:** `.php`
- **Features:** Associative array key-value pairs

PHP translation files using `return ['key' => 'value']` syntax are supported. This format is used by frameworks such as Laravel.

## Opening Files

All supported formats can be opened via:

- **File → Open** (Ctrl+O)
- Drag and drop onto the window
- Command line: `linguaedit path/to/file.ext`

The format is detected automatically from the file extension.
