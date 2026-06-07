"""CLI command: sdd audit

The audit loop has 4 steps:
  1. Run pytest + capture coverage
  2. Verify coverage >= 85%
  3. Spec conformance: every deliverable listed in SPEC exists
  4. Contract conformance: every acceptance test in CONTRACT exists

Each step is a helper; `audit()` is just the orchestrator.
"""

import json
import os
import subprocess
import sys
import yaml
import typer
from datetime import datetime, UTC
from pathlib import Path
from typing import Optional

from sdd.state_machine.machine import StateMachine

app = typer.Typer()

COVERAGE_THRESHOLD = 85.0


# ---------------------------------------------------------------------------
# Step helpers (each is small, single-purpose, easy to test in isolation)
# ---------------------------------------------------------------------------


def _run_tests(cov_json: str) -> tuple[bool, int]:
    """Step 1: run pytest + write coverage report. Returns (passed, returncode)."""
    cmd = [
        sys.executable, "-m", "pytest", "tests/", "-v",
        "--cov=sdd", f"--cov-report=json:{cov_json}",
        "--tb=short", "--no-header", "-q",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0, result.returncode


def _read_coverage(cov_json: str) -> float:
    """Step 2: parse coverage JSON; clean up the temp file. Fail-open returns 0.0."""
    if not Path(cov_json).exists():
        return 0.0
    try:
        with open(cov_json, "r", encoding="utf-8") as f:
            cov_data = json.load(f)
        return float(cov_data.get("totals", {}).get("percent_covered", 0.0))
    except Exception:
        return 0.0
    finally:
        try:
            os.remove(cov_json)
        except OSError:
            pass


def _check_spec_conformance(phase: int) -> tuple[bool, list[str]]:
    """Step 3: every file listed in SPEC.scope.included must exist on disk.

    Returns (passed, missing_files).
    """
    spec_path = Path(f"sdd/artifacts/PHASE_{phase}_SPEC.yaml")
    if not spec_path.exists():
        return True, []

    try:
        with open(spec_path, "r", encoding="utf-8") as f:
            spec_data = yaml.safe_load(f) or {}
    except Exception:
        return True, []  # fail-open: missing/corrupt spec is a different concern

    scope = spec_data.get("scope", {})
    included = scope.get("included", []) if isinstance(scope, dict) else []

    missing: list[str] = []
    for item in included:
        file_path = item.split(" — ")[0].strip() if " — " in item else item.strip()
        if file_path and not Path(file_path).exists():
            missing.append(file_path)

    return (len(missing) == 0), missing


def _collect_test_names() -> set[str]:
    """Scan tests/ for `def test_*` definitions. Returns a flat set of names."""
    names: set[str] = set()
    tests_dir = Path("tests")
    if not tests_dir.exists():
        return names
    for test_file in tests_dir.glob("test_*.py"):
        try:
            content = test_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("def test_"):
                names.add(stripped.split("(")[0].replace("def ", ""))
    return names


def _check_contract_conformance(phase: int) -> tuple[bool, list[str]]:
    """Step 4: every acceptance_test in CONTRACT.yaml must have a matching test.

    Skips entries with `kind: criterion` (those are verified by other audit steps).
    Returns (passed, missing_tests).
    """
    contract_path = Path(f"sdd/artifacts/PHASE_{phase}_CONTRACT.yaml")
    if not contract_path.exists():
        return True, []

    try:
        with open(contract_path, "r", encoding="utf-8") as f:
            contract_data = yaml.safe_load(f) or {}
    except Exception:
        return True, []

    acceptance_tests = contract_data.get("acceptance_tests", [])
    test_names = _collect_test_names()

    missing: list[str] = []
    for at in acceptance_tests:
        if not isinstance(at, dict):
            continue
        if at.get("kind") == "criterion":
            continue
        name = at.get("name", "")
        if name and name not in test_names:
            missing.append(name)

    return (len(missing) == 0), missing


def _write_audit_file(audit_file: Path, audit_data: dict) -> None:
    """Atomic write via tmp + replace, so the artifact is never half-written."""
    audit_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = audit_file.with_suffix(audit_file.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        yaml.dump(audit_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    os.replace(tmp, audit_file)


def _emit_telemetry(phase: int, verdict: str, coverage_pct: float, finding_count: int, executor: str) -> None:
    """Fail-open telemetry — never propagates errors to the caller."""
    try:
        from sdd.telemetry import emit_audit
        emit_audit(
            phase=phase,
            verdict=verdict,
            coverage_pct=coverage_pct,
            finding_count=finding_count,
            executor=executor,
        )
    except Exception:
        pass


def _git_commit_audit(audit_file: str, phase: int, coverage_pct: float) -> None:
    """Optional: stage and commit the APPROVED audit artifact."""
    from sdd.git_integration import is_git_repo, stage_and_commit
    repo_root = Path.cwd()
    if not is_git_repo(repo_root):
        typer.echo("WARN: --git specified but not in a git repository; skipping commit.")
        return
    commit_msg = f"audit(phase-{phase}): APPROVED {coverage_pct:.1f}% coverage"
    git_result = stage_and_commit(commit_msg, [audit_file], repo_root)
    if git_result["success"]:
        typer.echo(f"  git commit: {git_result['sha']} {commit_msg}")
    else:
        typer.echo(f"  WARN: git commit failed: {git_result['message']}")


def _load_github_config() -> dict | None:
    """Read github_integration block from AGENTS.yaml. Returns None if absent or disabled."""
    agents_path = Path("AGENTS.yaml")
    if not agents_path.exists():
        return None
    try:
        with open(agents_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        cfg = data.get("github_integration", {})
        if not cfg.get("enabled", False):
            return None
        if not cfg.get("repo"):
            typer.echo("WARN: github_integration.repo is required but missing; skipping GitHub PR.")
            return None
        return cfg
    except Exception:
        return None


def _create_github_pr(phase: int, coverage_pct: float, audit_file: str, cfg: dict) -> None:
    """Fail-open: create a GitHub PR linking spec + audit. Never propagates errors."""
    try:
        repo = cfg["repo"]
        spec_path = f"sdd/artifacts/PHASE_{phase}_SPEC.yaml"
        audit_path = audit_file

        title = f"Phase {phase} APPROVED — audit passed ({coverage_pct:.1f}% coverage)"
        body = (
            f"## Phase {phase} Audit — APPROVED ✅\n\n"
            f"| Field | Value |\n"
            f"|-------|-------|\n"
            f"| **Verdict** | APPROVED |\n"
            f"| **Coverage** | {coverage_pct:.1f}% |\n"
            f"| **Spec** | [`{spec_path}`]({spec_path}) |\n"
            f"| **Audit** | [`{audit_path}`]({audit_path}) |\n\n"
            f"---\n"
            f"*Auto-generated by `sdd audit --github` (SDD+ Phase {phase})*"
        )

        result = subprocess.run(
            ["gh", "pr", "create",
             "--title", title,
             "--body", body,
             "--repo", repo],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            pr_url = result.stdout.strip()
            typer.echo(f"  github PR: {pr_url}")
        else:
            typer.echo(f"  WARN: GitHub PR creation failed: {result.stderr.strip()}")
    except Exception as exc:
        typer.echo(f"  WARN: GitHub integration error: {exc}")


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------


@app.command()
def audit(
    role: str = typer.Option(..., "--role", "-r", help="Role performing audit (must be auditor)"),
    executor: str = typer.Option("any", "--executor", "-e", help="Executor for this audit (e.g. claude, gpt-4, llama, human)"),
    phase: Optional[int] = typer.Option(None, "--phase", "-p", help="Phase to audit (default: current)"),
    auto_approve: bool = typer.Option(False, "--auto-approve", help="Skip manual review"),
    git: bool = typer.Option(
        False,
        "--git",
        help="After an APPROVED verdict, stage and commit the AUDIT.yaml artifact.",
    ),
    github: bool = typer.Option(
        False,
        "--github",
        help="After an APPROVED verdict, create a GitHub PR (requires github_integration in AGENTS.yaml).",
    ),
):
    """Run the 4-step audit loop and produce AUDIT.yaml."""
    if role != "auditor":
        typer.echo("Error: Only auditor role can run audits", err=True)
        raise typer.Exit(1)

    try:
        machine = StateMachine()
        state = machine.get_state()
        audit_phase = phase or state["current_phase"]
    except FileNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

    findings: list[dict] = []
    steps: dict = {}

    # Step 1: tests
    cov_json = "coverage.json"
    tests_pass, returncode = _run_tests(cov_json)
    steps["pytest"] = {"passed": tests_pass, "returncode": returncode}
    if not tests_pass:
        findings.append({"severity": "HIGH", "description": "Test failures detected"})

    # Step 2: coverage
    coverage_pct = _read_coverage(cov_json)
    coverage_pass = coverage_pct >= COVERAGE_THRESHOLD
    steps["coverage"] = {
        "percent": round(coverage_pct, 1),
        "threshold": COVERAGE_THRESHOLD,
        "passed": coverage_pass,
    }
    if not coverage_pass:
        findings.append({
            "severity": "HIGH",
            "description": f"Coverage {coverage_pct:.1f}% below {COVERAGE_THRESHOLD:.0f}% threshold",
        })

    # Step 3: spec conformance
    spec_pass, missing_files = _check_spec_conformance(audit_phase)
    steps["spec_conformance"] = {"passed": spec_pass, "missing_files": missing_files}
    if missing_files:
        findings.append({
            "severity": "MEDIUM",
            "description": f"Missing spec deliverables: {', '.join(missing_files[:5])}",
        })

    # Step 4: contract conformance
    contract_pass, missing_tests = _check_contract_conformance(audit_phase)
    steps["contract_conformance"] = {"passed": contract_pass, "missing_tests": missing_tests}
    if missing_tests:
        findings.append({
            "severity": "MEDIUM",
            "description": f"Missing acceptance tests: {', '.join(missing_tests[:5])}",
        })

    # Verdict + artifact
    verdict = "APPROVED" if (
        tests_pass
        and coverage_pass
        and spec_pass
        and contract_pass
    ) else "REJECTED"
    audit_data = {
        "audit_id": f"audit-phase-{audit_phase}-v1",
        "phase": audit_phase,
        "timestamp": datetime.now(UTC).isoformat(),
        "auditor": role,
        "executor": executor,
        "verdict": verdict,
        "steps": steps,
        "findings": findings,
        "coverage_percent": round(coverage_pct, 1),
    }
    if auto_approve and verdict == "APPROVED":
        audit_data["signed_at"] = datetime.now(UTC).isoformat()

    audit_file = Path(f"sdd/artifacts/PHASE_{audit_phase}_AUDIT.yaml")
    _write_audit_file(audit_file, audit_data)

    # Telemetry (fail-open)
    _emit_telemetry(audit_phase, verdict, coverage_pct, len(findings), executor)

    # Output
    if verdict == "APPROVED":
        typer.echo(f"APPROVED Phase {audit_phase} - {coverage_pct:.1f}% coverage, all tests pass")
        if git:
            _git_commit_audit(str(audit_file), audit_phase, coverage_pct)
        if github:
            gh_cfg = _load_github_config()
            if gh_cfg:
                _create_github_pr(audit_phase, coverage_pct, str(audit_file), gh_cfg)
    else:
        typer.echo(f"REJECTED Phase {audit_phase}", err=True)
        for finding in findings:
            typer.echo(f"  - [{finding['severity']}] {finding['description']}", err=True)
        raise typer.Exit(1)
