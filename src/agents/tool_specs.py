"""OpenAI function-calling specs for the five read-only tools (ARCHITECTURE §3).

Used by the M1 smoke test to measure tool-call validity. The real tool
implementations and the registry arrive in M5; these are only the schemas the
model is shown, so they must match the documented argument names and types.
"""

from __future__ import annotations

from common.schemas import LABELS

_BASELINE_FEATURES = [
    "residual_kt_median",
    "largest_jump_km",
    "max_gap_s",
    "vertrate_vs_altitude_mismatch_ms_median",
]


def _fn(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        },
    }


TOOL_SPECS: list[dict] = [
    _fn(
        "get_track_window",
        "Downsampled summary of one aircraft's track in a time window.",
        {
            "icao24": {"type": "string", "description": "24-bit aircraft address (hex)"},
            "t_start": {"type": "integer", "description": "window start, Unix seconds"},
            "t_end": {"type": "integer", "description": "window end, Unix seconds"},
        },
        ["icao24", "t_start", "t_end"],
    ),
    _fn(
        "compute_kinematics",
        "Compare positions with reported speed/vertical-rate fields over a window.",
        {
            "icao24": {"type": "string"},
            "t_start": {"type": "integer"},
            "t_end": {"type": "integer"},
        },
        ["icao24", "t_start", "t_end"],
    ),
    _fn(
        "compare_to_baseline",
        "Compare a named feature with a baseline from real normal traffic in the same hour.",
        {
            "feature": {"type": "string", "enum": _BASELINE_FEATURES},
            "context": {"type": "string", "description": "e.g. 'all' or 'same_altitude_band'"},
        },
        ["feature", "context"],
    ),
    _fn(
        "check_identity",
        "Identity and consistency checks: callsign/squawk changes, duplicate positions.",
        {
            "icao24": {"type": "string"},
            "t_start": {"type": "integer"},
            "t_end": {"type": "integer"},
        },
        ["icao24", "t_start", "t_end"],
    ),
    _fn(
        "retrieve_cases",
        "Retrieve up to k case cards relevant to a query and hypothesis.",
        {
            "query": {"type": "string"},
            "hypothesis": {"type": "string", "enum": list(LABELS)},
            "k": {"type": "integer", "default": 4},
        },
        ["query", "hypothesis"],
    ),
]

TOOL_NAMES: set[str] = {spec["function"]["name"] for spec in TOOL_SPECS}

# Expected JSON types per argument, for the smoke-test validity check.
_JSON_TYPES = {"string": str, "integer": int, "number": (int, float), "object": dict}
TOOL_ARG_TYPES: dict[str, dict[str, type | tuple]] = {
    spec["function"]["name"]: {
        arg: _JSON_TYPES[prop["type"]]
        for arg, prop in spec["function"]["parameters"]["properties"].items()
    }
    for spec in TOOL_SPECS
}
