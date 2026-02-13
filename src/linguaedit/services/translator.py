"""Pre-translation services for LinguaEdit.

Free engines: Lingva, MyMemory, LibreTranslate, Argos Translate, Apertium, NLLB (Meta).
Paid engines (API key required): OpenAI, Anthropic, DeepL, Google Cloud, Microsoft, Amazon.
"""
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import json
import time
import requests
from typing import Optional

from linguaedit.services.keystore import get_secret

_DEFAULT_TIMEOUT = 30


class TranslationError(Exception):
    pass


# ── Helpers ───────────────────────────────────────────────────────────

def _retry_request(method: str, url: str, *, max_retries: int = 3, **kwargs) -> requests.Response:
    """HTTP request with retry on 429 / 5xx."""
    kwargs.setdefault("timeout", _DEFAULT_TIMEOUT)
    for attempt in range(max_retries):
        r = requests.request(method, url, **kwargs)
        if r.status_code == 429 or r.status_code >= 500:
            wait = float(r.headers.get("Retry-After", 2 ** attempt))
            time.sleep(min(wait, 30))
            continue
        r.raise_for_status()
        return r
    r.raise_for_status()
    return r


def _get_api_key(service: str, key: str = "api_key") -> str:
    """Fetch API key from keystore, raise if missing."""
    val = get_secret(service, key)
    if not val:
        raise TranslationError(f"{service}: API key not configured. Set it in Preferences → API Keys.")
    return val


# ── FREE ENGINES ──────────────────────────────────────────────────────

def translate_lingva(text: str, source: str = "en", target: str = "sv", **kw) -> str:
    """Free translation via Lingva Translate (Google Translate proxy)."""
    base = kw.get("lingva_url", "https://translate.plausibility.cloud")
    url = f"{base}/api/v1/{source}/{target}/{requests.utils.quote(text)}"
    try:
        r = _retry_request("GET", url)
        return r.json().get("translation", "")
    except Exception as e:
        raise TranslationError(f"Lingva: {e}")


def translate_mymemory(text: str, source: str = "en", target: str = "sv",
                       email: Optional[str] = None, **kw) -> str:
    """Free translation via MyMemory API."""
    params = {"q": text, "langpair": f"{source}|{target}"}
    if email:
        params["de"] = email
    try:
        r = _retry_request("GET", "https://api.mymemory.translated.net/get", params=params)
        data = r.json()
        return data.get("responseData", {}).get("translatedText", "")
    except Exception as e:
        raise TranslationError(f"MyMemory: {e}")


def translate_libretranslate(text: str, source: str = "en", target: str = "sv",
                             instance: str = "https://libretranslate.com", **kw) -> str:
    """Free translation via LibreTranslate (self-hostable)."""
    payload = {"q": text, "source": source, "target": target, "format": "text"}
    # Optional API key for paid instances
    api_key = get_secret("libretranslate", "api_key")
    if api_key:
        payload["api_key"] = api_key
    try:
        r = _retry_request("POST", f"{instance}/translate", json=payload)
        return r.json().get("translatedText", "")
    except Exception as e:
        raise TranslationError(f"LibreTranslate: {e}")


def translate_argos(text: str, source: str = "en", target: str = "sv", **kw) -> str:
    """Offline translation via Argos Translate (local, no network)."""
    try:
        import argostranslate.translate
    except ImportError:
        raise TranslationError("Install argostranslate: pip install argostranslate")
    try:
        result = argostranslate.translate.translate(text, source, target)
        if not result:
            raise TranslationError("Argos Translate returned empty result. Language pack may be missing.")
        return result
    except TranslationError:
        raise
    except Exception as e:
        raise TranslationError(f"Argos Translate: {e}")


def translate_apertium(text: str, source: str = "en", target: str = "sv", **kw) -> str:
    """Free translation via Apertium API (good for Nordic languages)."""
    params = {"q": text, "langpair": f"{source}|{target}"}
    try:
        r = _retry_request("GET", "https://apertium.org/apy/translate", params=params)
        data = r.json()
        translated = data.get("responseData", {}).get("translatedText", "")
        if not translated:
            code = data.get("responseStatus", "")
            raise TranslationError(f"Apertium: unsupported language pair ({source}→{target}), status {code}")
        return translated
    except TranslationError:
        raise
    except Exception as e:
        raise TranslationError(f"Apertium: {e}")


