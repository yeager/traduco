"""In-app update checker (macOS and Windows only; skipped on Linux)."""

from __future__ import annotations

import json
import platform
import sys
import requests
from typing import Optional

from linguaedit import __version__


GITHUB_RELEASES_URL = "https://api.github.com/repos/yeager/linguaedit/releases/latest"


def check_for_updates() -> Optional[dict]:
    """Check GitHub releases for a newer version.

    Returns dict with 'version', 'url', 'notes' if update available, else None.
    Skips on Linux (use package manager instead).
    """
    if platform.system() == "Linux":
        return None

    try:
        r = requests.get(GITHUB_RELEASES_URL, timeout=10)
        if r.status_code != 200:
            return None
        data = r.json()
        latest = data.get("tag_name", "").lstrip("v")
        if not latest:
            return None

        from packaging.version import Version
        if Version(latest) > Version(__version__):
            return {
                "version": latest,
                "url": data.get("html_url", ""),
                "notes": data.get("body", ""),
                "assets": [
                    {"name": a["name"], "url": a["browser_download_url"]}
                    for a in data.get("assets", [])
                ],
            }
    except Exception:
        pass
    return None
