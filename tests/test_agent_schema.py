"""Tests for agent schema and AGENTS.yaml parsing."""

import pytest
import tempfile
import yaml
from pathlib import Path

from sdd.schemas.agent import (
    AgentRoleSchema,
    AgentsConfigSchema,
    EnforcementConfigSchema,
    parse_transition_string,
    build_transition_table,
    ALL_STATES,
)
from sdd.state_machine.transitions import (
    load_agents_config,
    get_transition_table,
    is_transition_allowed,
)


class TestAgentRoleSchema:

    def test_valid_role(self):
        role = AgentRoleSchema(
            description="Test role",
            allowed_transitions=["DRAFT->REFINED"],
            allowed_file_patterns=["src/**/*"],
            forbidden_file_patterns=["sdd/**/*"],
            constraints=["Cannot do X"],
        )
        assert role.description == "Test role"
        assert role.allowed_transitions == ["DRAFT->REFINED"]

    def test_role_defaults(self):
        role = AgentRoleSchema(description="Minimal role")
        assert role.allowed_transitions == []
        assert role.allowed_file_patterns == []
        assert role.forbidden_file_patterns == []
        assert role.constraints == []


class TestAgentsConfigSchema:

    def test_agents_yaml_loads(self):
        """acceptance: test_agents_yaml_loads"""
        data = {
            "version": 1,
            "roles": {
                "implementer": {
                    "description": "Writes code",
                    "allowed_transitions": ["DRAFT->REFINED", "LOCKED->IMPLEMENTING"],
                },
                "auditor": {
                    "description": "Reviews code",
                    "allowed_transitions": ["REFINED->LOCKED", "AUDITING->COMPLETED", "*->DRAFT"],
                },
            },
        }
        config = AgentsConfigSchema.model_validate(data)
        assert "implementer" in config.roles
        assert "auditor" in config.roles
        assert config.roles["implementer"].description == "Writes code"
        assert len(config.roles["auditor"].allowed_transitions) == 3

    def test_extra_fields_allowed(self):
        data = {
            "version": 1,
            "roles": {"implementer": {"description": "test"}},
            "custom_field": "allowed",
        }
        config = AgentsConfigSchema.model_validate(data)
        assert config.version == 1

    def test_enforcement_mode_defaults_to_denylist(self):
        config = AgentsConfigSchema.model_validate({
            "version": 1,
            "roles": {"implementer": {"description": "test"}},
        })
        assert config.enforcement.mode == "denylist"

    def test_enforcement_mode_accepts_strict_allowlist(self):
        config = AgentsConfigSchema.model_validate({
            "version": 1,
            "enforcement": {"mode": "strict_allowlist"},
            "roles": {"implementer": {"description": "test"}},
        })
        assert config.enforcement.mode == "strict_allowlist"

    def test_invalid_enforcement_mode_rejected(self):
        with pytest.raises(Exception):
            EnforcementConfigSchema.model_validate({"mode": "invalid"})


class TestParseTransitionString:

    def test_simple_transition(self):
        result = parse_transition_string("DRAFT->REFINED")
        assert result == [("DRAFT", "REFINED")]

    def test_wildcard_from(self):
        result = parse_transition_string("*->DRAFT")
        assert len(result) == len(ALL_STATES)
        for from_state, to_state in result:
            assert to_state == "DRAFT"
            assert from_state in ALL_STATES

    def test_wildcard_to(self):
        result = parse_transition_string("DRAFT->*")
        assert len(result) == len(ALL_STATES)

    def test_invalid_state(self):
        result = parse_transition_string("INVALID->DRAFT")
        assert result == []

    def test_malformed_string(self):
        assert parse_transition_string("NODASH") == []
        assert parse_transition_string("A->B->C") == []


class TestBuildTransitionTable:

    def test_builds_table_from_config(self):
        config = AgentsConfigSchema.model_validate({
            "version": 1,
            "roles": {
                "implementer": {
                    "description": "impl",
                    "allowed_transitions": ["DRAFT->REFINED", "LOCKED->IMPLEMENTING"],
                },
                "auditor": {
                    "description": "aud",
                    "allowed_transitions": ["DRAFT->REFINED", "REFINED->LOCKED"],
                },
            },
        })
        table = build_transition_table(config)
        assert "implementer" in table[("DRAFT", "REFINED")]
        assert "auditor" in table[("DRAFT", "REFINED")]
        assert table[("REFINED", "LOCKED")] == ["auditor"]
        assert table[("LOCKED", "IMPLEMENTING")] == ["implementer"]


class TestAgentsYamlIntegration:

    def test_agents_yaml_enforces_transitions(self):
        """acceptance: test_agents_yaml_enforces_transitions"""
        with tempfile.TemporaryDirectory() as tmpdir:
            agents_path = f"{tmpdir}/AGENTS.yaml"
            agents_data = {
                "version": 1,
                "roles": {
                    "implementer": {
                        "description": "impl",
                        "allowed_transitions": ["DRAFT->REFINED", "LOCKED->IMPLEMENTING"],
                    },
                    "auditor": {
                        "description": "aud",
                        "allowed_transitions": ["REFINED->LOCKED", "AUDITING->COMPLETED"],
                    },
                },
            }
            with open(agents_path, "w") as f:
                yaml.dump(agents_data, f)

            allowed, _ = is_transition_allowed(
                "REFINED", "LOCKED", "implementer", agents_yaml_path=agents_path
            )
            assert allowed is False

            allowed, _ = is_transition_allowed(
                "REFINED", "LOCKED", "auditor", agents_yaml_path=agents_path
            )
            assert allowed is True

    def test_agents_yaml_fallback(self):
        """acceptance: test_agents_yaml_fallback"""
        allowed, roles = is_transition_allowed(
            "DRAFT", "REFINED", "auditor",
            agents_yaml_path="/nonexistent/AGENTS.yaml",
        )
        assert allowed is True
        assert "auditor" in roles

    def test_load_agents_config_returns_none_for_missing_file(self):
        result = load_agents_config("/nonexistent/AGENTS.yaml")
        assert result is None

    def test_load_agents_config_returns_none_for_invalid_yaml(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bad_path = f"{tmpdir}/AGENTS.yaml"
            with open(bad_path, "w") as f:
                f.write("not: valid: agents: yaml: [")
            result = load_agents_config(bad_path)
            assert result is None
