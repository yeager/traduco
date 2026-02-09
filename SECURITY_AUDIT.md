# LinguaEdit Security Audit Report

**Date:** 2026-02-09
**Auditor:** BOSSe (AI-assisted security review)
**Scope:** Full codebase (~27,000 lines Python, PySide6/Qt6)
**Version:** 1.3.0

---

## Executive Summary

LinguaEdit is a well-structured desktop application with generally good security practices. The codebase avoids many common pitfalls (no `eval()`, no `pickle`, no `shell=True`, YAML uses `safe_load`). However, several issues were found, primarily around XML parsing and the fallback credential storage.

**Fixed in this audit:** 1 Critical, 1 High issue.

---

## Findings

### 🔴 CRITICAL — CVE-class

#### 1. XXE (XML External Entity) in All XML Parsers
- **Status:** ✅ FIXED (commit `0b59599`)
- **Severity:** Critical
- **Type:** Actual vulnerability
- **Files affected:**
  - `src/linguaedit/parsers/xliff_parser.py:89` — `ET.parse()` without XXE protection
  - `src/linguaedit/parsers/sdlxliff_parser.py:109` — same
  - `src/linguaedit/parsers/mqxliff_parser.py:139` — same
  - `src/linguaedit/parsers/resx.py:48` — same
  - `src/linguaedit/parsers/android_parser.py:77` — same
  - `src/linguaedit/parsers/ts_parser.py:68` — same
  - `src/linguaedit/services/tmx.py:89,177,232` — same
- **Description:** All XML parsers used `xml.etree.ElementTree.parse()` without disabling external entity resolution. A crafted XLIFF/SDLXLIFF/MQXLIFF/RESX/Android XML/TS/TMX file could:
  - Read arbitrary local files (e.g., `~/.ssh/id_rsa`, `/etc/passwd`)
  - Cause denial of service via billion laughs (entity expansion bomb)
  - Potentially trigger SSRF via external HTTP entity references
- **Attack vector:** User opens a malicious translation file received from a client or downloaded from a platform
- **Fix:** Created `safe_parse_xml()` in `parsers/__init__.py` that configures expat to disable parameter entity parsing and external entity resolution. All XML parsers now use this function.
- **Recommendation:** Consider adding `defusedxml` to dependencies for defense-in-depth.

---

### 🟠 HIGH

#### 2. Plugin System Executes Arbitrary Code Without Verification
- **Status:** ✅ PARTIALLY FIXED (commit `0b59599`)
- **Severity:** High
- **Type:** Actual vulnerability (by design, but needs guardrails)
- **File:** `src/linguaedit/services/plugins.py:123`
- **Description:** The plugin system loads and executes arbitrary `.py` files from `~/.local/share/linguaedit/plugins/`. Any file placed there runs with full user privileges. There is no signature verification, sandboxing, or user consent prompt.
- **Fix applied:** Added path traversal guard to prevent loading plugins from outside the plugin directory.
- **Remaining risk:** A malicious plugin placed in the correct directory still executes without warning.
- **Recommendation:**
  1. Show a confirmation dialog when loading new/modified plugins
  2. Display plugin hash/fingerprint for verification
  3. Consider a plugin manifest with author signatures
  4. Log all plugin loads

#### 3. Legacy XOR "Encryption" Fallback in Keystore
- **Severity:** High
- **Type:** Actual vulnerability
- **File:** `src/linguaedit/services/keystore.py:290-310`
- **Description:** The legacy XOR fallback (`_legacy_fallback_load`, `_legacy_fallback_save`, `_xor_bytes`) uses a predictable machine-specific key (`platform.node() + USER` → SHA256). This is **not encryption** — it's trivially reversible obfuscation. The key is deterministic from publicly available machine info.
  - The primary Fernet fallback (PBKDF2 with 480,000 iterations + random salt) is solid.
  - But if `cryptography` is not installed, the legacy XOR path is used, storing secrets with zero real protection.
