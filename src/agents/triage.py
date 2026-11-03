"""M7 triage: rank the five hypotheses by prior from the alert summary alone.

One model call, no tools (ARCHITECTURE §2.3). Keep hypotheses with prior at
least `triage_min_prior`; keep at least `triage_min_hypotheses` and at most
`triage_max_hypotheses`. If triage fails to parse, fall back to rule-based
priors from the alert's top features and record the fallback (ARCHITECTURE §10).
"""

from __future__ import annotations

import json

from agents.llm import LLMClient
from agents.prompts import FEATURE_MAP, fill, load_prompt, triage_cheatsheet
from common.schemas import Alert, Triage, TriageItem

# Which hypotheses a detector feature points at, for the no-model fallback only.
_FEATURE_HINTS: dict[str, tuple[str, ...]] = {
    "identity_missing": ("ghost_aircraft", "replay_duplicate"),
    "identity_change": ("replay_duplicate", "sensor_fault"),
    "vel_cv": ("position_spoofing", "sensor_fault"),
    "implied_speed": ("position_spoofing",),
    "residual": ("position_spoofing",),
    "speed": ("position_spoofing",),
    "jump": ("replay_duplicate", "position_spoofing"),
    "duplicate": ("replay_duplicate",),
    "gap": ("sensor_fault",),
    "missing": ("sensor_fault", "ghost_aircraft"),
    "vertrate": ("sensor_fault", "position_spoofing"),
}
_ALL = ("position_spoofing", "ghost_aircraft", "replay_duplicate",
        "sensor_fault", "benign_anomaly")


def alert_json(alert: Alert) -> str:
    """Only the Alert fields — no label, scenario id or split (leakage test enforced)."""
    return json.dumps(alert.model_dump(), indent=2)


def rule_priors(alert: Alert) -> list[TriageItem]:
    """Deterministic fallback priors from the alert's top features (no model)."""
    scores = dict.fromkeys(_ALL, 0.2)
    for feat in alert.top_features:
        name = str(feat.get("name", "")).lower()
        for key, hyps in _FEATURE_HINTS.items():
            if key in name:
                for h in hyps:
                    scores[h] = min(1.0, scores[h] + 0.3)
    return [TriageItem(hypothesis=h, prior=round(scores[h], 2),
                       reason="rule-based fallback from the alert's top features")
            for h in _ALL]


def select_hypotheses(items: list[TriageItem], cfg: dict) -> list[TriageItem]:
    """Apply the keep rule: prior >= min, keep [min_hyp, max_hyp]; top-N if too few pass."""
    lo = int(cfg.get("triage_min_hypotheses", 3))
    hi = int(cfg.get("triage_max_hypotheses", 5))
    mn = float(cfg.get("triage_min_prior", 0.15))
    best: dict[str, TriageItem] = {}
    for it in items:
        if it.hypothesis not in best or it.prior > best[it.hypothesis].prior:
            best[it.hypothesis] = it
    ordered = sorted(best.values(), key=lambda x: (-x.prior, x.hypothesis))
    passing = [x for x in ordered if x.prior >= mn]
    if len(passing) < lo:
        passing = ordered[:lo]
    return passing[:hi]


async def run_triage(llm: LLMClient, alert: Alert, cfg: dict,
                     *, max_tokens: int = 450) -> tuple[list[TriageItem], Triage | None, bool]:
    """Return (kept hypotheses, raw triage or None, used_fallback).

    Triage runs the v2 prompt (D-037): it carries the label-free hypothesis
    definitions and the feature->hypothesis hints, so the true class is not
    buried as a low prior and cut before any subagent investigates it. Other
    stages stay on v1.
    """
    user = fill(load_prompt("triage", "v2"), cheatsheet=triage_cheatsheet(),
                feature_map=FEATURE_MAP, alert_json=alert_json(alert))
    messages = [
        {"role": "system", "content": load_prompt("preamble")},
        {"role": "user", "content": user},
    ]
    res = await llm.complete("triage", messages, response_schema=Triage, max_tokens=max_tokens)
    if res.parsed is None:
        kept = select_hypotheses(rule_priors(alert), cfg)
        return kept, None, True
    triage: Triage = res.parsed  # type: ignore[assignment]
    kept = select_hypotheses(list(triage.hypotheses), cfg)
    if not kept:  # model returned nothing usable
        kept = select_hypotheses(rule_priors(alert), cfg)
        return kept, triage, True
    return kept, triage, False
