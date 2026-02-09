"""Secure credential storage abstraction for macOS, Windows, Linux, and fallback.

Supports:
  - macOS: Keychain via ``security`` CLI
  - Windows: Windows Credential Locker via ``keyring`` (WinVaultKeyring)
  - Linux: Secret Service API (GNOME Keyring / KWallet) via ``secretstorage``
  - Fallback: AES-encrypted file with user-provided master password (Fernet)

SPDX-License-Identifier: GPL-3.0-or-later
"""

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

def _(s): return s  # no-op; UI handles translation

_SERVICE_PREFIX = "linguaedit"


# ── Backend detection ─────────────────────────────────────────────────

def _detect_backend() -> str:
    """Detect the best available secrets backend."""
    system = platform.system()
    if system == "Darwin":
        return "macos"
    if system == "Windows":
        try:
            import keyring  # noqa: F401
            return "windows"
        except ImportError:
            pass
    if system == "Linux":
        try:
            import secretstorage
            # Verify D-Bus connection works
            conn = secretstorage.dbus_init()
            secretstorage.get_default_collection(conn)
            return "linux"
        except Exception:
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
    elif _backend == "windows":
        _windows_store(label, value)
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
    elif _backend == "windows":
        return _windows_get(label)
    elif _backend == "linux":
        return _linux_get(label)
    else:
        return _fallback_get(label)


def delete_secret(service: str, key: str) -> None:
    """Delete a secret from the platform keychain."""
    label = f"{_SERVICE_PREFIX}/{service}/{key}"
    if _backend == "macos":
        _macos_delete(label)
    elif _backend == "windows":
        _windows_delete(label)
    elif _backend == "linux":
        _linux_delete(label)
    else:
        _fallback_delete(label)


def backend_name() -> str:
    """Return the name of the active backend for display."""
    names = {
        "macos": _("macOS Keychain"),
        "windows": _("Windows Credential Locker"),
        "linux": _("Secret Service (GNOME Keyring / KWallet)"),
        "fallback": _("Encrypted file (fallback)"),
    }
    return names[_backend]


def backend_id() -> str:
    """Return the raw backend identifier string."""
    return _backend


def is_secure_backend() -> bool:
    """True if using a real system keychain."""
    return _backend in ("macos", "windows", "linux")


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


# ── Windows Credential Locker ────────────────────────────────────────

def _windows_store(label: str, value: str) -> None:
    import keyring
    keyring.set_password(_SERVICE_PREFIX, label, value)


def _windows_get(label: str) -> Optional[str]:
    import keyring
    return keyring.get_password(_SERVICE_PREFIX, label)


def _windows_delete(label: str) -> None:
    import keyring
    try:
        keyring.delete_password(_SERVICE_PREFIX, label)
    except keyring.errors.PasswordDeleteError:
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


# ── Fallback: Fernet-encrypted file with master password ─────────────

_FALLBACK_DIR = Path.home() / ".config" / "linguaedit"
_FALLBACK_PATH = _FALLBACK_DIR / ".secrets.enc"
_FALLBACK_SALT_PATH = _FALLBACK_DIR / ".secrets.salt"
_FALLBACK_WARNED = False

# In-memory cache of the master password for the session
_master_password: Optional[str] = None


def _fallback_warn() -> None:
    global _FALLBACK_WARNED
    if not _FALLBACK_WARNED:
        print(
            "WARNING: No system keychain available. "
            "Secrets are stored with AES encryption (Fernet) in "
            f"{_FALLBACK_PATH}. "
            "A master password is required to unlock credentials. "
            "Install 'secretstorage' on Linux, 'keyring' on Windows, "
            "or use macOS for system-managed credential storage.",
            file=sys.stderr,
        )
        _FALLBACK_WARNED = True


