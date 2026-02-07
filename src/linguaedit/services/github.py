"""GitHub integration: fetch POT, create branches, push PRs."""

from __future__ import annotations

import json
import base64
import requests
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class GitHubConfig:
    token: str
    owner: str
    repo: str
    base_url: str = "https://api.github.com"

    @property
    def headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }


class GitHubError(Exception):
    pass


def fetch_pot_file(config: GitHubConfig, pot_path: str, branch: str = "main") -> str:
    """Fetch a POT file from a GitHub repo."""
    url = f"{config.base_url}/repos/{config.owner}/{config.repo}/contents/{pot_path}"
    r = requests.get(url, headers=config.headers, params={"ref": branch}, timeout=30)
    if r.status_code != 200:
        raise GitHubError(f"Failed to fetch {pot_path}: {r.status_code} {r.text}")
    content = r.json().get("content", "")
    return base64.b64decode(content).decode("utf-8")


def create_branch(config: GitHubConfig, branch_name: str, from_branch: str = "main") -> None:
    """Create a new branch."""
    # Get ref SHA
    url = f"{config.base_url}/repos/{config.owner}/{config.repo}/git/ref/heads/{from_branch}"
    r = requests.get(url, headers=config.headers, timeout=30)
    if r.status_code != 200:
        raise GitHubError(f"Failed to get ref: {r.status_code}")
    sha = r.json()["object"]["sha"]

    # Create branch
    url = f"{config.base_url}/repos/{config.owner}/{config.repo}/git/refs"
    data = {"ref": f"refs/heads/{branch_name}", "sha": sha}
    r = requests.post(url, headers=config.headers, json=data, timeout=30)
    if r.status_code not in (200, 201):
        raise GitHubError(f"Failed to create branch: {r.status_code} {r.text}")


def push_file(config: GitHubConfig, file_path: str, content: bytes,
              branch: str, message: str) -> None:
    """Push/update a file on a branch."""
    url = f"{config.base_url}/repos/{config.owner}/{config.repo}/contents/{file_path}"

    # Check if file exists to get SHA
    r = requests.get(url, headers=config.headers, params={"ref": branch}, timeout=30)
    sha = r.json().get("sha") if r.status_code == 200 else None

    data = {
        "message": message,
        "content": base64.b64encode(content).decode("ascii"),
        "branch": branch,
    }
    if sha:
        data["sha"] = sha

    r = requests.put(url, headers=config.headers, json=data, timeout=30)
    if r.status_code not in (200, 201):
        raise GitHubError(f"Failed to push file: {r.status_code} {r.text}")


def create_pull_request(config: GitHubConfig, title: str, body: str,
                        head: str, base: str = "main") -> str:
    """Create a pull request. Returns the PR URL."""
    url = f"{config.base_url}/repos/{config.owner}/{config.repo}/pulls"
    data = {"title": title, "body": body, "head": head, "base": base}
    r = requests.post(url, headers=config.headers, json=data, timeout=30)
    if r.status_code not in (200, 201):
        raise GitHubError(f"Failed to create PR: {r.status_code} {r.text}")
    return r.json().get("html_url", "")
