"""M7 adjudicator: write the IncidentReport from verified evidence only.

One model call (ARCHITECTURE §2.6). The model proposes a verdict, confidence and
narrative; in code we rebuild `ranked` from the verified reports, build the
`evidence_table` from verified items only, and enforce the confidence cap: no
confidence above `confidence_cap_single_evidence` (0.9) unless at least two
independent verified evidence items back the verdict (ARCHITECTURE §5). A failure
yields an inconclusive report listing the verified evidence, never a guess.
"""

from __future__ import annotations

import json

from pydantic import BaseModel, Field

from agents.llm import LLMClient
from agents.prompts import fill, load_prompt
from agents.triage import alert_json
from common.schemas import LABELS, Alert, Evidence, HypothesisReport, IncidentReport

_LABELS = set(LABELS)


class _AdjOut(BaseModel):
    verdict: str
    confidence: float = Field(ge=0, le=1)
    inference: str = ""
    discriminating_check: str = ""
    recommended_action: str = ""
    would_change_my_mind: list[str] = Field(default_factory=list)


def _reports_json(reports: list[HypothesisReport]) -> str:
    payload = [
        {
            "hypothesis": r.hypothesis, "verdict": r.verdict, "confidence": r.confidence,
            "evidence": [e.model_dump(include={"claim", "source", "ref_id", "stat", "value"})
                         for e in r.evidence],
            "inference": r.inference,
        }
        for r in reports
    ]
    return json.dumps(payload, indent=2, default=str)


def _rank(reports: list[HypothesisReport], verdict: str) -> list[HypothesisReport]:
    order = {"supported": 0, "inconclusive": 1, "refuted": 2}
    return sorted(reports, key=lambda r: (r.hypothesis != verdict, order.get(r.verdict, 1),
                                          -r.confidence, r.hypothesis))


def _evidence_table(reports: list[HypothesisReport]) -> list[Evidence]:
    table: list[Evidence] = []
    seen: set[tuple] = set()
    for r in reports:
        for e in r.evidence:
            if not e.verified:
                continue
            key = (e.ref_id, e.stat, e.claim)
            if key in seen:
                continue
            seen.add(key)
            table.append(e)
    return table


def _supporting_count(reports: list[HypothesisReport], verdict: str) -> int:
    refs: set[str] = set()
    for r in reports:
        if r.hypothesis == verdict:
            refs.update(e.ref_id for e in r.evidence if e.verified)
    return len(refs)


async def run_adjudicator(llm: LLMClient, alert: Alert,
                          verified_reports: list[HypothesisReport], *,
                          excluded_count: int = 0, cfg: dict | None = None,
                          max_tokens: int = 900, meta: dict | None = None) -> IncidentReport:
    cfg = cfg or {}
    cap = float(cfg.get("confidence_cap_single_evidence", 0.9))
    table = _evidence_table(verified_reports)
    messages = [
        {"role": "system", "content": load_prompt("preamble")},
        {"role": "user", "content": fill(load_prompt("adjudicator"),
                                          reports_json=_reports_json(verified_reports),
                                          alert_json=alert_json(alert))},
    ]
    res = await llm.complete("adjudication", messages, response_schema=_AdjOut,
                             max_tokens=max_tokens)
    if res.parsed is None:
        return IncidentReport(
            alert_id=alert.alert_id, verdict="inconclusive", confidence=0.0,
            ranked=_rank(verified_reports, ""), evidence_table=table,
            excluded_evidence_count=excluded_count,
            inference=f"reasoning: adjudicator produced no valid report ({res.error}).",
            would_change_my_mind=[], recommended_action="Re-run the investigation.",
            meta=meta or {})

    out: _AdjOut = res.parsed  # type: ignore[assignment]
    verdict = out.verdict if out.verdict in _LABELS or out.verdict == "inconclusive" \
        else "inconclusive"
    confidence = out.confidence
    if verdict != "inconclusive" and _supporting_count(verified_reports, verdict) < 2:
        confidence = min(confidence, cap)  # not enough independent verified support
    return IncidentReport(
        alert_id=alert.alert_id, verdict=verdict, confidence=round(confidence, 3),
        ranked=_rank(verified_reports, verdict), evidence_table=table,
        excluded_evidence_count=excluded_count, inference=out.inference,
        would_change_my_mind=list(out.would_change_my_mind),
        recommended_action=out.recommended_action,
        meta={**(meta or {}), "discriminating_check": out.discriminating_check})
