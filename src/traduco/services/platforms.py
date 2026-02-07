"""Integration for Transifex, Weblate, and Crowdin translation platforms."""
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import json
import time
import requests
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional
from gettext import gettext as _

from traduco.services.keystore import store_secret, get_secret, delete_secret

# ── Configuration persistence ─────────────────────────────────────────
#
# Non-sensitive settings (project, org, URLs) go in platforms.json.
# Secrets (API tokens/keys) go in the system keychain via keystore.py.
#

_CONFIG_PATH = Path.home() / ".config" / "traduco" / "platforms.json"

# Map of (platform, field) that are secret and must use keychain
_SECRET_FIELDS = {
    "transifex": ["api_token"],
    "weblate": ["api_key"],
    "crowdin": ["api_token"],
}


def load_platform_config() -> dict:
    """Load saved platform configurations (secrets resolved from keychain)."""
    try:
        data = json.loads(_CONFIG_PATH.read_text("utf-8"))
    except Exception:
        data = {}
    # Inject secrets from keychain
    for platform, secret_keys in _SECRET_FIELDS.items():
        if platform not in data:
            data[platform] = {}
        for key in secret_keys:
            val = get_secret(platform, key)
            if val:
                data[platform][key] = val
    return data


def save_platform_config(data: dict) -> None:
    """Save platform configurations. Secrets go to keychain, rest to JSON."""
    safe_data = {}
    for platform, cfg in data.items():
        safe_cfg = {}
        secret_keys = _SECRET_FIELDS.get(platform, [])
        for k, v in cfg.items():
            if k in secret_keys:
                # Store in keychain, not in JSON
                if v:
                    store_secret(platform, k, str(v))
                else:
                    delete_secret(platform, k)
            else:
                safe_cfg[k] = v
        safe_data[platform] = safe_cfg
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_PATH.write_text(json.dumps(safe_data, ensure_ascii=False, indent=2), "utf-8")


# ── Exceptions ────────────────────────────────────────────────────────

class PlatformError(Exception):
    pass


class PlatformTimeoutError(PlatformError):
    pass


class PlatformAuthError(PlatformError):
    pass


# ── Retry helper ──────────────────────────────────────────────────────

def _request_with_retry(method: str, url: str, max_retries: int = 3,
                        timeout: int = 30, **kwargs) -> requests.Response:
    """Make an HTTP request with retry logic."""
    last_exc = None
    for attempt in range(max_retries):
        try:
            r = requests.request(method, url, timeout=timeout, **kwargs)
            if r.status_code == 401:
                raise PlatformAuthError(_("Authentication failed. Check your API token."))
            if r.status_code == 403:
                raise PlatformAuthError(_("Access denied. Check permissions for your token."))
            if r.status_code == 429:
                # Rate limited — wait and retry
                wait = min(2 ** attempt * 2, 30)
                time.sleep(wait)
                continue
            if r.status_code >= 500:
                wait = min(2 ** attempt, 10)
                time.sleep(wait)
                continue
            return r
        except requests.Timeout as e:
            last_exc = e
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise PlatformTimeoutError(_("Request timed out after {n} attempts").format(n=max_retries)) from e
        except requests.ConnectionError as e:
            last_exc = e
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise PlatformError(_("Connection failed: {error}").format(error=str(e))) from e
    # If we exhausted retries due to 429/5xx
    raise PlatformError(_("Request failed after {n} retries").format(n=max_retries))


# ── Transifex ─────────────────────────────────────────────────────────

@dataclass
class TransifexConfig:
    api_token: str
    organization: str
    project: str
    base_url: str = "https://rest.api.transifex.com"

    @property
    def headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/vnd.api+json",
        }


def transifex_list_projects(config: TransifexConfig) -> list[dict]:
    """List all projects the user has access to in the organization."""
    url = f"{config.base_url}/projects"
    params = {"filter[organization]": f"o:{config.organization}"}
    results = []
    while url:
        r = _request_with_retry("GET", url, headers=config.headers, params=params)
        if r.status_code != 200:
            raise PlatformError(_("Transifex: {code} {text}").format(code=r.status_code, text=r.text[:200]))
        data = r.json()
        for item in data.get("data", []):
            attrs = item.get("attributes", {})
            results.append({
                "id": item.get("id", ""),
                "name": attrs.get("name", ""),
                "slug": attrs.get("slug", ""),
                "description": attrs.get("description", ""),
                "source_language": attrs.get("source_language_code", ""),
            })
        url = data.get("links", {}).get("next")
        params = {}  # pagination URL includes params
    return results