def _get_master_password() -> str:
    """Get the master password, prompting the user if needed."""
    global _master_password
    if _master_password is not None:
        return _master_password

    # Try to prompt via GUI if QApplication is running
    try:
        from PySide6.QtWidgets import QApplication, QInputDialog
        app = QApplication.instance()
        if app is not None:
            if _FALLBACK_PATH.exists():
                prompt = _("Enter master password to unlock credentials:")
            else:
                prompt = _("Create a master password for credential storage:")
            password, ok = QInputDialog.getText(
                None,
                _("Master Password"),
                prompt,
            )
            if ok and password:
                _master_password = password
                return password
    except Exception:
        pass

    # Fallback to terminal prompt
    import getpass
    if _FALLBACK_PATH.exists():
        password = getpass.getpass("Enter master password to unlock credentials: ")
    else:
        password = getpass.getpass("Create a master password for credential storage: ")
    _master_password = password
    return password


def set_master_password(password: str) -> None:
    """Set the master password for the current session (call from UI)."""
    global _master_password
    _master_password = password


def clear_master_password() -> None:
    """Clear the cached master password."""
    global _master_password
    _master_password = None


def _derive_fernet_key(password: str, salt: bytes) -> bytes:
    """Derive a Fernet key from password + salt using PBKDF2."""
    kdf_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 480_000, dklen=32)
    return base64.urlsafe_b64encode(kdf_key)


def _get_or_create_salt() -> bytes:
    """Get existing salt or create a new random one."""
    if _FALLBACK_SALT_PATH.exists():
        return _FALLBACK_SALT_PATH.read_bytes()
    salt = os.urandom(32)
    _FALLBACK_DIR.mkdir(parents=True, exist_ok=True)
    _FALLBACK_SALT_PATH.write_bytes(salt)
    _FALLBACK_SALT_PATH.chmod(0o600)
    return salt


def _fallback_load() -> dict:
    """Load and decrypt the secrets file."""
    if not _FALLBACK_PATH.exists():
        return {}
    try:
        from cryptography.fernet import Fernet, InvalidToken
    except ImportError:
        # If cryptography is not available, try legacy XOR format
        return _legacy_fallback_load()

    password = _get_master_password()
    salt = _get_or_create_salt()
    key = _derive_fernet_key(password, salt)
    f = Fernet(key)
    try:
        raw = _FALLBACK_PATH.read_bytes()
        decrypted = f.decrypt(raw)
        return json.loads(decrypted)
    except Exception:
        return {}


def _fallback_save(data: dict) -> None:
    """Encrypt and save the secrets file."""
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        # Fall back to legacy XOR if cryptography not available
        _legacy_fallback_save(data)
        return

    password = _get_master_password()
    salt = _get_or_create_salt()
    key = _derive_fernet_key(password, salt)
    f = Fernet(key)

    raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
    encrypted = f.encrypt(raw)

    _FALLBACK_DIR.mkdir(parents=True, exist_ok=True)
    _FALLBACK_PATH.write_bytes(encrypted)
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


# ── Legacy XOR fallback (migration support) ──────────────────────────

_LEGACY_PATH = Path.home() / ".config" / "linguaedit" / ".secrets.json"


def _legacy_fallback_key() -> bytes:
    """Derive a machine-specific obfuscation key (NOT real encryption)."""
    machine_id = platform.node() + os.getenv("USER", "linguaedit")
    return hashlib.sha256(machine_id.encode()).digest()


def _xor_bytes(data: bytes, key: bytes) -> bytes:
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


def _legacy_fallback_load() -> dict:
    for path in (_LEGACY_PATH, _FALLBACK_PATH):
        try:
            raw = path.read_bytes()
            decrypted = _xor_bytes(base64.b64decode(raw), _legacy_fallback_key())
            return json.loads(decrypted)
        except Exception:
            continue
    return {}


def _legacy_fallback_save(data: dict) -> None:
    _FALLBACK_DIR.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
    encoded = base64.b64encode(_xor_bytes(raw, _legacy_fallback_key()))
    _LEGACY_PATH.write_bytes(encoded)
    _LEGACY_PATH.chmod(0o600)
