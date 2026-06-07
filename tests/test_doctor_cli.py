"""Tests for sdd doctor readiness checks."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import subprocess
import yaml
from typer.testing import CliRunner

from sdd.cli.main import app


runner = CliRunner()


def _write_agents(root: Path, github_enabled: bool = False) -> None:
    data = {
        "version": 1,
        "github_integration": {
            "enabled": github_enabled,
            "repo": "owner/repo",
        },
        "roles": {
            "implementer": {
                "description": "Writes code",
                "allowed_transitions": ["DRAFT->REFINED"],
                "forbidden_file_patterns": ["sdd/artifacts/*AUDIT*.yaml"],
            },
        },
    }
    (root / "AGENTS.yaml").write_text(
        yaml.dump(data, allow_unicode=True), encoding="utf-8"
    )


def _write_state(root: Path) -> None:
    state_path = root / "sdd" / "artifacts" / "STATE_SNAPSHOT.yaml"
    state_path.parent.mkdir(parents=True)
    data = {
        "phase": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "current_phase": 1,
        "current_state": "DRAFT",
        "completed_phases": [],
    }
    state_path.write_text(yaml.dump(data), encoding="utf-8")


def _init_git_repo(root: Path) -> None:
    subprocess.run(["git", "init"], cwd=root, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=root,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=root,
        capture_output=True,
        check=True,
    )


def _install_hook(root: Path) -> None:
    hooks_dir = root / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    (hooks_dir / "pre-commit").write_text(
        "#!/bin/sh\n# SDD+ pre-commit hook\n", encoding="utf-8"
    )


def _ready_project(root: Path, github_enabled: bool = False, hook: bool = True) -> None:
    _write_agents(root, github_enabled=github_enabled)
    _write_state(root)
    (root / "tests").mkdir()
    _init_git_repo(root)
    if hook:
        _install_hook(root)


def test_doctor_all_checks_passing(tmp_path, monkeypatch):
    _ready_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0, result.output
    assert "PASS" in result.output
    assert "Python version" in result.output
    assert "AGENTS.yaml" in result.output
    assert "STATE_SNAPSHOT.yaml" in result.output
    assert "pytest runnable" in result.output
    assert "pre-commit hook" in result.output


def test_doctor_missing_agents_yaml_fails(tmp_path, monkeypatch):
    _ready_project(tmp_path)
    (tmp_path / "AGENTS.yaml").unlink()
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 1
    assert "FAIL" in result.output
    assert "AGENTS.yaml" in result.output


def test_doctor_missing_state_snapshot_fails(tmp_path, monkeypatch):
    _ready_project(tmp_path)
    (tmp_path / "sdd" / "artifacts" / "STATE_SNAPSHOT.yaml").unlink()
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 1
    assert "FAIL" in result.output
    assert "STATE_SNAPSHOT.yaml" in result.output


def test_doctor_missing_hook_warns(tmp_path, monkeypatch):
    _ready_project(tmp_path, hook=False)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0, result.output
    assert "WARN" in result.output
    assert "pre-commit hook" in result.output


def test_doctor_github_enabled_but_gh_missing_warns(tmp_path, monkeypatch):
    _ready_project(tmp_path, github_enabled=True)
    monkeypatch.chdir(tmp_path)

    def fake_which(name: str) -> str | None:
        if name == "gh":
            return None
        return "tool"

    monkeypatch.setattr("sdd.cli.commands.doctor.shutil.which", fake_which)

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0, result.output
    assert "WARN" in result.output
    assert "gh CLI" in result.output
