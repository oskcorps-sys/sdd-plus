# Changelog

All notable changes to SDD+ are documented here.

## [0.4.0] - 2026-06-08

Release hardening after PR #5, PR #6, and PR #7.

### Fixed
- Fixed audit verdict logic so APPROVED requires pytest, coverage, spec conformance, and contract conformance.
- Hardened CI security scanning by upgrading pip before running pip-audit, avoiding the runner pip 26.1.1 vulnerability PYSEC-2026-196.

### Added
- Added `strict_allowlist` enforcement mode while keeping `denylist` as the backward-compatible default.
- Added the `sdd doctor` readiness command.

### Stats
- 327 tests passing
- 92% coverage

---

## [0.3.0] - 2026-05-23

Phase 8 + 9: GitHub Integration and PyPI publish.

### Added
- **`sdd audit --github`** (Phase 8 S1): APPROVED audit auto-creates a GitHub PR with spec and audit artifact links
- **`sdd new-phase --github`** (Phase 8 S2): Phase advance auto-creates a GitHub milestone for the new phase and a draft release for the completed phase
- **`sdd transition --github`** (Phase 8 S3): State transitions apply a `sdd:{STATE}` label to open GitHub issues in the current phase milestone; labels are color-coded and auto-created if missing
- **PyPI Trusted Publishing** (Phase 9): `publish.yml` workflow — publishes to PyPI on `v*` tags via OIDC, no API tokens required
- **`github-automation` Sinapsis skill**: PowerShell helpers wrapping `gh` CLI for PR, issues, releases, and branch management

### Changed
- `pyproject.toml`: fixed repo URLs (`oskcorps-sys/sdd-plus`), moved `pytest`/`pytest-cov` to `[dev]`, bumped version to 0.3.0, added `build`, `bandit`, `radon`, `pip-audit` to `[dev]`
- CI: removed legacy `tests.yml` (superseded by `ci.yml` which runs on Python 3.13 + 3.14)

### Stats
- 307 tests · 91% coverage · 3 GitHub integration PRs merged

---

## [0.2.0] - 2026-05-21

LLM-agnostic refactor. SDD+ no longer assumes any specific AI provider.

### Changed
- **Executor field**: `AGENTS.yaml` roles now accept an optional `executor` field (default: `"any"`)
- **CLI `--executor` flag**: `sdd transition` and `sdd audit` accept `--executor` to record which LLM/human performed the action
- **Telemetry**: transition and audit events now include `executor` field
- **Schema**: `AgentRoleSchema` includes optional `executor` (default `"any"`)
- **Documentation**: README, description, and metadata rewritten to be fully LLM-agnostic
- **Version**: bumped to 0.2.0

### Removed
- All references to specific AI providers in documentation and metadata

---

## [0.1.0] - 2026-05-21

First public release. Seven phases of spec-driven development, fully audited.

### Added
- **State Machine** (Phase 2): 6-state lifecycle (DRAFT -> COMPLETED) with role-gated transitions
- **Schemas** (Phase 1): Pydantic v2 models for contracts, specs, audits, state snapshots
- **CLI** (Phase 2): `sdd` command with status, validate, transition, init, audit, new-phase
- **Agent Harness** (Phase 3): AGENTS.yaml authority matrix, AgentRoleSchema, automated audit loop
- **File-Pattern Enforcement** (Phase 4): git pre-commit hook enforcing AGENTS.yaml denylist rules
- **Git Integration** (Phase 4): `sdd install-hooks`, `sdd check-patterns`, `--git` flags on new-phase/audit
- **Telemetry** (Phase 5): JSONL event emission on transitions and audits, `sdd metrics show`
- **Web Dashboard** (Phase 6): FastAPI + Jinja2 + HTMX read-only dashboard at `sdd dashboard`
- **PyPI Packaging** (Phase 7): `pip install sdd-plus`

### Stats
- 244+ tests
- 91%+ coverage across all modules
- 7 phases, each independently audited with zero findings
- Zero external dependencies beyond Python stdlib + pydantic + typer + pyyaml + fastapi
