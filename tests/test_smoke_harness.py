"""Smoke-harness pieces that must hold without contacting Ollama (M1)."""

from agents.llm import _extract_json
from agents.prompts.dev_prompts import DEV_PROMPTS
from agents.tool_specs import TOOL_ARG_TYPES, TOOL_NAMES, TOOL_SPECS
from common.schemas import LABELS, HypothesisReport

_LEAK_TERMS = [*LABELS, "scenario", "spoof", "ghost", "replay", "sensor fault", "benign"]


def test_five_tool_specs_well_formed():
    assert len(TOOL_SPECS) == 5
    assert TOOL_NAMES == {
        "get_track_window", "compute_kinematics", "compare_to_baseline",
        "check_identity", "retrieve_cases",
    }
    for spec in TOOL_SPECS:
        fn = spec["function"]
        assert fn["description"]
        assert fn["parameters"]["type"] == "object"
        assert fn["parameters"]["required"]


def test_arg_types_cover_required_args():
    for name, types in TOOL_ARG_TYPES.items():
        assert name in TOOL_NAMES
        assert types  # at least one typed argument


def test_dev_prompts_count_and_fields():
    assert len(DEV_PROMPTS) == 20
    assert len({p["id"] for p in DEV_PROMPTS}) == 20
    for p in DEV_PROMPTS:
        assert p["t_start"] < p["t_end"]
        assert p["icao24"] and p["text"]


def test_dev_prompts_have_no_label_or_scenario_leakage():
    for p in DEV_PROMPTS:
        low = p["text"].lower()
        hits = [t for t in _LEAK_TERMS if t in low]
        assert not hits, f"{p['id']} leaks {hits}"


def test_extract_json_handles_wrapped_and_bare():
    assert _extract_json('{"a": 1}') == {"a": 1}
    assert _extract_json('here you go: {"a": 1} thanks') == {"a": 1}
    assert _extract_json("no json here") is None
    assert _extract_json("") is None


def test_minimal_hypothesis_report_validates():
    obj = {
        "hypothesis": "sensor_fault",
        "verdict": "inconclusive",
        "confidence": 0.3,
        "evidence": [],
        "inference": "not enough evidence",
        "would_disprove": [],
        "next_checks": ["compute_kinematics"],
        "tool_calls_used": 0,
    }
    assert HypothesisReport.model_validate(obj).hypothesis == "sensor_fault"