def translate_nllb(text: str, source: str = "en", target: str = "sv", **kw) -> str:
    """Free translation via Meta NLLB (No Language Left Behind) on HuggingFace Inference API."""
    # NLLB uses BCP-47-like codes: eng_Latn, swe_Latn etc.
    _NLLB_LANG_MAP = {
        "en": "eng_Latn", "sv": "swe_Latn", "da": "dan_Latn", "nb": "nob_Latn",
        "nn": "nno_Latn", "fi": "fin_Latn", "de": "deu_Latn", "fr": "fra_Latn",
        "es": "spa_Latn", "it": "ita_Latn", "pt": "por_Latn", "nl": "nld_Latn",
        "pl": "pol_Latn", "ru": "rus_Cyrl", "uk": "ukr_Cyrl", "zh": "zho_Hans",
        "ja": "jpn_Jpan", "ko": "kor_Hang", "ar": "arb_Arab", "hi": "hin_Deva",
        "tr": "tur_Latn", "cs": "ces_Latn", "ro": "ron_Latn", "hu": "hun_Latn",
        "el": "ell_Grek", "th": "tha_Thai", "vi": "vie_Latn", "id": "ind_Latn",
        "ms": "zsm_Latn", "he": "heb_Hebr", "bg": "bul_Cyrl", "hr": "hrv_Latn",
        "sk": "slk_Latn", "sl": "slv_Latn", "et": "est_Latn", "lv": "lvs_Latn",
        "lt": "lit_Latn", "is": "isl_Latn", "ga": "gle_Latn", "cy": "cym_Latn",
        "mt": "mlt_Latn", "sq": "als_Latn", "mk": "mkd_Cyrl", "bs": "bos_Latn",
        "sr": "srp_Cyrl", "ka": "kat_Geor", "hy": "hye_Armn", "az": "azj_Latn",
        "kk": "kaz_Cyrl", "uz": "uzn_Latn", "tg": "tgk_Cyrl", "mn": "khk_Cyrl",
        "my": "mya_Mymr", "km": "khm_Khmr", "lo": "lao_Laoo", "am": "amh_Ethi",
        "sw": "swh_Latn", "ha": "hau_Latn", "yo": "yor_Latn", "ig": "ibo_Latn",
        "zu": "zul_Latn", "af": "afr_Latn", "ta": "tam_Taml", "te": "tel_Telu",
        "bn": "ben_Beng", "ur": "urd_Arab", "fa": "pes_Arab", "ne": "npi_Deva",
        "si": "sin_Sinh", "ml": "mal_Mlym", "kn": "kan_Knda", "gu": "guj_Gujr",
        "mr": "mar_Deva", "pa": "pan_Guru",
    }
    src = _NLLB_LANG_MAP.get(source, source)
    tgt = _NLLB_LANG_MAP.get(target, target)
    # Use HuggingFace Inference API (free tier)
    headers = {}
    hf_token = get_secret("huggingface", "api_key")
    if hf_token:
        headers["Authorization"] = f"Bearer {hf_token}"
    payload = {"inputs": text, "parameters": {"src_lang": src, "tgt_lang": tgt}}
    try:
        r = _retry_request(
            "POST",
            "https://api-inference.huggingface.co/models/facebook/nllb-200-distilled-600M",
            headers=headers, json=payload,
        )
        data = r.json()
        if isinstance(data, list) and data:
            return data[0].get("translation_text", "")
        raise TranslationError(f"NLLB: unexpected response: {data}")
    except TranslationError:
        raise
    except Exception as e:
        raise TranslationError(f"NLLB: {e}")


# ── PAID ENGINES (API key required) ──────────────────────────────────

def translate_openai(text: str, source: str = "en", target: str = "sv",
                     api_key: str = "", model: str = "gpt-4o-mini", **kw) -> str:
    """Paid translation via OpenAI API."""
    api_key = api_key or get_secret("openai", "api_key") or ""
    if not api_key:
        raise TranslationError("OpenAI API key required")
    try:
        import openai
        client = openai.OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": f"You are a professional translator. Translate from {source} to {target}. Return only the translation, nothing else."},
                {"role": "user", "content": text},
            ],
            temperature=0.2,
        )
        return resp.choices[0].message.content.strip()
    except ImportError:
        raise TranslationError("Install openai: pip install openai")
    except Exception as e:
        raise TranslationError(f"OpenAI: {e}")


def translate_anthropic(text: str, source: str = "en", target: str = "sv",
                        api_key: str = "", model: str = "claude-sonnet-4-20260514", **kw) -> str:
    """Paid translation via Anthropic API."""
    api_key = api_key or get_secret("anthropic", "api_key") or ""
    if not api_key:
        raise TranslationError("Anthropic API key required")
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=model,
            max_tokens=4096,
            messages=[
                {"role": "user", "content": f"Translate the following text from {source} to {target}. Return only the translation, nothing else.\n\n{text}"},
            ],
        )
        return resp.content[0].text.strip()
    except ImportError:
        raise TranslationError("Install anthropic: pip install anthropic")
    except Exception as e:
        raise TranslationError(f"Anthropic: {e}")


