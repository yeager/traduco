"""Pre-translation services: Lingva, MyMemory (free), OpenAI, Anthropic (paid)."""

from __future__ import annotations

import json
import requests
from typing import Optional


class TranslationError(Exception):
    pass


def translate_lingva(text: str, source: str = "en", target: str = "sv") -> str:
    """Free translation via Lingva Translate (Google Translate proxy)."""
    url = f"https://lingva.ml/api/v1/{source}/{target}/{requests.utils.quote(text)}"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        return r.json().get("translation", "")
    except Exception as e:
        raise TranslationError(f"Lingva: {e}")


def translate_mymemory(text: str, source: str = "en", target: str = "sv",
                       email: Optional[str] = None) -> str:
    """Free translation via MyMemory API."""
    params = {"q": text, "langpair": f"{source}|{target}"}
    if email:
        params["de"] = email  # higher rate limit with email
    try:
        r = requests.get("https://api.mymemory.translated.net/get", params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        return data.get("responseData", {}).get("translatedText", "")
    except Exception as e:
        raise TranslationError(f"MyMemory: {e}")


def translate_openai(text: str, source: str = "en", target: str = "sv",
                     api_key: str = "", model: str = "gpt-4o-mini") -> str:
    """Paid translation via OpenAI API."""
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
                        api_key: str = "", model: str = "claude-sonnet-4-20250514") -> str:
    """Paid translation via Anthropic API."""
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


# Registry
ENGINES = {
    "lingva": {"fn": translate_lingva, "free": True, "name": "Lingva (Google)"},
    "mymemory": {"fn": translate_mymemory, "free": True, "name": "MyMemory"},
    "openai": {"fn": translate_openai, "free": False, "name": "OpenAI"},
    "anthropic": {"fn": translate_anthropic, "free": False, "name": "Anthropic"},
}


def translate(text: str, engine: str = "lingva", **kwargs) -> str:
    """Translate text using the specified engine."""
    if engine not in ENGINES:
        raise TranslationError(f"Unknown engine: {engine}")
    return ENGINES[engine]["fn"](text, **kwargs)
