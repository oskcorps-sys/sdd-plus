"""sdd doctor -- verify project readiness."""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import typer
import yaml

from sdd.schemas.agent import AgentsConfigSchema
from sdd.schemas.state import StateSnapshotSchema
from sdd.state_machine.machine import StateMachine


app = typer.Typer()


@dataclass
class DoctorCheck:
    status: str
    name: str
    detail: str
    required: bool = True


def _run_command(args: list[str], root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _pass(name: str, detail: str, required: bool = True) -> DoctorCheck:
    return DoctorCheck("PASS", name, detail, required)


def _warn(name: str, detail: str) -> DoctorCheck:
    return DoctorCheck("WARN", name, detail, required=False)


def _fail(name: str, detail: str, required: bool = True) -> DoctorCheck:
    return DoctorCheck("FAIL", name, detail, required)


def _load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _agents_check(root: Path) -> tuple[DoctorCheck, dict[str, Any] | None]:
    path = root / "AGENTS.yaml"
    if not path.exists():
        return _fail("AGENTS.yaml", "missing"), None
    try:
        data = _load_yaml(path)
        AgentsConfigSchema.model_validate(data)
    except Exception as exc:
        return _fail("AGENTS.yaml", f"invalid: {exc}"), None
    return _pass("AGENTS.yaml", "exists and validates"), data


def _state_snapshot_check(root: Path) -> DoctorCheck:
    path = root / "sdd" / "artifacts" / "STATE_SNAPSHOT.yaml"
    if not path.exists():
        return _fail("STATE_SNAPSHOT.yaml", "missing")
    try:
        data = _load_yaml(path)
        StateSnapshotSchema.model_validate(data)
    except Exception as exc:
        return _fail("STATE_SNAPSHOT.yaml", f"invalid: {exc}")
    return _pass("STATE_SNAPSHOT.yaml", "exists and validates")


def _current_state_check(root: Path) -> DoctorCheck:
    state_file = root / "sdd" / "artifacts" / "STATE_SNAPSHOT.yaml"
    agents_file = root / "AGENTS.yaml"
    try:
        state = StateMachine(
            state_file=str(state_file),
            agents_yaml_path=str(agents_file),
        ).get_state()
    except Exception as exc:
        return _fail("current state", f"could not load: {exc}")
    return _pass("current state", f"{state['current_state']} phase {state['current_phase']}")


def _git_repo_check(root: Path) -> DoctorCheck:
    result = _run_command(["git", "rev-parse", "--is-inside-work-tree"], root)
    if result.returncode != 0 or result.stdout.strip() != "true":
        detail = result.stderr.strip() or "not a git repository"
        return _fail("git repository", detail)
    return _pass("git repository", "detected")


def _git_status_check(root: Path) -> DoctorCheck:
    result = _run_command(["git", "status", "--short"], root)
    if result.returncode != 0:
        detail = result.stderr.strip() or "git status failed"
        return _fail("working tree status", detail)
    return _pass("working tree status", "readable")


def _pytest_check(root: Path) -> DoctorCheck:
    result = _run_command([sys.executable, "-m", "pytest", "--version"], root)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "pytest is not runnable"
        return _fail("pytest runnable", detail)
    return _pass("pytest runnable", result.stdout.strip())


def _hook_check(root: Path) -> DoctorCheck:
    hook = root / ".git" / "hooks" / "pre-commit"
    if not hook.exists():
        return _warn("pre-commit hook", "missing")
    return _pass("pre-commit hook", "installed", required=False)


def _github_enabled(agents_config: dict[str, Any] | None) -> bool:
    if not agents_config:
        return False
    github = agents_config.get("github_integration", {}) or {}
    return bool(github.get("enabled", False))


def _gh_check() -> DoctorCheck:
    if shutil.which("gh") is None:
        return _warn("gh CLI", "missing while github_integration.enabled=true")
    return _pass("gh CLI", "available", required=False)


def collect_checks(root: Path) -> list[DoctorCheck]:
    checks: list[DoctorCheck] = [
        _pass(
            "Python version",
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        )
        if sys.version_info >= (3, 13)
        else _fail("Python version", "requires Python >= 3.13"),
    ]

    agents_result, agents_config = _agents_check(root)
    checks.append(agents_result)
    checks.append(_state_snapshot_check(root))
    checks.append(_current_state_check(root))
    checks.append(_git_repo_check(root))
    checks.append(_git_status_check(root))
    checks.append(
        _pass("tests directory", "exists")
        if (root / "tests").is_dir()
        else _fail("tests directory", "missing")
    )
    checks.append(_pytest_check(root))
    checks.append(_hook_check(root))

    if _github_enabled(agents_config):
        checks.append(_gh_check())

    return checks


def _print_checks(checks: list[DoctorCheck]) -> None:
    for check in checks:
        typer.echo(f"{check.status:<4}  {check.name:<22} {check.detail}")


@app.command("doctor")
def doctor(
    repo_root: str = typer.Option(
        "",
        "--repo-root",
        help="Path to the project root (default: current directory).",
    ),
) -> None:
    """Verify that an SDD+ project is ready for local development."""
    root = Path(repo_root).resolve() if repo_root else Path.cwd()
    checks = collect_checks(root)
    _print_checks(checks)

    has_required_failure = any(check.required and check.status == "FAIL" for check in checks)
    raise typer.Exit(code=1 if has_required_failure else 0)
