"""Tests for sdd/enforcement.py — file-pattern enforcement."""

import os
from pathlib import Path

import pytest
import yaml

from sdd.enforcement import (
    SDD_HOOK_MARKER,
    check_files,
    generate_hook_script,
    get_allowed_patterns,
    get_enforcement_mode,
    get_forbidden_patterns,
    get_staged_files,
    install_hook,
    load_agents_config,
    match_pattern,
    resolve_role,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_AGENTS_YAML = {
    "version": 1,
    "roles": {
        "implementer": {
            "allowed_file_patterns": [
                "src/**/*",
                "tests/**/*",
                "README.md",
            ],
            "forbidden_file_patterns": [
                "sdd/artifacts/*SPEC*.yaml",
                "sdd/artifacts/*AUDIT*.yaml",
                "AGENTS.yaml",
            ],
        },
        "auditor": {
            "allowed_file_patterns": [
                "sdd/artifacts/*SPEC*.yaml",
                "sdd/artifacts/*AUDIT*.yaml",
                "README.md",
            ],
            "forbidden_file_patterns": [
                "src/**/*",
            ],
        },
    },
}


def _write_agents(root: Path, data: dict | None = None) -> None:
    content = data if data is not None else _AGENTS_YAML
    (root / "AGENTS.yaml").write_text(
        yaml.dump(content, allow_unicode=True), encoding="utf-8"
    )


def _make_git_repo(root: Path) -> None:
    """Initialise a minimal bare git repo at *root* for hook tests."""
    import subprocess
    subprocess.run(["git", "init"], cwd=str(root), capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(root), capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(root), capture_output=True)


# ---------------------------------------------------------------------------
# match_pattern
# ---------------------------------------------------------------------------


class TestMatchPattern:
    def test_double_star_matches_nested(self):
        assert match_pattern("src/**/*", "src/foo/bar.py") is True

    def test_double_star_matches_single_level(self):
        assert match_pattern("src/**/*", "src/foo.py") is True

    def test_double_star_no_match_different_root(self):
        assert match_pattern("src/**/*", "tests/test_foo.py") is False

    def test_star_spec_wildcard(self):
        assert match_pattern("sdd/artifacts/*SPEC*.yaml", "sdd/artifacts/PHASE_4_SPEC.yaml") is True

    def test_star_audit_wildcard(self):
        assert match_pattern("sdd/artifacts/*AUDIT*.yaml", "sdd/artifacts/PHASE_3_AUDIT.yaml") is True

    def test_exact_match(self):
        assert match_pattern("AGENTS.yaml", "AGENTS.yaml") is True

    def test_exact_no_match(self):
        assert match_pattern("AGENTS.yaml", "README.md") is False

    def test_neutral_file_no_match_src(self):
        assert match_pattern("src/**/*", "README.md") is False

    def test_windows_backslash_normalised(self):
        # Windows paths with backslashes should be normalised to forward slashes
        assert match_pattern("src/**/*", r"src\foo\bar.py") is True

    def test_root_level_wildcard(self):
        assert match_pattern("*.yaml", "pyproject.toml") is False
        assert match_pattern("*.yaml", "AGENTS.yaml") is True


# ---------------------------------------------------------------------------
# check_files (denylist semantics)
# ---------------------------------------------------------------------------


class TestCheckFiles:
    def test_implementer_cannot_stage_spec(self):
        """Implementer cannot stage a SPEC artifact."""
        forbidden = _AGENTS_YAML["roles"]["implementer"]["forbidden_file_patterns"]
        v = check_files(["sdd/artifacts/PHASE_4_SPEC.yaml"], "implementer", forbidden)
        assert len(v) == 1
        assert v[0]["file"] == "sdd/artifacts/PHASE_4_SPEC.yaml"
        assert v[0]["role"] == "implementer"

    def test_auditor_cannot_stage_src(self):
        """Auditor cannot stage source code."""
        forbidden = _AGENTS_YAML["roles"]["auditor"]["forbidden_file_patterns"]
        v = check_files(["src/foo.py"], "auditor", forbidden)
        assert len(v) == 1
        assert v[0]["file"] == "src/foo.py"

    def test_neutral_file_allowed_for_implementer(self):
        forbidden = _AGENTS_YAML["roles"]["implementer"]["forbidden_file_patterns"]
        v = check_files(["README.md", "pyproject.toml"], "implementer", forbidden)
        assert v == []

    def test_neutral_file_allowed_for_auditor(self):
        forbidden = _AGENTS_YAML["roles"]["auditor"]["forbidden_file_patterns"]
        v = check_files(["README.md", "pyproject.toml"], "auditor", forbidden)
        assert v == []

    def test_one_violation_per_file(self):
        """A file matching multiple patterns only creates one violation."""
        forbidden = ["sdd/**/*", "sdd/artifacts/*SPEC*.yaml"]
        v = check_files(["sdd/artifacts/PHASE_4_SPEC.yaml"], "implementer", forbidden)
        assert len(v) == 1

    def test_empty_files_returns_empty(self):
        forbidden = _AGENTS_YAML["roles"]["implementer"]["forbidden_file_patterns"]
        assert check_files([], "implementer", forbidden) == []

    def test_empty_patterns_returns_empty(self):
        assert check_files(["sdd/artifacts/PHASE_4_SPEC.yaml"], "implementer", []) == []

    def test_denylist_mode_allows_neutral_files(self):
        forbidden = _AGENTS_YAML["roles"]["implementer"]["forbidden_file_patterns"]
        allowed = _AGENTS_YAML["roles"]["implementer"]["allowed_file_patterns"]
        v = check_files(
            ["pyproject.toml"],
            "implementer",
            forbidden,
            allowed_patterns=allowed,
            mode="denylist",
        )
        assert v == []

    def test_strict_allowlist_allows_allowed_files(self):
        forbidden = _AGENTS_YAML["roles"]["implementer"]["forbidden_file_patterns"]
        allowed = _AGENTS_YAML["roles"]["implementer"]["allowed_file_patterns"]
        v = check_files(
            ["src/foo.py", "tests/test_foo.py"],
            "implementer",
            forbidden,
            allowed_patterns=allowed,
            mode="strict_allowlist",
        )
        assert v == []

    def test_strict_allowlist_rejects_forbidden_files(self):
        forbidden = _AGENTS_YAML["roles"]["implementer"]["forbidden_file_patterns"]
        allowed = _AGENTS_YAML["roles"]["implementer"]["allowed_file_patterns"]
        v = check_files(
            ["sdd/artifacts/PHASE_4_SPEC.yaml"],
            "implementer",
            forbidden,
            allowed_patterns=allowed,
            mode="strict_allowlist",
        )
        assert len(v) == 1
        assert v[0]["reason"] == "forbidden_match"
        assert v[0]["pattern"] == "sdd/artifacts/*SPEC*.yaml"

    def test_strict_allowlist_rejects_neutral_files(self):
        forbidden = _AGENTS_YAML["roles"]["implementer"]["forbidden_file_patterns"]
        allowed = _AGENTS_YAML["roles"]["implementer"]["allowed_file_patterns"]
        v = check_files(
            ["pyproject.toml"],
            "implementer",
            forbidden,
            allowed_patterns=allowed,
            mode="strict_allowlist",
        )
        assert len(v) == 1
        assert v[0] == {
            "file": "pyproject.toml",
            "pattern": "",
            "role": "implementer",
            "reason": "not_allowed",
        }


# ---------------------------------------------------------------------------
# resolve_role
# ---------------------------------------------------------------------------


class TestResolveRole:
    def test_env_var_takes_precedence(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SDD_ROLE", "auditor")
        (tmp_path / ".sdd-role").write_text("implementer\n", encoding="utf-8")
        assert resolve_role(tmp_path) == "auditor"

    def test_role_file_fallback(self, tmp_path, monkeypatch):
        monkeypatch.delenv("SDD_ROLE", raising=False)
        (tmp_path / ".sdd-role").write_text("implementer\n", encoding="utf-8")
        assert resolve_role(tmp_path) == "implementer"

    def test_no_role_is_none(self, tmp_path, monkeypatch):
        monkeypatch.delenv("SDD_ROLE", raising=False)
        assert resolve_role(tmp_path) is None

    def test_empty_role_file_is_none(self, tmp_path, monkeypatch):
        monkeypatch.delenv("SDD_ROLE", raising=False)
        (tmp_path / ".sdd-role").write_text("   \n", encoding="utf-8")
        assert resolve_role(tmp_path) is None


# ---------------------------------------------------------------------------
# load_agents_config / get_forbidden_patterns
# ---------------------------------------------------------------------------


class TestLoadAgentsConfig:
    def test_absent_returns_none(self, tmp_path):
        assert load_agents_config(tmp_path) is None

    def test_loads_yaml(self, tmp_path):
        _write_agents(tmp_path)
        cfg = load_agents_config(tmp_path)
        assert cfg is not None
        assert "roles" in cfg

    def test_get_forbidden_patterns_implementer(self, tmp_path):
        _write_agents(tmp_path)
        cfg = load_agents_config(tmp_path)
        patterns = get_forbidden_patterns("implementer", cfg)
        assert "sdd/artifacts/*SPEC*.yaml" in patterns

    def test_get_forbidden_patterns_unknown_role(self, tmp_path):
        _write_agents(tmp_path)
        cfg = load_agents_config(tmp_path)
        assert get_forbidden_patterns("nonexistent", cfg) == []

    def test_get_allowed_patterns_implementer(self, tmp_path):
        _write_agents(tmp_path)
        cfg = load_agents_config(tmp_path)
        patterns = get_allowed_patterns("implementer", cfg)
        assert "src/**/*" in patterns

    def test_missing_enforcement_mode_defaults_to_denylist(self, tmp_path):
        _write_agents(tmp_path)
        cfg = load_agents_config(tmp_path)
        assert get_enforcement_mode(cfg) == "denylist"

    def test_invalid_enforcement_mode_rejected(self, tmp_path):
        agents = {
            "version": 1,
            "enforcement": {"mode": "unknown"},
            "roles": {"implementer": {"description": "Writes code"}},
        }
        _write_agents(tmp_path, agents)
        cfg = load_agents_config(tmp_path)
        with pytest.raises(ValueError, match="Invalid enforcement.mode"):
            get_enforcement_mode(cfg)


# ---------------------------------------------------------------------------
# generate_hook_script
# ---------------------------------------------------------------------------


class TestGenerateHookScript:
    def test_contains_marker(self):
        assert SDD_HOOK_MARKER in generate_hook_script()

    def test_contains_check_patterns(self):
        assert "check-patterns --staged" in generate_hook_script()

    def test_starts_with_shebang(self):
        assert generate_hook_script().startswith("#!/bin/sh")


# ---------------------------------------------------------------------------
# install_hook
# ---------------------------------------------------------------------------


class TestInstallHook:
    def test_install_writes_hook_and_role_file(self, tmp_path):
        _make_git_repo(tmp_path)
        result = install_hook("implementer", tmp_path)
        assert result["installed"] is True
        assert result["backed_up"] is False
        hook = tmp_path / ".git" / "hooks" / "pre-commit"
        assert hook.exists()
        assert SDD_HOOK_MARKER in hook.read_text(encoding="utf-8")
        role_file = tmp_path / ".sdd-role"
        assert role_file.exists()
        assert role_file.read_text(encoding="utf-8").strip() == "implementer"

    def test_install_preserves_existing_hook(self, tmp_path):
        _make_git_repo(tmp_path)
        hooks_dir = tmp_path / ".git" / "hooks"
        existing = hooks_dir / "pre-commit"
        existing.write_text("#!/bin/sh\necho original hook\n", encoding="utf-8")

        result = install_hook("implementer", tmp_path)
        assert result["installed"] is True
        assert result["backed_up"] is True

        backup = hooks_dir / "pre-commit.pre-sdd"
        assert backup.exists()
        assert "original hook" in backup.read_text(encoding="utf-8")

    def test_install_updates_existing_sdd_hook(self, tmp_path):
        """Re-installing an SDD hook updates in place without a backup."""
        _make_git_repo(tmp_path)
        install_hook("implementer", tmp_path)
        result = install_hook("auditor", tmp_path)
        assert result["installed"] is True
        assert result["backed_up"] is False

    def test_not_a_git_repo_returns_failure(self, tmp_path):
        result = install_hook("implementer", tmp_path)
        assert result["installed"] is False
        assert "not a git repository" in result["message"].lower()


# ---------------------------------------------------------------------------
# get_staged_files
# ---------------------------------------------------------------------------


class TestGetStagedFiles:
    def test_no_staged_files_returns_empty(self, tmp_path):
        _make_git_repo(tmp_path)
        assert get_staged_files(tmp_path) == []

    def test_staged_file_appears(self, tmp_path):
        import subprocess
        _make_git_repo(tmp_path)
        f = tmp_path / "hello.txt"
        f.write_text("hello", encoding="utf-8")
        subprocess.run(["git", "add", "hello.txt"], cwd=str(tmp_path), capture_output=True)
        staged = get_staged_files(tmp_path)
        assert "hello.txt" in staged

    def test_not_a_repo_returns_empty(self, tmp_path):
        assert get_staged_files(tmp_path) == []


# ---------------------------------------------------------------------------
# Named acceptance-test functions (must match PHASE_4_CONTRACT.yaml names)
# ---------------------------------------------------------------------------


def test_pattern_matches_glob():
    """Glob patterns src/**/*, sdd/artifacts/*SPEC*.yaml, AGENTS.yaml work correctly."""
    assert match_pattern("src/**/*", "src/foo/bar.py") is True
    assert match_pattern("src/**/*", "src/nested/deep/file.py") is True
    assert match_pattern("sdd/artifacts/*SPEC*.yaml", "sdd/artifacts/PHASE_4_SPEC.yaml") is True
    assert match_pattern("AGENTS.yaml", "AGENTS.yaml") is True
    assert match_pattern("src/**/*", "tests/test_foo.py") is False
    assert match_pattern("AGENTS.yaml", "README.md") is False


def test_neutral_file_allowed(tmp_path):
    """Neutral files (README.md, pyproject.toml) match no forbidden pattern for either role."""
    _write_agents(tmp_path)
    cfg = load_agents_config(tmp_path)
    impl_forbidden = get_forbidden_patterns("implementer", cfg)
    aud_forbidden = get_forbidden_patterns("auditor", cfg)
    assert check_files(["README.md", "pyproject.toml"], "implementer", impl_forbidden) == []
    assert check_files(["README.md", "pyproject.toml"], "auditor", aud_forbidden) == []


def test_install_hooks_writes_precommit(tmp_path):
    """install_hook writes pre-commit with SDD marker and records .sdd-role."""
    _make_git_repo(tmp_path)
    result = install_hook("implementer", tmp_path)
    assert result["installed"] is True
    hook = tmp_path / ".git" / "hooks" / "pre-commit"
    assert hook.exists()
    assert SDD_HOOK_MARKER in hook.read_text(encoding="utf-8")
    role_file = tmp_path / ".sdd-role"
    assert role_file.read_text(encoding="utf-8").strip() == "implementer"


def test_install_hooks_preserves_existing(tmp_path):
    """install_hook backs up a pre-existing non-SDD pre-commit hook."""
    _make_git_repo(tmp_path)
    hooks_dir = tmp_path / ".git" / "hooks"
    (hooks_dir / "pre-commit").write_text("#!/bin/sh\necho original\n", encoding="utf-8")
    result = install_hook("auditor", tmp_path)
    assert result["installed"] is True
    assert result["backed_up"] is True
    backup = hooks_dir / "pre-commit.pre-sdd"
    assert backup.exists()
    assert "original" in backup.read_text(encoding="utf-8")
