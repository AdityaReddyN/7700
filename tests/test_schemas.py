"""Boundary schemas construct, validate and round-trip through JSON."""

import pytest
from pydantic import ValidationError

from common.schemas import (
    LABELS,
    Alert,
    Evidence,
    HypothesisReport,
    IncidentReport,
    ToolResult,
    Triage,
    TriageItem,
)


def test_labels_are_the_five_agreed_classes():
    assert LABELS == (
        "position_spoofing",
        "ghost_aircraft",
        "replay_duplicate",
        "sensor_fault",
        "benign_anomaly",
    )


def test_alert_round_trips():
    alert = Alert(
        alert_id="alert_abc_100_200",
        icao24="abc123",
        t_start=100,
        t_end=200,
        score=3.2,
        top_features=[{"name": "residual_kt_median", "z": 4.1}],
        summary="Aircraft shows a large position jump over the window.",
    )
    assert Alert.model_validate_json(alert.model_dump_json()) == alert


def test_prior_bounds_enforced():
    with pytest.raises(ValidationError):
        TriageItem(hypothesis="sensor_fault", prior=1.5, reason="too high")


def test_triage_and_reports_build():
    triage = Triage(hypotheses=[TriageItem(hypothesis="ghost_aircraft", prior=0.4, reason="r")])
    assert triage.hypotheses[0].prior == 0.4

    report = HypothesisReport(
        hypothesis="ghost_aircraft",
        verdict="supported",
        confidence=0.7,
        evidence=[Evidence(claim="no baseline track", source="calc", ref_id="calc:x:kin:0001")],
        inference="reasoning here",
    )
    assert report.tool_calls_used == 0

    incident = IncidentReport(
        alert_id="alert_abc_100_200", verdict="ghost_aircraft", confidence=0.7
    )
    assert incident.excluded_evidence_count == 0


def test_toolresult_defaults():
    tr = ToolResult(ref_id="win:a:1-2", tool="get_track_window", args={}, output={}, ts=1.0)
    assert tr.truncated is False
