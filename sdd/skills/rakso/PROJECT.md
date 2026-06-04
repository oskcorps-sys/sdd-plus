# Project: RAKSO Fortress OS — MVP Core
# Scope: Phase 1

## Architecture
- **Adapter Layer**: Interfaces for LLM models (Anthropic, OpenAI, etc.) and Channel actions (Telegram, Instagram).
- **Identity Layer**: Loads brand voice and limits from Obsidian markdown frontmatter.
- **Agent Layer**: `MarketingAgent` orchestrates fan-out to 4 sub-agents (`RAKSOCreativo`, `NeurofunnelSub`, `ModuleC`, `TheBridge`).
- **Bridge Gate**: Convergence node that validates and scores outputs before routing.
- **Routing Layer**: `NeuroRouter` & `Trafficker` route to channels.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Adapters & Identity | LLM/Channel interfaces, Obsidian parser | none | PLANNED |
| 2 | Sub-Agents & The Bridge | RAKSOCreativo, NeurofunnelSub, ModuleC, TheBridge | M1 | PLANNED |
| 3 | Orchestration | MarketingAgent parallel fan-out, modes | M2 | PLANNED |

## Interface Contracts
### `adapters` ↔ `agents`
- `LLMAdapter` interface: `async def generate(prompt, **kwargs) -> str`
- `ChannelAdapter` interface: `async def publish(payload) -> bool`

### `identity` ↔ `agents`
- `load_identity_pack(vault_path) -> dict` returning voice, visual, product, hard_limits.

### `MarketingAgent` ↔ `SubAgents`
- Each subagent has `async def execute(context) -> dict`
- Parallel execution using `asyncio.gather`.

## Code Layout
```
sdd/skills/rakso/
├── src/
│   └── rakso/
│       ├── adapters/
│       ├── identity/
│       ├── agents/
│       └── orchestration/
├── tests/
│   ├── adapters/
│   ├── identity/
│   ├── agents/
│   └── orchestration/
└── SKILL.md
```
