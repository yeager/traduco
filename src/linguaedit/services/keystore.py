"""Secure credential storage abstraction for macOS Keychain, Linux Secret Service, and fallback."""
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Optional
from gettext import gettext as _

_SERVICE_PREFIX = "linguaedit"


# ── Backend detection ─────────────────────────────────────────────────

def _detect_backend() -> str:
    """Detect the best available secrets backend."""
    if platform.system() == "Darwin":
        return "macos"
    if platform.system() == "Linux":
        try:
            import secretstorage  # noqa: F401
            return "linux"
        except ImportError:
            pass
    return "fallback"


_backend = _detect_backend()


# ── Public API ────────────────────────────────────────────────────────

def store_secret(service: str, key: str, value: str) -> None:
    """Store a secret in the platform keychain.

    Args:
        service: Service/platform name (e.g. "transifex")
        key: Key name (e.g. "api_token")
        value: Secret value
    """
    label = f"{_SERVICE_PREFIX}/{service}/{key}"
    if _backend == "macos":
        _macos_store(label, value)
    elif _backend == "linux":
        _linux_store(label, value)
    else:
        _fallback_store(label, value)


def get_secret(service: str, key: str) -> Optional[str]:
    """Retrieve a secret from the platform keychain.

    Returns None if not found.
    """
    label = f"{_SERVICE_PREFIX}/{service}/{key}"
    if _backend == "macos":
        return _macos_get(label)
    elif _backend == "linux":
        return _linux_get(label)
    else:
        return _fallback_get(label)


def delete_secret(service: str, key: str) -> None:
    """Delete a secret from the platform keychain."""
    label = f"{_SERVICE_PREFIX}/{service}/{key}"
    if _backend == "macos":
        _macos_delete(label)
    elif _backend == "linux":
        _linux_delete(label)
    else:
        _fallback_delete(label)


def backend_name() -> str:
    """Return the name of the active backend for display."""
    return {"macos": "macOS Keychain", "linux": "Secret Service", "fallback": _("Encrypted file (fallback)")}[_backend]


def is_secure_backend() -> bool:
    """True if using a real system keychain."""
    return _backend in ("macos", "linux")


# ── macOS Keychain ────────────────────────────────────────────────────

def _macos_store(label: str, value: str) -> None:
    # Delete first to avoid "already exists" error
    _macos_delete(label)
    subprocess.run(
        ["security", "add-generic-password",
         "-a", _SERVICE_PREFIX, "-s", label, "-w", value,
         "-T", "", "-U"],
        check=True, capture_output=True, text=True,
    )


def _macos_get(label: str) -> Optional[str]:
    try:
        r = subprocess.run(
            ["security", "find-generic-password",
             "-a", _SERVICE_PREFIX, "-s", label, "-w"],
            check=True, capture_output=True, text=True,
        )
        return r.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def _macos_delete(label: str) -> None:
    try:
        subprocess.run(
            ["security", "delete-generic-password",
             "-a", _SERVICE_PREFIX, "-s", label],
            check=True, capture_output=True, text=True,
        )
    except subprocess.CalledProcessError:
        pass  # not found, fine


# ── Linux Secret Service ─────────────────────────────────────────────

def _linux_store(label: str, value: str) -> None:
    import secretstorage
    conn = secretstorage.dbus_init()
    collection = secretstorage.get_default_collection(conn)
    if collection.is_locked():
        collection.unlock()
    attrs = {"application": _SERVICE_PREFIX, "key": label}
    # Delete existing
    for item in collection.search_items(attrs):
        item.delete()
    collection.create_item(label, attrs, value.encode("utf-8"), replace=True)


def _linux_get(label: str) -> Optional[str]:
    import secretstorage
    conn = secretstorage.dbus_init()
    collection = secretstorage.get_default_collection(conn)
    if collection.is_locked():
        collection.unlock()
    attrs = {"application": _SERVICE_PREFIX, "key": label}
    for item in collection.search_items(attrs):
        if item.is_locked():
            item.unlock()
        return item.get_secret().decode("utf-8")
    return None


def _linux_delete(label: str) -> None:
    import secretstorage
    conn = secretstorage.dbus_init()
    collection = secretstorage.get_default_collection(conn)
    if collection.is_locked():
        collection.unlock()
    attrs = {"application": _SERVICE_PREFIX, "key": label}
    for item in collection.search_items(attrs):
        item.delete()


# ── Fallback: obfuscated file (NOT truly secure) ─────────────────────

_FALLBACK_PATH = Path.home() / ".config" / "linguaedit" / ".secrets.json"
_FALLBACK_WARNED = False


def _fallback_warn() -> None:
    global _FALLBACK_WARNED
    if not _FALLBACK_WARNED:
        print(
            "WARNING: No system keychain available. "
            "Secrets are stored with basic obfuscation in "
            f"{_FALLBACK_PATH} — this is NOT secure. "
            "Install 'secretstorage' on Linux or use macOS for proper credential storage.",
            file=sys.stderr,
        )
        _FALLBACK_WARNED = True


def _fallback_key() -> bytes:
    """Derive a machine-specific obfuscation key (NOT real encryption)."""
    machine_id = platform.node() + os.getenv("USER", "linguaedit")
    return hashlib.sha256(machine_id.encode()).digest()


def _xor_bytes(data: bytes, key: bytes) -> bytes:
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


def _fallback_load() -> dict:
    try:
        raw = _FALLBACK_PATH.read_bytes()
        decrypted = _xor_bytes(base64.b64decode(raw), _fallback_key())
        return json.loads(decrypted)
    except Exception:
        return {}


def _fallback_save(data: dict) -> None:
    _FALLBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
    encoded = base64.b64encode(_xor_bytes(raw, _fallback_key()))
    _FALLBACK_PATH.write_bytes(encoded)
    _FALLBACK_PATH.chmod(0o600)


def _fallback_store(label: str, value: str) -> None:
    _fallback_warn()
    data = _fallback_load()
    data[label] = value
    _fallback_save(data)


def _fallback_get(label: str) -> Optional[str]:
    _fallback_warn()
    return _fallback_load().get(label)


def _fallback_delete(label: str) -> None:
    data = _fallback_load()
    data.pop(label, None)
    _fallback_save(data)