- **Recommendation:**
  1. Make `cryptography` a required dependency (not optional)
  2. Remove the legacy XOR code path entirely, or at minimum show a strong warning
  3. Add migration: on first run with `cryptography` available, re-encrypt any legacy XOR secrets

---

### 🟡 MEDIUM

#### 4. SSRF via User-Configurable LibreTranslate Instance URL
- **Severity:** Medium
- **Type:** Actual vulnerability
- **File:** `src/linguaedit/services/translator.py:72`
- **Description:** `translate_libretranslate()` accepts an `instance` parameter for the LibreTranslate URL. If the user (or a crafted config) sets this to an internal URL (e.g., `http://169.254.169.254/` for cloud metadata, or `http://localhost:8080/admin`), the app will make HTTP requests to it.
- **Recommendation:** Validate the URL scheme (HTTPS only) and block RFC 1918 / link-local addresses. Add a URL allowlist or warning in preferences.

#### 5. Temp Files Not Always Cleaned Up
- **Severity:** Medium
- **Type:** Best practice
- **Files:**
  - `src/linguaedit/ui/video_subtitle_dialog.py:376` — `NamedTemporaryFile(delete=False)` without guaranteed cleanup
  - `src/linguaedit/ui/ocr_dialog.py:64` — same
  - `src/linguaedit/ui/sync_dialog.py:208` — same
  - `src/linguaedit/ui/diff_dialog.py:689` — cleaned up in finally block ✅ (line 710)
- **Description:** Several temp files are created with `delete=False` but not consistently cleaned up in `finally` blocks. If the process crashes between creation and cleanup, sensitive translation content remains in `/tmp`.
- **Recommendation:** Use `try/finally` with `os.unlink()` in all cases, or use context managers.

#### 6. QInputDialog for Master Password Shows Plaintext
- **Severity:** Medium
- **Type:** Best practice / UX security
- **File:** `src/linguaedit/services/keystore.py:255`
- **Description:** The master password prompt uses `QInputDialog.getText()` which shows the password in cleartext. Should use `QInputDialog.getText()` with `QLineEdit.Password` echo mode.
- **Recommendation:** Add `QLineEdit.Password` echo mode parameter:
  ```python
  from PySide6.QtWidgets import QLineEdit
  password, ok = QInputDialog.getText(
      None, _("Master Password"), prompt,
      QLineEdit.Password  # Add this parameter
  )
  ```

---

### 🟢 LOW

#### 7. No HTTP Request Timeout Validation on Retry
- **Severity:** Low
- **Type:** Best practice
- **File:** `src/linguaedit/services/translator.py:26`
- **Description:** The `_retry_request` helper uses `Retry-After` header value directly from the server as a sleep duration. A malicious server could set `Retry-After: 86400` to hang the app for a day. The `min(wait, 30)` cap mitigates this well, but `float()` conversion of arbitrary header could raise exceptions.
- **Recommendation:** Wrap `float(r.headers.get("Retry-After", ...))` in try/except.

#### 8. Git Integration Passes User-Derived Filenames to Subprocess
- **Severity:** Low
- **Type:** Best practice
- **File:** `src/linguaedit/services/git_integration.py:33`
- **Description:** Git commands use `subprocess.run(["git"] + args, ...)` with list arguments (no shell=True) — this is safe against injection. The filenames come from the filesystem, not user input. No actual vulnerability.
- **Recommendation:** No action needed. Current implementation is correct.

#### 9. Subprocess Calls in window.py for TTS/External Tools
- **Severity:** Low
- **Type:** Best practice
- **File:** `src/linguaedit/ui/window.py:4330,5759,5832`
- **Description:** Multiple `subprocess.run()` and `subprocess.Popen()` calls for TTS (`say`, `espeak`, `spd-say`) and file manager integration. All use list arguments (no shell=True) and are invoked with hardcoded command names.
- **Recommendation:** No action needed. Correct use of subprocess.