def translate_deepl(text: str, source: str = "en", target: str = "sv",
                    formality: str = "default", **kw) -> str:
    """Paid translation via DeepL API (Free + Pro)."""
    api_key = _get_api_key("deepl")
    # DeepL Free keys end with ":fx"
    base = "https://api-free.deepl.com" if api_key.endswith(":fx") else "https://api.deepl.com"
    # DeepL uses uppercase lang codes; source can be auto-detect (None)
    src = source.upper() if source else None
    tgt = target.upper()
    # DeepL special cases
    if tgt == "EN":
        tgt = "EN-US"
    if tgt == "PT":
        tgt = "PT-PT"
    payload = {"text": [text], "target_lang": tgt}
    if src:
        payload["source_lang"] = src
    if formality != "default":
        payload["formality"] = formality  # less, more, prefer_less, prefer_more
    headers = {"Authorization": f"DeepL-Auth-Key {api_key}", "Content-Type": "application/json"}
    try:
        r = _retry_request("POST", f"{base}/v2/translate", headers=headers, json=payload)
        data = r.json()
        translations = data.get("translations", [])
        if translations:
            return translations[0].get("text", "")
        raise TranslationError(f"DeepL: empty response")
    except TranslationError:
        raise
    except Exception as e:
        raise TranslationError(f"DeepL: {e}")


def translate_google_cloud(text: str, source: str = "en", target: str = "sv", **kw) -> str:
    """Paid translation via Google Cloud Translation API v2."""
    api_key = _get_api_key("google_cloud")
    params = {"q": text, "target": target, "source": source, "format": "text", "key": api_key}
    try:
        r = _retry_request("POST", "https://translation.googleapis.com/language/translate/v2", params=params)
        data = r.json()
        translations = data.get("data", {}).get("translations", [])
        if translations:
            return translations[0].get("translatedText", "")
        raise TranslationError("Google Cloud: empty response")
    except TranslationError:
        raise
    except Exception as e:
        raise TranslationError(f"Google Cloud Translation: {e}")


def translate_microsoft(text: str, source: str = "en", target: str = "sv", **kw) -> str:
    """Paid translation via Microsoft Azure Translator."""
    api_key = _get_api_key("microsoft_translator")
    region = get_secret("microsoft_translator", "region") or "global"
    headers = {
        "Ocp-Apim-Subscription-Key": api_key,
        "Ocp-Apim-Subscription-Region": region,
        "Content-Type": "application/json",
    }
    params = {"api-version": "3.0", "from": source, "to": target}
    body = [{"Text": text}]
    try:
        r = _retry_request(
            "POST", "https://api.cognitive.microsofttranslator.com/translate",
            headers=headers, params=params, json=body,
        )
        data = r.json()
        if data and data[0].get("translations"):
            return data[0]["translations"][0].get("text", "")
        raise TranslationError("Microsoft Translator: empty response")
    except TranslationError:
        raise
    except Exception as e:
        raise TranslationError(f"Microsoft Translator: {e}")


def translate_amazon(text: str, source: str = "en", target: str = "sv", **kw) -> str:
    """Paid translation via Amazon Translate (AWS)."""
    try:
        import boto3
    except ImportError:
        raise TranslationError("Install boto3: pip install boto3")
    # AWS credentials from keystore or environment
    access_key = get_secret("aws", "access_key_id")
    secret_key = get_secret("aws", "secret_access_key")
    region = get_secret("aws", "region") or "us-east-1"
    try:
        kwargs_boto = {"service_name": "translate", "region_name": region}
        if access_key and secret_key:
            kwargs_boto["aws_access_key_id"] = access_key
            kwargs_boto["aws_secret_access_key"] = secret_key
        client = boto3.client(**kwargs_boto)
        resp = client.translate_text(Text=text, SourceLanguageCode=source, TargetLanguageCode=target)
        return resp.get("TranslatedText", "")
    except Exception as e:
        raise TranslationError(f"Amazon Translate: {e}")


# ── Registry ──────────────────────────────────────────────────────────

ENGINES = {
    # Free
    "lingva":          {"fn": translate_lingva,          "free": True,  "name": "Lingva (Google)"},
    "mymemory":        {"fn": translate_mymemory,        "free": True,  "name": "MyMemory"},
    "libretranslate":  {"fn": translate_libretranslate,  "free": True,  "name": "LibreTranslate"},
    "argos":           {"fn": translate_argos,           "free": True,  "name": "Argos Translate (offline)"},
    "apertium":        {"fn": translate_apertium,        "free": True,  "name": "Apertium"},
    "nllb":            {"fn": translate_nllb,            "free": True,  "name": "NLLB (Meta)"},
    # Paid
    "openai":          {"fn": translate_openai,          "free": False, "name": "OpenAI"},
    "anthropic":       {"fn": translate_anthropic,       "free": False, "name": "Anthropic"},
    "deepl":           {"fn": translate_deepl,           "free": False, "name": "DeepL"},
    "google_cloud":    {"fn": translate_google_cloud,    "free": False, "name": "Google Cloud Translation"},
    "microsoft":       {"fn": translate_microsoft,       "free": False, "name": "Microsoft Translator"},
    "amazon":          {"fn": translate_amazon,          "free": False, "name": "Amazon Translate"},
}


def translate(text: str, engine: str = "lingva", **kwargs) -> str:
    """Translate text using the specified engine."""
    if engine not in ENGINES:
        raise TranslationError(f"Unknown engine: {engine}")
    return ENGINES[engine]["fn"](text, **kwargs)
