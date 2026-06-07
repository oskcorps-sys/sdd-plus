"""Agent role schema — machine-readable authority matrix."""

from typing import Dict, List, Literal, Tuple
from pydantic import BaseModel, Field, ConfigDict


ALL_STATES = {"DRAFT", "REFINED", "LOCKED", "IMPLEMENTING", "AUDITING", "COMPLETED"}


class AgentRoleSchema(BaseModel):
    """Single agent role with permissions and constraints."""

    description: str = Field(..., description="Role description")
    executor: str = Field(
        "any",
        description="Executor for this role (e.g. 'claude', 'gpt-4', 'llama', 'gemini', 'human', 'any')",
    )
    allowed_transitions: List[str] = Field(
        default_factory=list, description="Transition strings like 'DRAFT->REFINED'"
    )
    allowed_file_patterns: List[str] = Field(default_factory=list)
    forbidden_file_patterns: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)


class EnforcementConfigSchema(BaseModel):
    """File-pattern enforcement configuration."""

    mode: Literal["denylist", "strict_allowlist"] = Field("denylist")


class AgentsConfigSchema(BaseModel):
    """AGENTS.yaml schema — authority matrix for all roles."""

    model_config = ConfigDict(extra="allow")

    version: int = Field(1)
    enforcement: EnforcementConfigSchema = Field(default_factory=EnforcementConfigSchema)
    roles: Dict[str, AgentRoleSchema] = Field(...)


def parse_transition_string(s: str) -> List[Tuple[str, str]]:
    """Parse 'FROM->TO' into list of (from, to) tuples. Expands wildcards."""
    parts = s.split("->")
    if len(parts) != 2:
        return []

    from_state, to_state = parts[0].strip(), parts[1].strip()

    if from_state == "*":
        return [(st, to_state) for st in ALL_STATES if to_state in ALL_STATES]
    if to_state == "*":
        return [(from_state, st) for st in ALL_STATES if from_state in ALL_STATES]
    if from_state not in ALL_STATES or to_state not in ALL_STATES:
        return []

    return [(from_state, to_state)]


def build_transition_table(
    config: AgentsConfigSchema,
) -> Dict[Tuple[str, str], List[str]]:
    """Build {(from, to): [roles]} dict from AgentsConfigSchema."""
    table: Dict[Tuple[str, str], List[str]] = {}

    for role_name, role in config.roles.items():
        for transition_str in role.allowed_transitions:
            pairs = parse_transition_string(transition_str)
            for pair in pairs:
                if pair not in table:
                    table[pair] = []
                if role_name not in table[pair]:
                    table[pair].append(role_name)

    return table
