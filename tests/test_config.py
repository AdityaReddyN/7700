"""Config YAML files load and expose the values the pipeline depends on."""

import pytest

from common.config import get_settings, load_yaml


def test_models_yaml_has_primary_backend():
    models = load_yaml("models")
    assert models["primary"]["backend"] == "ollama"
    assert "model" in models["primary"]


def test_agents_yaml_thresholds():
    agents = load_yaml("agents")
    assert agents["triage_min_prior"] == 0.15
    assert agents["triage_min_hypotheses"] == 3
    assert agents["triage_max_hypotheses"] == 3  # D-035: cut from 5 for the time budget
    assert agents["subagent_tool_call_limit"] == 3  # D-035: cut from 4
    assert agents["config_a_tool_call_limit"] == 8
    assert agents["max_concurrency"] == 1


def test_missing_config_raises():
    with pytest.raises(FileNotFoundError):
        load_yaml("does_not_exist")


def test_settings_default_spend_cap():
    settings = get_settings()
    # Default cap matches the $1 Modal balance unless overridden in .env.
    assert settings.max_spend_usd >= 0
