"""M6: generate case cards from KB-split scenarios (SCENARIO_SPEC §8.1).

Cards are built only from scenarios whose split is ``kb`` and only from numbers
computed by the M5 tools (`kinematics`, `identity`, `window_summary`) on each
scenario's own track — never from memory, never from dev/test scenarios, and
never using a scenario id. The card's class label is metadata (cards are a
label -> signature reference, and `retrieve_cases` returns the label); the
signature text is the objective computed profile, shared with the recall query
via `describe_stats` so retrieval keys on the measured signal.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pandas as pd
import yaml

from common.schemas import LABELS
from tools.data_tools import identity, kinematics, window_summary

TrackLoader = Callable[[dict], pd.DataFrame]

# Label -> (title stem, differentiator templates). Metadata only; filled with
# the card's own computed numbers. No test/dev data is involved.
_TITLE_STEM = {
    "position_spoofing": "Position offset with reported-speed disagreement",
    "ghost_aircraft": "Self-consistent track with no identity changes",
    "replay_duplicate": "Repeated positions or same-address duplicates",
    "sensor_fault": "Dropouts, noise or frozen fields",
    "benign_anomaly": "Benign manoeuvre (holding or go-around)",
}
_DIFFERENTIATORS = {
    "position_spoofing": [
        "vs sensor_fault: residual grows smoothly with no dropouts or large time gaps",
        "vs replay_duplicate: no duplicate positions and no backward time jumps",
    ],
    "ghost_aircraft": [
        "vs position_spoofing: implied and reported speed agree (near-zero residual)",
        "vs sensor_fault: no dropouts, scatter or frozen fields; timing is regular",
    ],
    "replay_duplicate": [
        "vs position_spoofing: duplicate position pairs and/or a large position jump",
        "vs sensor_fault: duplication is clean, not noisy; identity is unchanged",
    ],
    "sensor_fault": [
        "vs position_spoofing: irregular timing, dropouts or scatter rather than a smooth residual",
        "vs replay_duplicate: no duplicate positions; gaps and noise dominate",
    ],
    "benign_anomaly": [
        "vs position_spoofing: reported speed tracks position; residual stays low",
        "vs sensor_fault: timing is regular with no dropouts; no frozen fields",
    ],
}


def compute_stats(df: pd.DataFrame) -> tuple[dict, dict, dict]:
    """Run the three M5 tools on a track window."""
    return kinematics(df), identity(df), window_summary(df)


def signal_tokens(kin: dict, ident: dict, win: dict) -> str:
    """Label-free discriminative tokens derived from the computed numbers.

    Each compound token fires only when its quality is present, so a track's
    token set is a fingerprint that BM25 can separate. The same function builds
    the card's indexed text and the recall query, so a scenario matches cards
    with the same measured qualities. No label, scenario id or split name.
    """
    toks: list[str] = []
    if kin["residual_kt_median"] >= 25 or kin["residual_kt_max"] >= 150:
        toks.append("residualhigh")
    if kin["residual_slope_kt_per_min"] >= 1.0:
        toks.append("residualrising")
    if kin["largest_jump_km"] >= 10:
        toks.append("positionjump")
    if ident["duplicate_position_pairs"] >= 1:
        toks.append("duplicatepositions")
    if win["max_gap_s"] >= 60:
        toks.append("coveragegap")
    if win["missing_fraction"] >= 0.1:
        toks.append("missingsamples")
    if ident["callsign_changes"] >= 1 or ident["squawk_changes"] >= 1:
        toks.append("identitychange")
    if kin["vertrate_vs_altitude_mismatch_ms_median"] >= 3.0:
        toks.append("vertratemismatch")
    if kin["residual_kt_median"] < 15 and kin["largest_jump_km"] < 5:
        toks.append("consistentkinematics")
    if win["max_gap_s"] <= 30 and win["missing_fraction"] < 0.05:
        toks.append("regularsampling")
    return " ".join(toks)


def describe_stats(kin: dict, ident: dict, win: dict) -> str:
    """Label-free, unit-consistent numeric summary of the computed values.

    Human-readable signature for the card and the report; the discriminative
    retrieval signal comes from `signal_tokens`. No label or scenario id.
    """
    span_min = 0.0
    if win.get("t_first") is not None and win.get("t_last") is not None:
        span_min = (win["t_last"] - win["t_first"]) / 60.0
    return (
        f"implied speed {kin['implied_speed_kt_median']:.0f} kt versus reported speed "
        f"{kin['reported_speed_kt_median']:.0f} kt; "
        f"speed residual {kin['residual_kt_median']:.0f} kt median up to "
        f"{kin['residual_kt_max']:.0f} kt; "
        f"residual slope {kin['residual_slope_kt_per_min']:.1f} kt per minute; "
        f"largest position jump {kin['largest_jump_km']:.1f} km; "
        f"maximum time gap {win['max_gap_s']:.0f} s; "
        f"missing fraction {win['missing_fraction']:.2f}; "
        f"vertical-rate versus altitude mismatch "
        f"{kin['vertrate_vs_altitude_mismatch_ms_median']:.1f} m/s; "
        f"callsign changes {ident['callsign_changes']}; "
        f"squawk changes {ident['squawk_changes']}; "
        f"duplicate position pairs {ident['duplicate_position_pairs']}; "
        f"track span {span_min:.0f} min over {win['n_points']} points"
    )


def _card_dict(card_id: str, label: str, kin: dict, ident: dict, win: dict) -> dict:
    span_min = 0.0
    if win.get("t_first") is not None and win.get("t_last") is not None:
        span_min = (win["t_last"] - win["t_first"]) / 60.0
    title = (f"{_TITLE_STEM[label]} "
             f"(median residual {kin['residual_kt_median']:.0f} kt, "
             f"largest jump {kin['largest_jump_km']:.1f} km)")
    signature = describe_stats(kin, ident, win)
    outcome = (f"Computed over {win['n_points']} points spanning {span_min:.0f} min; "
               f"largest step {kin['largest_jump_km']:.1f} km, "
               f"maximum gap {win['max_gap_s']:.0f} s, "
               f"duplicate position pairs {ident['duplicate_position_pairs']}.")
    return {
        "id": card_id,
        "label": label,
        "title": title,
        "signature": signature,
        "signals": signal_tokens(kin, ident, win),
        "differentiators": list(_DIFFERENTIATORS[label]),
        "outcome": outcome,
        "synthetic": True,
        "source_split": "kb",
    }


def _render(card: dict) -> str:
    front = yaml.safe_dump(card, sort_keys=False, allow_unicode=True).strip()
    body = (f"{card['title']}. Observed measurements: {card['signature']}. "
            f"Distinctions from other classes: {' '.join(card['differentiators'])} "
            f"{card['outcome']}")
    return f"---\n{front}\n---\n\n{body}\n"


def select_kb_scenarios(catalog: dict) -> list[dict]:
    """The KB-split scenarios, sorted deterministically, 2 per label."""
    kb = [s for s in catalog["scenarios"] if s["split"] == "kb"]
    return sorted(kb, key=lambda s: (LABELS.index(s["label"]), s["scenario_id"]))


def generate_cards(catalog: dict, track_loader: TrackLoader,
                   out_dir: Path) -> list[dict]:
    """Generate the case cards and write them to ``out_dir`` as C0NN.md.

    Returns the list of card dicts. Deterministic: order and ids depend only on
    (label, scenario_id). Rerunnable: files are overwritten.
    """
    kb = select_kb_scenarios(catalog)
    out_dir.mkdir(parents=True, exist_ok=True)
    cards: list[dict] = []
    for i, scn in enumerate(kb, start=1):
        card_id = f"C{i:03d}"
        df = track_loader(scn)
        kin, ident, win = compute_stats(df)
        card = _card_dict(card_id, scn["label"], kin, ident, win)
        (out_dir / f"{card_id}.md").write_text(_render(card), encoding="utf-8")
        cards.append(card)
    return cards
