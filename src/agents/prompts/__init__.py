"""Versioned prompt files and the label-free hypothesis cheat sheet (M7).

Prompts live as `<stage>.v<N>.md` next to this file (PROMPT_SPECS.md). They are
filled by exact-token replacement so the JSON braces in the templates stay
literal. No scenario id, split name or test label appears in any prompt; the
hypothesis names are the fixed public taxonomy, not scenario labels.
"""

from __future__ import annotations

from pathlib import Path

PROMPT_VERSION = "v1"
_DIR = Path(__file__).resolve().parent

# Starting heuristics (PROMPT_SPECS §1-2). Label-free: these describe the public
# hypothesis taxonomy, refined on dev only.
CHEATSHEET: dict[str, dict[str, str]] = {
    "position_spoofing": {
        "definition": "false positions or positions inconsistent with reported velocity",
        "supports": "implied speed from positions differs from reported speed; residual "
                    "grows steadily (drift) or jumps; reported velocity far from position change",
        "refutes": "implied and reported speed agree; motion smooth and consistent with "
                   "reported velocity",
    },
    "ghost_aircraft": {
        "definition": "a fabricated track with no genuine history",
        "supports": "no history before the window; unusually smooth kinematics; no nearby "
                    "traffic behaving like it",
        "refutes": "continuous, plausible history over earlier minutes",
    },
    "replay_duplicate": {
        "definition": "an earlier window re-broadcast, or one address at distant places at once",
        "supports": "sequence matches an earlier window; same address at distant positions "
                    "at once; timestamps go backwards",
        "refutes": "no matching earlier sequence; one consistent position",
    },
    "sensor_fault": {
        "definition": "noise, dropouts, repeated values or timestamp jitter from the receiver",
        "supports": "scatter, dropouts, repeated values, timestamp jitter; neighbours affected too",
        "refutes": "clean, smooth data; neighbours unaffected",
    },
    "benign_anomaly": {
        "definition": "a real, harmless manoeuvre such as a holding pattern or go-around",
        "supports": "pattern matches a known manoeuvre (holding, go-around); kinematics "
                    "consistent; neighbours normal",
        "refutes": "kinematic inconsistency or identity problems that no manoeuvre explains",
    },
}


# Label-free hint from detector feature -> likely hypothesis, for triage (D-037).
# Uses only public feature names and the public taxonomy; no scenario label/id.
FEATURE_MAP = (
    "Feature hints (what an elevated anomaly feature typically indicates):\n"
    "- identity_missing / no callsign or squawk -> ghost_aircraft (a fabricated track) "
    "or replay_duplicate; only rarely benign_anomaly.\n"
    "- duplicate position pairs / one address at two places at once -> replay_duplicate.\n"
    "- large position jump / backwards timestamps -> replay_duplicate or position_spoofing.\n"
    "- implied-vs-reported speed residual -> position_spoofing.\n"
    "- scatter / dropouts / repeated values / timestamp jitter -> sensor_fault.\n"
)


def triage_cheatsheet() -> str:
    """Render the label-free hypothesis definitions for the triage prompt (D-037)."""
    return "\n".join(
        f"- {h}: {c['definition']}. Supports: {c['supports']}."
        for h, c in CHEATSHEET.items()
    )


def load_prompt(name: str, version: str = PROMPT_VERSION) -> str:
    """Read `<name>.<version>.md` from this directory."""
    return (_DIR / f"{name}.{version}.md").read_text(encoding="utf-8")


def fill(template: str, **values: str) -> str:
    """Replace exact `{key}` tokens; JSON braces in the template stay literal."""
    out = template
    for key, value in values.items():
        out = out.replace("{" + key + "}", str(value))
    return out