---

### ℹ️ INFO

#### 10. YAML Parser Uses `safe_load` ✅
- **File:** `src/linguaedit/parsers/yaml_parser.py:105`
- **Description:** Correctly uses `yaml.safe_load()` — no arbitrary code execution risk.

#### 11. No `eval()`, `exec()`, or `pickle` Usage ✅
- **Description:** Codebase audit found zero instances of `eval()`, `exec()` (Python builtin), or `pickle` deserialization. The only `exec()` calls are Qt's `QDialog.exec()`.

#### 12. No `shell=True` in Subprocess Calls ✅
- **Description:** All subprocess invocations use list arguments without `shell=True`.

#### 13. Keystore Fernet Fallback: Good PBKDF2 Configuration ✅
- **File:** `src/linguaedit/services/keystore.py:267`
- **Description:** 480,000 PBKDF2 iterations with SHA256, 32-byte random salt, Fernet (AES-128-CBC with HMAC-SHA256) — meets OWASP 2024 recommendations. Salt stored with 0o600 permissions.

#### 14. API Keys Not Logged ✅
- **Description:** No logging/print statements expose API keys. Keys are retrieved from keystore only when needed for HTTP headers.

#### 15. File Permissions on Encrypted Secrets ✅
- **File:** `src/linguaedit/services/keystore.py:286,296`
- **Description:** Both `.secrets.enc` and `.secrets.salt` are created with `chmod(0o600)`.

#### 16. TLS Verification Not Disabled ✅
- **Description:** No `verify=False` found in any `requests` call. All HTTPS connections validate certificates.

#### 17. No Path Traversal in Parsers ✅
- **Description:** Parsers read from user-selected file paths (via QFileDialog) and write to the same path or user-specified output. No path construction from parsed file content.

---

## Dependencies Review (`pyproject.toml`)

| Dependency | Version | Known Issues |
|---|---|---|
| PySide6 >=6.5 | ✅ | Keep updated; Qt has periodic CVEs |
| polib >=1.2 | ✅ | No known vulnerabilities |
| requests >=2.28 | ✅ | Keep updated |
| pyenchant >=3.2 | ✅ | No known vulnerabilities |
| PyYAML >=6.0 | ✅ | Safe (uses `safe_load`) |
| openai >=1.0 (optional) | ✅ | No known vulnerabilities |
| anthropic >=0.18 (optional) | ✅ | No known vulnerabilities |

**Recommendation:** Add `cryptography` as a required dependency (currently only needed by fallback keystore but not declared).

---

## Summary Table

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| 1 | 🔴 Critical | XXE in XML parsers | ✅ Fixed |
| 2 | 🟠 High | Plugin arbitrary code execution | ⚠️ Partially fixed |
| 3 | 🟠 High | Legacy XOR keystore fallback | ⚠️ Open |
| 4 | 🟡 Medium | SSRF via LibreTranslate URL | ⚠️ Open |
| 5 | 🟡 Medium | Temp file cleanup | ⚠️ Open |
| 6 | 🟡 Medium | Password prompt shows cleartext | ⚠️ Open |
| 7 | 🟢 Low | Retry-After header parsing | ⚠️ Open |
| 8-9 | 🟢 Low | Subprocess usage | ✅ OK |
| 10-17 | ℹ️ Info | Good practices confirmed | ✅ OK |

---

## Overall Assessment

**Rating: Good** — The codebase follows secure coding practices in most areas. The critical XXE vulnerability has been fixed. The main remaining concern is the legacy XOR keystore fallback which should be removed. For a desktop translation editor, the attack surface is relatively limited (primarily via malicious translation files), and the XXE fix addresses the most significant vector.

The code quality reflects that the author (Danne) takes security seriously — no `eval`, no `shell=True`, proper use of `yaml.safe_load`, credentials in system keychain, TLS validation everywhere. 👍