def transifex_list_organizations(config: TransifexConfig) -> list[dict]:
    """List all organizations the user is a member of."""
    url = f"{config.base_url}/organizations"
    r = _request_with_retry("GET", url, headers=config.headers)
    if r.status_code != 200:
        raise PlatformError(_("Transifex: {code} {text}").format(code=r.status_code, text=r.text[:200]))
    results = []
    for item in r.json().get("data", []):
        attrs = item.get("attributes", {})
        results.append({
            "id": item.get("id", ""),
            "name": attrs.get("name", ""),
            "slug": attrs.get("slug", ""),
        })
    return results


def transifex_test_connection(config: TransifexConfig) -> str:
    """Test Transifex connection. Returns organization name on success."""
    url = f"{config.base_url}/organizations/o:{config.organization}"
    r = _request_with_retry("GET", url, headers=config.headers)
    if r.status_code != 200:
        raise PlatformError(_("Transifex: {code} {text}").format(code=r.status_code, text=r.text[:200]))
    data = r.json().get("data", {})
    return data.get("attributes", {}).get("name", config.organization)


def transifex_list_resources(config: TransifexConfig) -> list[dict]:
    """List resources in a Transifex project."""
    url = f"{config.base_url}/resources"
    params = {"filter[project]": f"o:{config.organization}:p:{config.project}"}
    r = _request_with_retry("GET", url, headers=config.headers, params=params)
    if r.status_code != 200:
        raise PlatformError(_("Transifex: {code} {text}").format(code=r.status_code, text=r.text[:200]))
    return r.json().get("data", [])


def transifex_list_languages(config: TransifexConfig) -> list[dict]:
    """List available languages for a Transifex project."""
    url = f"{config.base_url}/projects/o:{config.organization}:p:{config.project}/languages"
    r = _request_with_retry("GET", url, headers=config.headers)
    if r.status_code != 200:
        raise PlatformError(_("Transifex: {code} {text}").format(code=r.status_code, text=r.text[:200]))
    return r.json().get("data", [])


def transifex_download(config: TransifexConfig, resource_id: str, language: str,
                       poll_interval: float = 2.0, max_wait: float = 120.0) -> bytes:
    """Download a translation file from Transifex with async polling."""
    url = f"{config.base_url}/resource_translations_async_downloads"
    payload = {
        "data": {
            "attributes": {"content_encoding": "text"},
            "relationships": {
                "resource": {"data": {"type": "resources", "id": resource_id}},
                "language": {"data": {"type": "languages", "id": f"l:{language}"}},
            },
            "type": "resource_translations_async_downloads",
        }
    }
    r = _request_with_retry("POST", url, headers=config.headers, json=payload)
    if r.status_code not in (200, 201, 202, 303):
        raise PlatformError(_("Transifex download failed: {code}").format(code=r.status_code))

    # If we get a redirect, follow it
    if r.status_code == 303 or "Location" in r.headers:
        download_url = r.headers.get("Location") or r.json().get("data", {}).get("links", {}).get("self")
        if download_url:
            dr = _request_with_retry("GET", download_url, headers={"Authorization": f"Bearer {config.api_token}"})
            return dr.content

    # Poll for completion
    download_url = r.json().get("data", {}).get("links", {}).get("self", "")
    if not download_url:
        # Try to get from response ID
        dl_id = r.json().get("data", {}).get("id", "")
        if dl_id:
            download_url = f"{config.base_url}/resource_translations_async_downloads/{dl_id}"

    if not download_url:
        raise PlatformError(_("Transifex: could not determine download URL"))

    elapsed = 0.0
    while elapsed < max_wait:
        time.sleep(poll_interval)
        elapsed += poll_interval
        pr = _request_with_retry("GET", download_url,
                                 headers={"Authorization": f"Bearer {config.api_token}"})
        if pr.status_code == 200:
            ct = pr.headers.get("Content-Type", "")
            if "json" not in ct:
                return pr.content
            # Still pending
            status = pr.json().get("data", {}).get("attributes", {}).get("status")
            if status == "failed":
                raise PlatformError(_("Transifex download failed on server"))
        elif pr.status_code == 303:
            final_url = pr.headers.get("Location", "")
            if final_url:
                fr = _request_with_retry("GET", final_url,
                                         headers={"Authorization": f"Bearer {config.api_token}"})
                return fr.content

    raise PlatformTimeoutError(_("Transifex download timed out after {sec}s").format(sec=int(max_wait)))


