# SDD+ - Specification-Driven Development Extended

[![Python 3.13+](https://img.shields.io/badge/Python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-300%2B-brightgreen.svg)](https://github.com/oskcorps-sys/sdd-plus/actions)
[![Coverage](https://img.shields.io/badge/Coverage-91%25-brightgreen.svg)](#test-coverage)
[![Code Quality](https://img.shields.io/badge/Complexity-A%2FB-brightgreen.svg)](#code-quality)

LLM-agnostic spec-first governance framework for AI-assisted development, with independent audit gates, role-based file enforcement, telemetry, and a web dashboard.

**Core principle**: Specifications are binding. Code follows spec, not vice versa. Audit is independent and impartial.

**LLM-agnostic**: SDD+ doesn't care what AI (or human) executes each role. Use Claude, GPT-4, Gemini, Llama, Ollama, or manual review. Bring your own executor.

---

## Install

```bash
pip install sdd-plus
```

Requires Python 3.13+.

## Quick Start

```bash
# Initialize a new SDD+ project
sdd init

# Check current phase and state
sdd status

# Transition state (as auditor or implementer, with any executor)
sdd transition REFINED --role auditor --executor claude
sdd transition IMPLEMENTING --role implementer --executor gpt-4

# Run the 4-step audit loop (executor is whoever runs the audit)
sdd audit --role auditor --executor claude --auto-approve

# Advance to next phase (auditor only, after COMPLETED)
sdd new-phase --role auditor

# Install the pre-commit enforcement hook
sdd install-hooks --role implementer

# Check file patterns against role rules (dry-run)
sdd check-patterns --role implementer --files src/foo.py

# View telemetry
sdd metrics show --phase 4

# Launch the web dashboard
sdd dashboard --port 8888
```

---

## What It Does

SDD+ enforces a spec-first workflow with pluggable executors:

1. **State Machine** - 6-state lifecycle: DRAFT -> REFINED -> LOCKED -> IMPLEMENTING -> AUDITING -> COMPLETED
2. **Role Enforcement** - `AGENTS.yaml` declares which files each role (implementer/auditor) may touch. A git pre-commit hook enforces it.
3. **Audit Loop** - 4-step automated audit: pytest, coverage >= 85%, spec conformance, contract conformance.
4. **Telemetry** - Every transition and audit is logged to `.sdd-metrics/` as JSONL.
5. **Dashboard** - `sdd dashboard` serves a read-only web UI showing project state, audit history, and metrics.

---

## Architecture

```
project/
  AGENTS.yaml                  # Authority matrix (role -> file patterns)
  sdd/
    artifacts/                 # Specs, contracts, audits, state snapshot
      STATE_SNAPSHOT.yaml
      PHASE_N_SPEC.yaml
      PHASE_N_CONTRACT.yaml
      PHASE_N_AUDIT.yaml
    handoffs/                  # Phase transition summaries
    state_machine/             # 6-state machine + transitions
    schemas/                   # Pydantic v2 models
    validators/                # Contract + state validators
    enforcement.py             # File-pattern enforcement modes
    git_integration.py         # Git helpers (branch, commit, clean check)
    telemetry.py               # JSONL event emitter + query
    web/                       # FastAPI + Jinja2 dashboard
    cli/                       # Typer CLI commands
  tests/                       # 300+ tests, >= 85% coverage
  .sdd-metrics/                # Telemetry JSONL (gitignored)
```

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `sdd init` | Initialize SDD+ in a directory |
| `sdd status` | Show current phase and state |
| `sdd validate` | Validate contract and state artifacts |
| `sdd transition STATE --role ROLE [--executor E]` | Advance the state machine |
| `sdd new-phase --role auditor` | Start next phase after COMPLETED |
| `sdd audit --role auditor [--executor E]` | Run 4-step audit loop |
| `sdd install-hooks --role ROLE` | Install git pre-commit hook |
| `sdd check-patterns --role ROLE` | Dry-run file enforcement check |
| `sdd metrics show` | Display telemetry records |
| `sdd dashboard` | Launch web dashboard |
| `sdd projects list/add/remove` | Manage workspace projects |

### `sdd doctor`

Checks project readiness and reports each check as PASS, WARN, or FAIL.
Exits 1 when required readiness checks fail.

---

## Enforcement Modes

`AGENTS.yaml` can choose how role file patterns are enforced:

- `denylist`: MVP/default mode. Blocks files matching `forbidden_file_patterns` only. Neutral files remain allowed.
- `strict_allowlist`: Production mode. Allows only files matching the active role's `allowed_file_patterns`, while still blocking `forbidden_file_patterns`.

If `enforcement.mode` is missing, SDD+ uses `denylist` for backward compatibility.

```yaml
version: 1
enforcement:
  mode: strict_allowlist
roles:
  implementer:
    description: Writes implementation and tests
    allowed_file_patterns:
      - "src/**/*"
      - "tests/**/*"
      - "README.md"
    forbidden_file_patterns:
      - "sdd/artifacts/*SPEC*.yaml"
      - "sdd/artifacts/*AUDIT*.yaml"
```

---

## Phases Completed

| Phase | Title | Tests | Coverage |
|-------|-------|-------|----------|
| 0-2 | Schemas + State Machine + CLI | 300+ tests | 85%+ |
| 3 | Agent Harness (AGENTS.yaml, audit loop) | 300+ tests | 92% |
| 4 | Harness Closure (enforcement + git hooks) | 300+ tests | 92.1% |
| 5 | Telemetry & Metrics | 300+ tests | 91.7% |
| 6 | Web Dashboard | 300+ tests | 91.6% |
| 7 | PyPI Packaging | 300+ tests | 91%+ |

---

## Development

```bash
# Clone and install in dev mode
git clone https://github.com/oskcorps-sys/sdd-plus.git
cd sdd-plus
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=sdd --cov-report=html
```

---

## License

MIT - see [LICENSE](LICENSE).

---

**Built by Oscar Franco (ReguSense). LLM-agnostic by design.**
