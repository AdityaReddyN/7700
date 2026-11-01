"""Pydantic v2 schemas for every boundary in the pipeline.

Mirrors docs/ARCHITECTURE.md section 5 (and the ToolResult from section 3).
No label, scenario_id or split name may appear in any object the model sees:
Alert.summary and tool outputs are enforced elsewhere by the leakage test.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Label = Literal[
    "position_spoofing",
    "ghost_aircraft",
    "replay_duplicate",
    "sensor_fault",
    "benign_anomaly",
]

LABELS: tuple[str, ...] = (
    "position_spoofing",
    "ghost_aircraft",
    "replay_duplicate",
    "sensor_fault",
    "benign_anomaly",
)


class Alert(BaseModel):
    """Output of the rule-based flagger. Contains no label and no scenario id."""

    alert_id: str
    icao24: str
    t_start: int
    t_end: int
    score: float
    top_features: list[dict] = Field(default_factory=list)  # {"name": str, "z": float}
    summary: str  # human-readable; no label, no scenario id


class TriageItem(BaseModel):
    hypothesis: Label
    prior: float = Field(ge=0, le=1)
    reason: str


class Triage(BaseModel):
    hypotheses: list[TriageItem]


class Evidence(BaseModel):
    claim: str
    source: Literal["data_window", "calc", "retrieved_case", "reference"]
    ref_id: str
    stat: str | None = None
    value: float | None = None
    verified: bool | None = None  # set by the verifier only


class HypothesisReport(BaseModel):
    hypothesis: Label
    verdict: Literal["supported", "refuted", "inconclusive"]
    confidence: float = Field(ge=0, le=1)
    evidence: list[Evidence] = Field(default_factory=list)
    inference: str  # labelled as reasoning, not evidence
    would_disprove: list[str] = Field(default_factory=list)
    next_checks: list[str] = Field(default_factory=list)
    tool_calls_used: int = 0


class IncidentReport(BaseModel):
    alert_id: str
    verdict: Label | Literal["inconclusive"]
    confidence: float = Field(ge=0, le=1)
    ranked: list[HypothesisReport] = Field(default_factory=list)
    evidence_table: list[Evidence] = Field(default_factory=list)  # verified only
    excluded_evidence_count: int = 0
    inference: str = ""
    would_change_my_mind: list[str] = Field(default_factory=list)
    recommended_action: str = ""
    meta: dict = Field(default_factory=dict)  # config, models, per-stage seconds, tokens


class ToolResult(BaseModel):
    """Bounded, deterministic result of one read-only tool call (ARCHITECTURE 3)."""

    ref_id: str
    tool: str
    args: dict
    output: dict  # bounded; serialised form kept under ~400 tokens for the model
    truncated: bool = False
    ts: float