def transifex_upload(config: TransifexConfig, resource_id: str, content: bytes,
                     content_type: str = "application/octet-stream") -> dict:
    """Upload a translation file to Transifex."""
    url = f"{config.base_url}/resource_strings_async_uploads"
    payload = {
        "data": {
            "attributes": {
                "content": content.decode("utf-8"),
                "content_encoding": "text",
            },
            "relationships": {
                "resource": {"data": {"type": "resources", "id": resource_id}},
            },
            "type": "resource_strings_async_uploads",
        }
    }
    r = _request_with_retry("POST", url, headers=config.headers, json=payload)
    if r.status_code not in (200, 201, 202):
        raise PlatformError(_("Transifex upload failed: {code} {text}").format(
            code=r.status_code, text=r.text[:200]))
    return r.json()


def transifex_upload_translation(config: TransifexConfig, resource_id: str,
                                 language: str, content: bytes) -> dict:
    """Upload a translation file to Transifex."""
    url = f"{config.base_url}/resource_translations_async_uploads"
    payload = {
        "data": {
            "attributes": {
                "content": content.decode("utf-8"),
                "content_encoding": "text",
            },
            "relationships": {
                "resource": {"data": {"type": "resources", "id": resource_id}},
                "language": {"data": {"type": "languages", "id": f"l:{language}"}},
            },
            "type": "resource_translations_async_uploads",
        }
    }
    r = _request_with_retry("POST", url, headers=config.headers, json=payload)
    if r.status_code not in (200, 201, 202):
        raise PlatformError(_("Transifex translation upload failed: {code}").format(code=r.status_code))
    return r.json()


# ── Weblate ───────────────────────────────────────────────────────────

@dataclass
class WeblateConfig:
    api_url: str  # e.g. https://hosted.weblate.org/api/
    api_key: str
    project: str
    component: str

    @property
    def headers(self) -> dict:
        return {"Authorization": f"Token {self.api_key}"}


def weblate_list_projects(config: WeblateConfig) -> list[dict]:
    """List all projects the user has access to."""
    url = f"{config.api_url}projects/"
    results = []
    while url:
        r = _request_with_retry("GET", url, headers=config.headers)
        if r.status_code != 200:
            raise PlatformError(_("Weblate: {code} {text}").format(code=r.status_code, text=r.text[:200]))
        data = r.json()
        for item in data.get("results", []):
            results.append({
                "slug": item.get("slug", ""),
                "name": item.get("name", ""),
                "web_url": item.get("web_url", ""),
                "source_language": item.get("source_language", {}).get("code", ""),
                "component_count": len(item.get("components", [])),
            })
        url = data.get("next")
    return results


def weblate_test_connection(config: WeblateConfig) -> str:
    """Test Weblate connection. Returns project name on success."""
    url = f"{config.api_url}projects/{config.project}/"
    r = _request_with_retry("GET", url, headers=config.headers)
    if r.status_code != 200:
        raise PlatformError(_("Weblate: {code} {text}").format(code=r.status_code, text=r.text[:200]))
    return r.json().get("name", config.project)


def weblate_list_components(config: WeblateConfig) -> list[dict]:
    """List components in a Weblate project."""
    url = f"{config.api_url}projects/{config.project}/components/"
    r = _request_with_retry("GET", url, headers=config.headers)
    if r.status_code != 200:
        raise PlatformError(_("Weblate: {code} {text}").format(code=r.status_code, text=r.text[:200]))
    return r.json().get("results", [])


def weblate_list_translations(config: WeblateConfig) -> list[dict]:
    """List translations for a Weblate component."""
    url = f"{config.api_url}components/{config.project}/{config.component}/translations/"
    r = _request_with_retry("GET", url, headers=config.headers)
    if r.status_code != 200:
        raise PlatformError(_("Weblate: {code} {text}").format(code=r.status_code, text=r.text[:200]))
    return r.json().get("results", [])


