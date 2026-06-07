"""Tests for sdd install-hooks and check-patterns CLI commands."""

import subprocess
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from sdd.cli.main import app

runner = CliRunner()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_AGENTS_YAML = {
    "version": 1,
    "roles": {
        "implementer": {
            "forbidden_file_patterns": [
                "sdd/artifacts/*SPEC*.yaml",
                "sdd/artifacts/*AUDIT*.yaml",
                "AGENTS.yaml",
            ],
        },
        "auditor": {
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


def _init_git_repo(root: Path) -> None:
    subprocess.run(["git", "init"], cwd=str(root), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@t.com"], cwd=str(root), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(root), capture_output=True, check=True)
    (root / "init.txt").write_text("init", encoding="utf-8")
    subprocess.run(["git", "add", "init.txt"], cwd=str(root), capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(root), capture_output=True, check=True)


# ---------------------------------------------------------------------------
# install-hooks
# ---------------------------------------------------------------------------


class TestInstallHooksCLI:
    def test_installs_hook_in_git_repo(self, tmp_path, monkeypatch):
        _init_git_repo(tmp_path)
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["install-hooks", "--role", "implementer", "--repo-root", str(tmp_path)])
        assert result.exit_code == 0, result.output
        hook = tmp_path / ".git" / "hooks" / "pre-commit"
        assert hook.exists()
        assert "SDD+ pre-commit hook" in hook.read_text(encoding="utf-8")
        role_file = tmp_path / ".sdd-role"
        assert role_file.read_text(encoding="utf-8").strip() == "implementer"

    def test_fails_gracefully_outside_git_repo(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["install-hooks", "--role", "auditor", "--repo-root", str(tmp_path)])
        assert result.exit_code != 0

    def test_backs_up_existing_non_sdd_hook(self, tmp_path, monkeypatch):
        _init_git_repo(tmp_path)
        hooks_dir = tmp_path / ".git" / "hooks"
        (hooks_dir / "pre-commit").write_text("#!/bin/sh\necho old hook\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["install-hooks", "--role", "implementer", "--repo-root", str(tmp_path)])
        assert result.exit_code == 0
        backup = hooks_dir / "pre-commit.pre-sdd"
        assert backup.exists()
        assert "old hook" in backup.read_text(encoding="utf-8")
        assert "backup" in result.output.lower()


# ---------------------------------------------------------------------------
# check-patterns
# ---------------------------------------------------------------------------


class TestCheckPatternsCLI:
    def test_no_violations_exit_0(self, tmp_path, monkeypatch):
        _write_agents(tmp_path)
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(
            app,
            ["check-patterns", "--role", "implementer", "--files", "tests/test_x.py", "--repo-root", str(tmp_path)],
        )
        assert result.exit_code == 0, result.output
        assert "OK" in result.output

    def test_violation_exits_1(self, tmp_path, monkeypatch):
        _write_agents(tmp_path)
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(
            app,
            [
                "check-patterns",
                "--role", "implementer",
                "--files", "sdd/artifacts/PHASE_4_SPEC.yaml",
                "--repo-root", str(tmp_path),
            ],
        )
        assert result.exit_code == 1
        # Violation details go to stderr — CliRunner mixes stdout+stderr by default
        assert "sdd/artifacts/PHASE_4_SPEC.yaml" in result.output

    def test_no_role_is_noop(self, tmp_path, monkeypatch):
        _write_agents(tmp_path)
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("SDD_ROLE", raising=False)
        result = runner.invoke(
            app,
            ["check-patterns", "--files", "sdd/artifacts/PHASE_4_SPEC.yaml", "--repo-root", str(tmp_path)],
        )
        assert result.exit_code == 0
        assert "no-op" in result.output.lower() or "advisory" in result.output.lower()

    def test_absent_agents_yaml_is_noop(self, tmp_path, monkeypatch):
        # No AGENTS.yaml written
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(
            app,
            ["check-patterns", "--role", "implementer", "--files", "src/foo.py", "--repo-root", str(tmp_path)],
        )
        assert result.exit_code == 0
        assert "not found" in result.output.lower() or "disabled" in result.output.lower()

    def test_no_files_specified_is_noop(self, tmp_path, monkeypatch):
        _write_agents(tmp_path)
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(
            app,
            ["check-patterns", "--role", "implementer", "--repo-root", str(tmp_path)],
        )
        assert result.exit_code == 0

    def test_multiple_violations_reported(self, tmp_path, monkeypatch):
        _write_agents(tmp_path)
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(
            app,
            [
                "check-patterns",
                "--role", "implementer",
                "--files", "sdd/artifacts/PHASE_4_SPEC.yaml",
                "--files", "sdd/artifacts/PHASE_3_AUDIT.yaml",
                "--repo-root", str(tmp_path),
            ],
        )
        assert result.exit_code == 1

    def test_auditor_cannot_stage_src(self, tmp_path, monkeypatch):
        _write_agents(tmp_path)
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(
            app,
            [
                "check-patterns",
                "--role", "auditor",
                "--files", "src/foo.py",
                "--repo-root", str(tmp_path),
            ],
        )
        assert result.exit_code == 1
        assert "src/foo.py" in result.output

    def test_strict_allowlist_rejects_neutral_file_with_clear_output(self, tmp_path, monkeypatch):
        agents = {
            "version": 1,
            "enforcement": {"mode": "strict_allowlist"},
            "roles": {
                "implementer": {
                    "allowed_file_patterns": ["src/**/*"],
                    "forbidden_file_patterns": ["sdd/artifacts/*SPEC*.yaml"],
                },
            },
        }
        _write_agents(tmp_path, agents)
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(
            app,
            [
                "check-patterns",
                "--role", "implementer",
                "--files", "README.md",
                "--repo-root", str(tmp_path),
            ],
        )

        assert result.exit_code == 1
        assert "not allowed for role 'implementer' under strict_allowlist mode" in result.output

    def test_invalid_enforcement_mode_exits_clearly(self, tmp_path, monkeypatch):
        agents = {
            "version": 1,
            "enforcement": {"mode": "invalid"},
            "roles": {
                "implementer": {
                    "allowed_file_patterns": ["src/**/*"],
                    "forbidden_file_patterns": [],
                },
            },
        }
        _write_agents(tmp_path, agents)
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(
            app,
            [
                "check-patterns",
                "--role", "implementer",
                "--files", "src/foo.py",
                "--repo-root", str(tmp_path),
            ],
        )

        assert result.exit_code == 1
        assert "Invalid enforcement.mode" in result.output


# ---------------------------------------------------------------------------
# Named acceptance-test functions (must match PHASE_4_CONTRACT.yaml names)
# ---------------------------------------------------------------------------


def test_check_patterns_cli_clean(tmp_path, monkeypatch):
    """sdd check-patterns --role implementer --files tests/test_x.py exits 0."""
    _write_agents(tmp_path)
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        app,
        ["check-patterns", "--role", "implementer", "--files", "tests/test_x.py", "--repo-root", str(tmp_path)],
    )
    assert result.exit_code == 0
    assert "OK" in result.output


def test_check_patterns_cli_violation(tmp_path, monkeypatch):
    """sdd check-patterns --role implementer --files sdd/artifacts/PHASE_4_SPEC.yaml exits 1."""
    _write_agents(tmp_path)
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        app,
        [
            "check-patterns",
            "--role", "implementer",
            "--files", "sdd/artifacts/PHASE_4_SPEC.yaml",
            "--repo-root", str(tmp_path),
        ],
    )
    assert result.exit_code == 1
    assert "sdd/artifacts/PHASE_4_SPEC.yaml" in result.output
