"""Git integration — diff, commit, branch via subprocess."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class GitStatus:
    """Git repository status."""
    is_repo: bool = False
    branch: str = ""
    modified_files: list[str] = None
    staged_files: list[str] = None
    untracked_files: list[str] = None
    has_changes: bool = False

    def __post_init__(self):
        if self.modified_files is None:
            self.modified_files = []
        if self.staged_files is None:
            self.staged_files = []
        if self.untracked_files is None:
            self.untracked_files = []


def _run_git(args: list[str], cwd: str | Path) -> tuple[bool, str]:
    """Run a git command. Returns (success, output)."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0, result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return False, str(e)


def get_status(file_path: str | Path) -> GitStatus:
    """Get git status for the directory containing the file."""
    cwd = Path(file_path).parent
    ok, branch = _run_git(["branch", "--show-current"], cwd)
    if not ok:
        return GitStatus(is_repo=False)

    status = GitStatus(is_repo=True, branch=branch)

    ok, output = _run_git(["status", "--porcelain"], cwd)
    if ok and output:
        status.has_changes = True
        for line in output.splitlines():
            if len(line) < 3:
                continue
            x, y = line[0], line[1]
            fname = line[3:]
            if x in "MADRC":
                status.staged_files.append(fname)
            if y == "M":
                status.modified_files.append(fname)
            elif y == "?":
                status.untracked_files.append(fname)

    return status


def get_diff(file_path: str | Path) -> str:
    """Get git diff for a specific file."""
    cwd = Path(file_path).parent
    fname = Path(file_path).name
    ok, output = _run_git(["diff", fname], cwd)
    return output if ok else ""


def get_diff_staged(file_path: str | Path) -> str:
    """Get staged diff."""
    cwd = Path(file_path).parent
    fname = Path(file_path).name
    ok, output = _run_git(["diff", "--cached", fname], cwd)
    return output if ok else ""


def stage_file(file_path: str | Path) -> bool:
    """Stage a file for commit."""
    cwd = Path(file_path).parent
    fname = Path(file_path).name
    ok, _ = _run_git(["add", fname], cwd)
    return ok


def commit(file_path: str | Path, message: str) -> tuple[bool, str]:
    """Commit staged changes."""
    cwd = Path(file_path).parent
    return _run_git(["commit", "-m", message], cwd)


def get_branches(file_path: str | Path) -> list[str]:
    """List all branches."""
    cwd = Path(file_path).parent
    ok, output = _run_git(["branch", "--list", "--format=%(refname:short)"], cwd)
    if ok:
        return [b.strip() for b in output.splitlines() if b.strip()]
    return []


def switch_branch(file_path: str | Path, branch: str) -> tuple[bool, str]:
    """Switch to a branch."""
    cwd = Path(file_path).parent
    return _run_git(["checkout", branch], cwd)


def create_branch(file_path: str | Path, branch: str) -> tuple[bool, str]:
    """Create and switch to a new branch."""
    cwd = Path(file_path).parent
    return _run_git(["checkout", "-b", branch], cwd)


def get_log(file_path: str | Path, count: int = 10) -> str:
    """Get recent git log for the file."""
    cwd = Path(file_path).parent
    fname = Path(file_path).name
    ok, output = _run_git(["log", f"-{count}", "--oneline", "--", fname], cwd)
    return output if ok else ""