def weblate_download(config: WeblateConfig, language: str) -> bytes:
    """Download a translation file from Weblate."""
    url = f"{config.api_url}translations/{config.project}/{config.component}/{language}/file/"
    r = _request_with_retry("GET", url, headers=config.headers, timeout=60)
    if r.status_code != 200:
        raise PlatformError(_("Weblate download failed: {code}").format(code=r.status_code))
    return r.content


def weblate_upload(config: WeblateConfig, language: str, file_content: bytes,
                   filename: str = "translation.po", method: str = "translate") -> dict:
    """Upload a translation file to Weblate.

    method: translate, approve, suggest, fuzzy, replace, source
    """
    url = f"{config.api_url}translations/{config.project}/{config.component}/{language}/file/"
    files = {"file": (filename, file_content)}
    data = {"method": method}
    r = _request_with_retry("POST", url, headers=config.headers, files=files, data=data, timeout=60)
    if r.status_code not in (200, 201):
        raise PlatformError(_("Weblate upload failed: {code} {text}").format(
            code=r.status_code, text=r.text[:200]))
    return r.json()


# ── Crowdin ───────────────────────────────────────────────────────────

@dataclass
class CrowdinConfig:
    api_token: str
    project_id: int
    base_url: str = "https://api.crowdin.com/api/v2"

    @property
    def headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_token}"}


def crowdin_list_projects(config: CrowdinConfig) -> list[dict]:
    """List all projects the user has access to."""
    url = f"{config.base_url}/projects"
    params = {"limit": 100, "hasManagerAccess": 0}
    results = []
    offset = 0
    while True:
        params["offset"] = offset
        r = _request_with_retry("GET", url, headers=config.headers, params=params)
        if r.status_code != 200:
            raise PlatformError(_("Crowdin: {code} {text}").format(code=r.status_code, text=r.text[:200]))
        data = r.json().get("data", [])
        if not data:
            break
        for item in data:
            d = item.get("data", {})
            results.append({
                "id": d.get("id"),
                "name": d.get("name", ""),
                "identifier": d.get("identifier", ""),
                "description": d.get("description", ""),
                "source_language": d.get("sourceLanguageId", ""),
                "visibility": d.get("visibility", ""),
            })
        offset += len(data)
        if len(data) < 100:
            break
    return results


def crowdin_test_connection(config: CrowdinConfig) -> str:
    """Test Crowdin connection. Returns project name on success."""
    url = f"{config.base_url}/projects/{config.project_id}"
    r = _request_with_retry("GET", url, headers=config.headers)
    if r.status_code != 200:
        raise PlatformError(_("Crowdin: {code} {text}").format(code=r.status_code, text=r.text[:200]))
    return r.json().get("data", {}).get("name", str(config.project_id))


def crowdin_list_files(config: CrowdinConfig) -> list[dict]:
    """List files in a Crowdin project."""
    url = f"{config.base_url}/projects/{config.project_id}/files"
    r = _request_with_retry("GET", url, headers=config.headers)
    if r.status_code != 200:
        raise PlatformError(_("Crowdin: {code} {text}").format(code=r.status_code, text=r.text[:200]))
    return r.json().get("data", [])


def crowdin_list_languages(config: CrowdinConfig) -> list[dict]:
    """List target languages for a Crowdin project."""
    url = f"{config.base_url}/projects/{config.project_id}"
    r = _request_with_retry("GET", url, headers=config.headers)
    if r.status_code != 200:
        raise PlatformError(_("Crowdin: {code} {text}").format(code=r.status_code, text=r.text[:200]))
    return r.json().get("data", {}).get("targetLanguages", [])


def crowdin_upload_source(config: CrowdinConfig, file_content: bytes,
                          filename: str, storage_id: Optional[int] = None) -> dict:
    """Upload a source file to Crowdin (two-step: storage + add file)."""
    # Step 1: Upload to storage
    storage_url = f"{config.base_url}/storages"
    storage_headers = {**config.headers, "Crowdin-API-FileName": filename, "Content-Type": "application/octet-stream"}
    r = _request_with_retry("POST", storage_url, headers=storage_headers, data=file_content, timeout=60)
    if r.status_code not in (200, 201):
        raise PlatformError(_("Crowdin storage upload failed: {code}").format(code=r.status_code))
    sid = r.json().get("data", {}).get("id")

    # Step 2: Add file to project
    files_url = f"{config.base_url}/projects/{config.project_id}/files"
    payload = {"storageId": sid, "name": filename}
    r2 = _request_with_retry("POST", files_url, headers=config.headers, json=payload, timeout=60)
    if r2.status_code not in (200, 201):
        # Maybe file already exists — try update
        return crowdin_update_source(config, sid, filename)
    return r2.json()


