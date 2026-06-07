"""sdd check-patterns -- report file-pattern violations for a role + fileset.

Used as a dry-run tool and called by the SDD pre-commit hook.
"""

from pathlib import Path
from typing import Optional

import typer

from sdd.enforcement import (
    check_files,
    get_allowed_patterns,
    get_enforcement_mode,
    get_forbidden_patterns,
    get_staged_files,
    load_agents_config,
    resolve_role,
)

app = typer.Typer()


def _resolve_target_files(
    staged: bool,
    files: Optional[list[str]],
    root: Optional[Path],
) -> Optional[list[str]]:
    """Pick the fileset to check. Returns None if no fileset is requested."""
    if staged:
        return get_staged_files(root)
    if files:
        return list(files)
    return None


def _print_violations(violations: list[dict], role: str, mode: str) -> None:
    """Emit human-readable violation report to stderr."""
    typer.echo(
        f"FAIL: {len(violations)} violation(s) for role '{role}':", err=True
    )
    for v in violations:
        typer.echo(f"  file   : {v['file']}", err=True)
        if v.get("reason") == "not_allowed":
            typer.echo(
                f"  reason : File is not allowed for role '{role}' under {mode} mode",
                err=True,
            )
        else:
            typer.echo(f"  rule   : {v['pattern']}", err=True)
            typer.echo("  reason : forbidden_match", err=True)
        typer.echo("", err=True)


@app.command("check-patterns")
def check_patterns(
    role: Optional[str] = typer.Option(
        None,
        "--role",
        "-r",
        help="Role to check against.  Defaults to resolved role (SDD_ROLE env / .sdd-role file).",
    ),
    files: Optional[list[str]] = typer.Option(
        None,
        "--files",
        "-f",
        help="Explicit list of files to check (repeatable).  Mutually exclusive with --staged.",
    ),
    staged: bool = typer.Option(
        False,
        "--staged",
        help="Check git-staged files (used by the pre-commit hook).",
    ),
    repo_root: str = typer.Option(
        "",
        "--repo-root",
        help="Path to the git repository root (default: current directory).",
    ),
) -> None:
    """Check file paths against the active role's forbidden_file_patterns.

    Exit 0 when there are no violations or when no role is active (advisory
    no-op).  Exit 1 when one or more violations are found.

    Examples:
      sdd check-patterns --role implementer --files sdd/artifacts/PHASE_4_SPEC.yaml
      sdd check-patterns --staged                 # called by the pre-commit hook
    """
    root = Path(repo_root) if repo_root else None

    active_role = role or resolve_role(root)
    if not active_role:
        typer.echo("INFO: No role set - enforcement is a no-op (advisory mode).")
        raise typer.Exit(code=0)

    target_files = _resolve_target_files(staged, files, root)
    if target_files is None:
        typer.echo("INFO: No files specified and --staged not set.  Nothing to check.")
        raise typer.Exit(code=0)
    if not target_files:
        typer.echo("OK: No files to check.")
        raise typer.Exit(code=0)

    config = load_agents_config(root)
    if config is None:
        typer.echo("INFO: AGENTS.yaml not found - enforcement disabled (no-op).")
        raise typer.Exit(code=0)

    try:
        mode = get_enforcement_mode(config)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)

    forbidden = get_forbidden_patterns(active_role, config)
    allowed = get_allowed_patterns(active_role, config)
    if mode == "denylist" and not forbidden:
        typer.echo(f"OK: No forbidden patterns defined for role '{active_role}'.")
        raise typer.Exit(code=0)

    violations = check_files(
        target_files,
        active_role,
        forbidden,
        allowed_patterns=allowed,
        mode=mode,
    )
    if not violations:
        typer.echo(f"OK: No violations for role '{active_role}'.")
        raise typer.Exit(code=0)

    _print_violations(violations, active_role, mode)
    raise typer.Exit(code=1)
