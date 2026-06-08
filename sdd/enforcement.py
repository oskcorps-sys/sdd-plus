"""
sdd/enforcement.py — File-pattern enforcement for the SDD+ authority matrix.

Enforcement supports two modes:
  - denylist: current/default behavior; forbidden matches are violations.
  - strict_allowlist: files must match allowed_file_patterns and must not match
    forbidden_file_patterns.

Pattern matching uses pathlib.PurePosixPath.full_match (Python 3.12+).
All file paths are normalised to forward slashes before matching.

Role resolution order:
  1. Environment variable SDD_ROLE
  2. .sdd-role file at the repo root
  3. None — enforcement is a no-op (advisory mode), exit 0

No new top-level dependencies: stdlib pathlib + subprocess + os only.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path, PurePosixPath
from typing import TypedDict

import yaml

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

SDD_HOOK_MARKER = "# SDD+ pre-commit hook"


class Violation(TypedDict):
    file: str
    pattern: str
    role: str
    reason: str


# ---------------------------------------------------------------------------
# Pattern matching
# ---------------------------------------------------------------------------


def match_pattern(pattern: str, path: str) -> bool:
    """Return True if *path* matches *pattern* using PurePosixPath.full_match.

    Both the pattern and the path are normalised to forward slashes so that
    Windows paths (e.g. ``src\\foo\\bar.py``) are handled correctly.
    """
    normalised = path.replace("\\", "/")
    return PurePosixPath(normalised).full_match(pattern)


# ---------------------------------------------------------------------------
# Role resolution
# ---------------------------------------------------------------------------


def resolve_role(repo_root: Path | None = None) -> str | None:
    """Return the active role string, or None if no role is set.

    Resolution order:
      1. Environment variable SDD_ROLE
      2. .sdd-role file at *repo_root* (or cwd if None)
    """
    env_role = os.environ.get("SDD_ROLE", "").strip()
    if env_role:
        return env_role

    root = repo_root if repo_root is not None else Path.cwd()
    role_file = root / ".sdd-role"
    if role_file.exists():
        text = role_file.read_text(encoding="utf-8").strip()
        if text:
            return text

    return None


# ---------------------------------------------------------------------------
# AGENTS.yaml loader
# ---------------------------------------------------------------------------


def load_agents_config(repo_root: Path | None = None) -> dict | None:
    """Load AGENTS.yaml from *repo_root* (or cwd).  Return None if absent."""
    root = repo_root if repo_root is not None else Path.cwd()
    agents_file = root / "AGENTS.yaml"
    if not agents_file.exists():
        return None
    with open(agents_file, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def get_forbidden_patterns(role: str, agents_config: dict) -> list[str]:
    """Extract the forbidden_file_patterns list for *role* from *agents_config*.

    Returns an empty list if the role or the key is absent.
    """
    roles = agents_config.get("roles", {}) or {}
    role_def = roles.get(role, {}) or {}
    patterns = role_def.get("forbidden_file_patterns", []) or []
    return list(patterns)


def get_allowed_patterns(role: str, agents_config: dict) -> list[str]:
    """Extract the allowed_file_patterns list for *role* from *agents_config*.

    Returns an empty list if the role or the key is absent.
    """
    roles = agents_config.get("roles", {}) or {}
    role_def = roles.get(role, {}) or {}
    patterns = role_def.get("allowed_file_patterns", []) or []
    return list(patterns)


def get_enforcement_mode(agents_config: dict) -> str:
    """Return configured enforcement mode, defaulting to denylist.

    Raises ValueError for unknown modes so callers can fail clearly.
    """
    enforcement = agents_config.get("enforcement", {}) or {}
    mode = enforcement.get("mode", "denylist")
    if mode not in {"denylist", "strict_allowlist"}:
        raise ValueError(
            "Invalid enforcement.mode: "
            f"{mode!r}. Expected 'denylist' or 'strict_allowlist'."
        )
    return mode


# ---------------------------------------------------------------------------
# Check files
# ---------------------------------------------------------------------------


def check_files(
    files: list[str],
    role: str,
    forbidden_patterns: list[str],
    allowed_patterns: list[str] | None = None,
    mode: str = "denylist",
) -> list[Violation]:
    """Return file-pattern violations for *role*.

    Each violation is a dict with keys: file, pattern, role, reason.
    An empty list means the commit is clean for the given role.
    """
    allowed = allowed_patterns or []
    violations: list[Violation] = []
    for path in files:
        for pattern in forbidden_patterns:
            if match_pattern(pattern, path):
                violations.append({
                    "file": path,
                    "pattern": pattern,
                    "role": role,
                    "reason": "forbidden_match",
                })
                break  # one violation per file is enough
        else:
            if mode == "strict_allowlist" and not any(
                match_pattern(pattern, path) for pattern in allowed
            ):
                violations.append({
                    "file": path,
                    "pattern": "",
                    "role": role,
                    "reason": "not_allowed",
                })
    return violations


# ---------------------------------------------------------------------------
# Staged files (git)
# ---------------------------------------------------------------------------


def get_staged_files(repo_root: Path | None = None) -> list[str]:
    """Return the list of staged files via ``git diff --cached --name-only``.

    Returns an empty list if git is unavailable or the path is not a repo.
    """
    root = repo_root if repo_root is not None else Path.cwd()
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if result.returncode != 0:
            return []
        return [line for line in result.stdout.splitlines() if line.strip()]
    except FileNotFoundError:
        # git not on PATH
        return []


# ---------------------------------------------------------------------------
# Pre-commit hook
# ---------------------------------------------------------------------------

_HOOK_TEMPLATE = """\
#!/bin/sh
{marker}
#
# Generated by `sdd install-hooks`.  Do not edit this header.
# To uninstall: delete this file (the backup is at pre-commit.pre-sdd).