def crowdin_update_source(config: CrowdinConfig, storage_id: int, filename: str) -> dict:
    """Update an existing source file in Crowdin."""
    # Find existing file ID
    files = crowdin_list_files(config)
    file_id = None
    for f in files:
        fd = f.get("data", f)
        if fd.get("name") == filename:
            file_id = fd.get("id")
            break
    if not file_id:
        raise PlatformError(_("Crowdin: file '{name}' not found for update").format(name=filename))

    url = f"{config.base_url}/projects/{config.project_id}/files/{file_id}"
    payload = {"storageId": storage_id}
    r = _request_with_retry("PUT", url, headers=config.headers, json=payload, timeout=60)
    if r.status_code != 200:
        raise PlatformError(_("Crowdin file update failed: {code}").format(code=r.status_code))
    return r.json()


def crowdin_upload_translation(config: CrowdinConfig, file_id: int, language: str,
                               file_content: bytes, filename: str) -> dict:
    """Upload a translation file to Crowdin."""
    # Step 1: Upload to storage
    storage_url = f"{config.base_url}/storages"
    storage_headers = {**config.headers, "Crowdin-API-FileName": filename, "Content-Type": "application/octet-stream"}
    r = _request_with_retry("POST", storage_url, headers=storage_headers, data=file_content, timeout=60)
    if r.status_code not in (200, 201):
        raise PlatformError(_("Crowdin storage upload failed: {code}").format(code=r.status_code))
    sid = r.json().get("data", {}).get("id")

    # Step 2: Upload translation
    url = f"{config.base_url}/projects/{config.project_id}/translations/{language}"
    payload = {"storageId": sid, "fileId": file_id}
    r2 = _request_with_retry("POST", url, headers=config.headers, json=payload, timeout=60)
    if r2.status_code not in (200, 201):
        raise PlatformError(_("Crowdin translation upload failed: {code}").format(code=r2.status_code))
    return r2.json()


def crowdin_build_translations(config: CrowdinConfig) -> int:
    """Trigger a translation build. Returns build ID."""
    url = f"{config.base_url}/projects/{config.project_id}/translations/builds"
    r = _request_with_retry("POST", url, headers=config.headers, json={})
    if r.status_code not in (200, 201):
        raise PlatformError(_("Crowdin build trigger failed: {code}").format(code=r.status_code))
    return r.json().get("data", {}).get("id", 0)


def crowdin_poll_build(config: CrowdinConfig, build_id: int,
                       poll_interval: float = 3.0, max_wait: float = 180.0) -> str:
    """Poll a Crowdin build until done. Returns download URL."""
    url = f"{config.base_url}/projects/{config.project_id}/translations/builds/{build_id}"
    elapsed = 0.0
    while elapsed < max_wait:
        r = _request_with_retry("GET", url, headers=config.headers)
        if r.status_code != 200:
            raise PlatformError(_("Crowdin build status failed: {code}").format(code=r.status_code))
        data = r.json().get("data", {})
        status = data.get("status")
        if status == "finished":
            return crowdin_download_build(config, build_id)
        if status == "failed":
            raise PlatformError(_("Crowdin build failed"))
        time.sleep(poll_interval)
        elapsed += poll_interval
    raise PlatformTimeoutError(_("Crowdin build timed out after {sec}s").format(sec=int(max_wait)))


def crowdin_download_build(config: CrowdinConfig, build_id: int) -> str:
    """Get download URL for a Crowdin build."""
    url = f"{config.base_url}/projects/{config.project_id}/translations/builds/{build_id}/download"
    r = _request_with_retry("GET", url, headers=config.headers)
    if r.status_code != 200:
        raise PlatformError(_("Crowdin download failed: {code}").format(code=r.status_code))
    return r.json().get("data", {}).get("url", "")


def crowdin_download_file(url: str) -> bytes:
    """Download file content from a Crowdin build URL."""
    r = _request_with_retry("GET", url, timeout=60)
    if r.status_code != 200:
        raise PlatformError(_("Crowdin file download failed: {code}").format(code=r.status_code))
    return r.content
