"""Translation linting and quality score."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from PySide6.QtCore import QCoreApplication

from linguaedit.services.glossary import check_glossary


# CLDR locale data for validation
LOCALE_FORMATS = {
    # Date formats (DD/MM vs MM/DD vs YYYY-MM-DD)
    "en": {"date_format": "MM/DD/YYYY", "currency": "$", "decimal_separator": ".", "thousands_separator": ","},
    "en-US": {"date_format": "MM/DD/YYYY", "currency": "$", "decimal_separator": ".", "thousands_separator": ","},
    "en-GB": {"date_format": "DD/MM/YYYY", "currency": "£", "decimal_separator": ".", "thousands_separator": ","},
    "sv": {"date_format": "YYYY-MM-DD", "currency": "kr", "decimal_separator": ",", "thousands_separator": " "},
    "sv-SE": {"date_format": "YYYY-MM-DD", "currency": "kr", "decimal_separator": ",", "thousands_separator": " "},
    "de": {"date_format": "DD.MM.YYYY", "currency": "€", "decimal_separator": ",", "thousands_separator": "."},
    "de-DE": {"date_format": "DD.MM.YYYY", "currency": "€", "decimal_separator": ",", "thousands_separator": "."},
    "fr": {"date_format": "DD/MM/YYYY", "currency": "€", "decimal_separator": ",", "thousands_separator": " "},
    "fr-FR": {"date_format": "DD/MM/YYYY", "currency": "€", "decimal_separator": ",", "thousands_separator": " "},
    "es": {"date_format": "DD/MM/YYYY", "currency": "€", "decimal_separator": ",", "thousands_separator": "."},
    "es-ES": {"date_format": "DD/MM/YYYY", "currency": "€", "decimal_separator": ",", "thousands_separator": "."},
    "it": {"date_format": "DD/MM/YYYY", "currency": "€", "decimal_separator": ",", "thousands_separator": "."},
    "pt": {"date_format": "DD/MM/YYYY", "currency": "€", "decimal_separator": ",", "thousands_separator": " "},
    "ru": {"date_format": "DD.MM.YYYY", "currency": "₽", "decimal_separator": ",", "thousands_separator": " "},
    "ja": {"date_format": "YYYY/MM/DD", "currency": "¥", "decimal_separator": ".", "thousands_separator": ","},
    "ko": {"date_format": "YYYY.MM.DD", "currency": "₩", "decimal_separator": ".", "thousands_separator": ","},
    "zh": {"date_format": "YYYY/MM/DD", "currency": "¥", "decimal_separator": ".", "thousands_separator": ","},
    "zh-CN": {"date_format": "YYYY/MM/DD", "currency": "¥", "decimal_separator": ".", "thousands_separator": ","},
    "no": {"date_format": "DD.MM.YYYY", "currency": "kr", "decimal_separator": ",", "thousands_separator": " "},
    "da": {"date_format": "DD.MM.YYYY", "currency": "kr", "decimal_separator": ",", "thousands_separator": "."},
    "fi": {"date_format": "DD.MM.YYYY", "currency": "€", "decimal_separator": ",", "thousands_separator": " "},
}



@dataclass
class LintIssue:
    severity: str  # "error", "warning", "info"
    message: str
    entry_index: int = -1
    msgid: str = ""


@dataclass
class LintResult:
    issues: list[LintIssue] = field(default_factory=list)
    score: float = 100.0  # quality percentage

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")


def _get_locale_format(locale: str) -> dict:
    """Hämta CLDR-format för en locale."""
    # Försök fullständig locale först (sv-SE)
    if locale in LOCALE_FORMATS:
        return LOCALE_FORMATS[locale]
    
    # Försök bara språkkod (sv)
    lang_code = locale.split('-')[0].split('_')[0]
    if lang_code in LOCALE_FORMATS:
        return LOCALE_FORMATS[lang_code]
    
    # Fallback till engelska
    return LOCALE_FORMATS["en"]


def _check_number_localization(source: str, target: str, target_locale: str) -> list[str]:
    """Kontrollera att tal är korrekt lokaliserade."""
    issues = []
    
    # Hitta tal i source (engelska format)
    number_pattern = r'\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\b'
    source_numbers = re.findall(number_pattern, source)
    
    if not source_numbers:
        return issues
    
    locale_format = _get_locale_format(target_locale)
    expected_thousands = locale_format["thousands_separator"]
    expected_decimal = locale_format["decimal_separator"]
    
    for num in source_numbers:
        # Kontrollera om detta tal finns i target i fel format
        if num in target and expected_thousands != ",":
            # Tal från source finns direkt i target - kan vara fel lokalisering
            issues.append(QCoreApplication.translate("Linter", 
                f"Number '{num}' might need localization (expected thousands separator: '{expected_thousands}')"))
    
    return issues


def _check_currency_localization(source: str, target: str, target_locale: str) -> list[str]:
    """Kontrollera valutasymboler."""
    issues = []
    
    locale_format = _get_locale_format(target_locale)
    expected_currency = locale_format["currency"]
    
    # Vanliga valutasymboler
    currency_symbols = ["$", "€", "£", "¥", "₹", "₽", "kr", "€", "CHF"]
    
    # Hitta valutasymboler i source
    source_currencies = []
    for symbol in currency_symbols:
        if symbol in source:
            source_currencies.append(symbol)
    
    if source_currencies:
        # Kolla om samma symbol används i target
        for symbol in source_currencies:
            if symbol in target and symbol != expected_currency:
                issues.append(QCoreApplication.translate("Linter", 
                    f"Currency symbol '{symbol}' should be localized to '{expected_currency}' for {target_locale}"))
    
    return issues


def _check_date_format(source: str, target: str, target_locale: str) -> list[str]:
    """Kontrollera datumformat."""
    issues = []
    
    locale_format = _get_locale_format(target_locale)
    expected_format = locale_format["date_format"]
    
    # Hitta amerikanska datumformat (MM/DD/YYYY) i source
    us_date_pattern = r'\b\d{1,2}/\d{1,2}/\d{4}\b'
    us_dates = re.findall(us_date_pattern, source)
    
    if us_dates and target_locale not in ["en", "en-US"]:
        # Kolla om samma format används i target
        for date in us_dates:
            if date in target:
                issues.append(QCoreApplication.translate("Linter", 
                    f"Date format '{date}' should be localized to {expected_format} format for {target_locale}"))
    
    return issues


def lint_entries(entries: list[dict]) -> LintResult:
    """Lint a list of translation entries.

    Each entry dict must have: msgid, msgstr, flags (list), index (int).
    Returns LintResult with issues and quality score.
    """
    issues: list[LintIssue] = []
    total = len(entries)
    if total == 0:
        return LintResult(issues=[], score=100.0)

    penalty = 0.0

    for e in entries:
        idx = e.get("index", -1)
        msgid = e.get("msgid", "")
        msgstr = e.get("msgstr", "")
        flags = e.get("flags", [])

        if not msgid:
            continue

        # Missing translation
        if not msgstr:
            issues.append(LintIssue("info", QCoreApplication.translate("Linter", "Untranslated"), idx, msgid))
            penalty += 1.0
            continue

        # Fuzzy
        if "fuzzy" in flags:
            issues.append(LintIssue("info", QCoreApplication.translate("Linter", "Fuzzy"), idx, msgid))
            penalty += 0.5

        # Case mismatch (first letter upper/lower)
        if msgid[0].isalpha() and msgstr[0].isalpha():
            if msgid[0].isupper() != msgstr[0].isupper():
                issues.append(LintIssue("warning", QCoreApplication.translate("Linter", "Case mismatch: source starts with '%s', translation with '%s'") % (msgid[0], msgstr[0]), idx, msgid))
                penalty += 0.3

        # Trailing/leading whitespace mismatch
        if msgid.startswith(" ") != msgstr.startswith(" "):
            issues.append(LintIssue("warning", QCoreApplication.translate("Linter", "Leading whitespace mismatch"), idx, msgid))
            penalty += 0.3
        if msgid.endswith(" ") != msgstr.endswith(" "):
            issues.append(LintIssue("warning", QCoreApplication.translate("Linter", "Trailing whitespace mismatch"), idx, msgid))
            penalty += 0.3

        # Newline mismatch
        src_nl = msgid.count("\n")
        dst_nl = msgstr.count("\n")
        if src_nl != dst_nl:
            issues.append(LintIssue("warning", QCoreApplication.translate("Linter", "Newline count mismatch (%s vs %s)") % (src_nl, dst_nl), idx, msgid))
            penalty += 0.3

        # Printf format specifier mismatch
        src_fmt = set(re.findall(r'%[\d$]*[sdiufxXoecpg%]', msgid))
        dst_fmt = set(re.findall(r'%[\d$]*[sdiufxXoecpg%]', msgstr))
        if src_fmt != dst_fmt:
            issues.append(LintIssue("error", QCoreApplication.translate("Linter", "Format specifier mismatch: %s vs %s") % (src_fmt, dst_fmt), idx, msgid))
            penalty += 2.0

        # Python format specifier mismatch
        src_py = set(re.findall(r'\{[^}]*\}', msgid))
        dst_py = set(re.findall(r'\{[^}]*\}', msgstr))
        if src_py != dst_py:
            issues.append(LintIssue("error", QCoreApplication.translate("Linter", "Python format mismatch: %s vs %s") % (src_py, dst_py), idx, msgid))
            penalty += 2.0

        # Punctuation mismatch (ending)
        if msgid and msgstr:
            for p in ".!?:;":
                if msgid.endswith(p) and not msgstr.endswith(p):
                    issues.append(LintIssue("info", QCoreApplication.translate("Linter", "Ending '%s' missing in translation") % p, idx, msgid))
                    penalty += 0.1
                    break

        # Suspicious length ratio  
        if len(msgid) > 5 and len(msgstr) > 0:
            ratio = len(msgstr) / len(msgid)
            if ratio > 3.0 or ratio < 0.2:
                issues.append(LintIssue("warning", QCoreApplication.translate("Linter", "Suspicious length ratio: %sx") % f"{ratio:.1f}", idx, msgid))
                penalty += 0.5

        # HTML/XML tag validation
        html_tag_pattern = r'<[^>]+>'
        src_tags = set(re.findall(html_tag_pattern, msgid))
        dst_tags = set(re.findall(html_tag_pattern, msgstr))
        
        if src_tags != dst_tags:
            missing_in_target = src_tags - dst_tags
            extra_in_target = dst_tags - src_tags
            
            if missing_in_target:
                issues.append(LintIssue("error", QCoreApplication.translate("Linter", "Missing HTML/XML tags in translation: %s") % ", ".join(missing_in_target), idx, msgid))
                penalty += 1.5
            if extra_in_target:
                issues.append(LintIssue("warning", QCoreApplication.translate("Linter", "Extra HTML/XML tags in translation: %s") % ", ".join(extra_in_target), idx, msgid))
                penalty += 1.0

        # Qt accelerator keys (&) validation 
        src_accelerators = re.findall(r'&[a-zA-Z]', msgid)
        dst_accelerators = re.findall(r'&[a-zA-Z]', msgstr)
        
        if len(src_accelerators) != len(dst_accelerators):
            issues.append(LintIssue("warning", QCoreApplication.translate("Linter", "Accelerator key mismatch: source has %d, translation has %d") % (len(src_accelerators), len(dst_accelerators)), idx, msgid))
            penalty += 0.8

        # CLDR validation (kräver target_locale i entry dict)
        target_locale = e.get("target_locale", "sv")  # Default till svenska
        
        # Nummer-lokalisering
        number_issues = _check_number_localization(msgid, msgstr, target_locale)
        for issue_msg in number_issues:
            issues.append(LintIssue("warning", issue_msg, idx, msgid))
            penalty += 0.4
        
        # Valuta-lokalisering
        currency_issues = _check_currency_localization(msgid, msgstr, target_locale)
        for issue_msg in currency_issues:
            issues.append(LintIssue("warning", issue_msg, idx, msgid))
            penalty += 0.4
        
        # Datum-format
        date_issues = _check_date_format(msgid, msgstr, target_locale)
        for issue_msg in date_issues:
            issues.append(LintIssue("warning", issue_msg, idx, msgid))
            penalty += 0.4

    # Check for duplicate msgids with different translations (after individual entry checks)
    msgid_translations = {}
    for e in entries:
        msgid = e.get("msgid", "")
        msgstr = e.get("msgstr", "")
        if msgid and msgstr:
            if msgid in msgid_translations:
                if msgid_translations[msgid] != msgstr:
                    # Found duplicate msgid with different translation
                    issues.append(LintIssue("warning", QCoreApplication.translate("Linter", "Inconsistent translation for '%s'") % msgid[:50], e.get("index", -1), msgid))
                    penalty += 0.5
            else:
                msgid_translations[msgid] = msgstr

    # Check glossary consistency
    try:
        glossary_violations = check_glossary(entries)
        for violation in glossary_violations:
            issues.append(LintIssue("warning", 
                QCoreApplication.translate("Linter", "Glossary inconsistency: %s") % violation.message, 
                violation.entry_index, violation.term.source))
            penalty += 0.3
    except Exception:
        pass  # Glossary check is optional

    score = max(0.0, 100.0 - (penalty / total) * 100.0)
    return LintResult(issues=issues, score=round(score, 1))