python -m sdd.cli.main check-patterns --staged
""".format(
    marker=SDD_HOOK_MARKER
)


def generate_hook_script() -> str:
    """Return the content of the SDD pre-commit hook script."""
    return _HOOK_TEMPLATE


def install_hook(role: str, repo_root: Path | None = None) -> dict:
    """Install the SDD pre-commit hook into *repo_root*/.git/hooks/.

    If a pre-existing non-SDD hook is present it is backed up to
    ``pre-commit.pre-sdd`` before writing.  If the SDD hook is already
    installed (marker present) it is overwritten in place (an update).

    Also writes a ``.sdd-role`` file at *repo_root* recording *role*.

    Returns a dict with keys:
      - installed (bool)
      - backed_up (bool)
      - hook_path (str)
      - role_file (str)
      - message (str)
    """
    root = repo_root if repo_root is not None else Path.cwd()
    hooks_dir = root / ".git" / "hooks"
    if not hooks_dir.exists():
        return {
            "installed": False,
            "backed_up": False,
            "hook_path": "",
            "role_file": "",
            "message": "Not a git repository (no .git/hooks directory found)",
        }

    hook_path = hooks_dir / "pre-commit"
    backup_path = hooks_dir / "pre-commit.pre-sdd"
    backed_up = False

    if hook_path.exists():
        content = hook_path.read_text(encoding="utf-8")
        if SDD_HOOK_MARKER not in content:
            # Back up the existing non-SDD hook
            backup_path.write_bytes(hook_path.read_bytes())
            backed_up = True

    # Write the SDD hook
    script = generate_hook_script()
    hook_path.write_text(script, encoding="utf-8")

    # Make executable on POSIX; harmless no-op on Windows
    try:
        hook_path.chmod(hook_path.stat().st_mode | 0o111)
    except (AttributeError, NotImplementedError):
        pass  # Windows — git for Windows uses sh.exe regardless

    # Write .sdd-role
    role_file = root / ".sdd-role"
    role_file.write_text(role + "\n", encoding="utf-8")

    msg = "Hook installed"
    if backed_up:
        msg += " (previous hook backed up to pre-commit.pre-sdd)"

    return {
        "installed": True,
        "backed_up": backed_up,
        "hook_path": str(hook_path),
        "role_file": str(role_file),
        "message": msg,
    }
