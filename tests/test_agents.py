"""M7 agent tests: hermetic, no Ollama. A scripted FakeLLM drives every stage.

Covers the verifier's required cases, the triage keep-rule and fallback, the
subagent tool-call budget and inconclusive-on-failure path, the adjudicator
confidence cap, and configs A and D end-to-end (valid IncidentReport + trace
with per-stage timing). A leakage check confirms no scenario id / split reaches
any prompt.
"""

from __future__ import annotations

import asyncio
import json
import re

import numpy as np
import pandas as pd

from agents import orchestrator as orch
from agents.adjudicator import _AdjOut, run_adjudicator
from agents.llm import LLMResult
from agents.subagent import SingleAgentReport, run_subagent
from agents.triage import rule_priors, run_triage, select_hypotheses
from agents.verifier import verified_only, verify_report
from common.schemas import Alert, Evidence, HypothesisReport, Triage, TriageItem
from tools.data_tools import TrackProvider
from tools.registry import ToolRegistry
from tools.toollog import ToolLog

_T = 1_575_849_600
_COLS = ["time", "icao24", "lat", "lon", "velocity", "heading", "vertrate",
         "callsign", "squawk", "baroaltitude", "geoaltitude"]
_MS_PER_DEG_LAT = 111_320.0

_AGENTS_CFG = {
    "triage_min_prior": 0.15, "triage_min_hypotheses": 3, "triage_max_hypotheses": 5,
    "subagent_tool_call_limit": 4, "config_a_tool_call_limit": 8, "max_concurrency": 1,
    "call_timeout_s": 5, "confidence_cap_single_evidence": 0.9, "tool_output_max_chars": 1600,
    "max_tokens": {"triage": 50, "subagent": 50, "adjudicator": 50},
}
_ABLATIONS = {"configs": {
    "A": {"triage": False, "subagents": 1, "verifier": True, "adjudicator": False,
          "tool_call_limit": 8},
    "D": {"triage": True, "subagents": "3-5", "verifier": True, "adjudicator": True,
          "tool_call_limit": 4},
}}


def _track(icao="aa0001", n=40, v_ms=200.0, reported=120.0):
    dlat = (v_ms * 10.0) / _MS_PER_DEG_LAT
    return pd.DataFrame({
        "time": _T + np.arange(n) * 10, "icao24": icao,
        "lat": 50.0 + np.arange(n) * dlat, "lon": 8.0, "velocity": reported,
        "heading": 0.0, "vertrate": 0.0, "callsign": "DLH1", "squawk": "1000",
        "baroaltitude": 10000.0, "geoaltitude": 10000.0,
    })[_COLS]


def _alert(icao="aa0001"):
    return Alert(alert_id=f"alert_{icao}_{_T}_{_T + 390}", icao24=icao, t_start=_T,
                 t_end=_T + 390, score=0.07,
                 top_features=[{"name": "implied_speed", "z": 6.0},
                               {"name": "identity_missing", "z": 50.0}],
                 summary="Implied speed far above reported; no callsign.")


def _provider(icao="aa0001"):
    return TrackProvider(con=None, scenario_tracks=_track(icao), exclude_icao24=set())


def _full_triage():
    labels = ["position_spoofing", "ghost_aircraft", "replay_duplicate",
              "sensor_fault", "benign_anomaly"]
    priors = [0.9, 0.3, 0.2, 0.25, 0.1]
    return Triage(hypotheses=[TriageItem(hypothesis=h, prior=p, reason="r")
                              for h, p in zip(labels, priors, strict=True)])


class FakeLLM:
    """Scripts complete() per stage. Tool turns emit one call until a tool result exists."""

    def __init__(self, alert, *, triage=None, subagent_report=None, single_report=None,
                 adj_out=None, loop_forever_tools=False, bad_args=False):
        self.alert = alert
        self.triage = triage
        self.subagent_report = subagent_report
        self.single_report = single_report
        self.adj_out = adj_out
        self.loop_forever_tools = loop_forever_tools
        self.bad_args = bad_args
        self.tool_turns = 0
        self.calls: list[dict] = []
        self.seen: list[tuple[str, list]] = []

    def model_for(self, stage):
        return "fake-model"

    async def complete(self, stage, messages, *, tools=None, response_schema=None,
                       max_tokens=800, timeout_s=None):
        self.seen.append((stage, messages))
        self.calls.append({"stage": stage, "prompt_tokens": 1, "completion_tokens": 1,
                           "latency_s": 0.0, "tool_call_valid": True, "parse_ok": True})
        if tools:
            has_result = any(m.get("role") == "tool" for m in messages)
            if self.loop_forever_tools or not has_result:
                self.tool_turns += 1
                args = {} if self.bad_args else {
                    "icao24": self.alert.icao24, "t_start": self.alert.t_start,
                    "t_end": self.alert.t_end}
                return LLMResult(text="", mode="native_tools", tool_calls=[
                    {"id": f"c{len(self.seen)}", "name": "compute_kinematics",
                     "arguments": json.dumps(args)}])
            return LLMResult(text="", mode="native_tools", tool_calls=[])
        if stage == "triage":
            return LLMResult(text="", parsed=self.triage, mode="json_schema",
                             parse_ok=self.triage is not None)
        if stage == "adjudication":
            return LLMResult(text="", parsed=self.adj_out, mode="json_schema",
                             parse_ok=self.adj_out is not None)
        rep = self.single_report if stage == "single_agent" else self.subagent_report
        return LLMResult(text="", parsed=rep, mode="json_schema", parse_ok=rep is not None)


# --- verifier --------------------------------------------------------------

def _log_with(output, ref_id="calc:a:kin:0001"):
    log = ToolLog()
    log.record("compute_kinematics", {}, output, ref_id)
    return log, ref_id


def _ev(ref_id, stat=None, value=None, source="calc"):
    return Evidence(claim="c", source=source, ref_id=ref_id, stat=stat, value=value)


def _verify_one(ev, log):
    report = HypothesisReport(hypothesis="position_spoofing", verdict="supported",
                              confidence=0.5, evidence=[ev], inference="r")
    _, stats = verify_report(report, log)
    return stats.items[0]


def test_verifier_missing_ref():
    log, _ = _log_with({"residual_kt_median": 50.0})
    assert _verify_one(_ev("calc:a:kin:zzzz", "residual_kt_median", 50.0), log).status \
        == "missing_ref"


def test_verifier_unknown_stat():
    log, ref = _log_with({"residual_kt_median": 50.0})
    assert _verify_one(_ev(ref, "nope", 1.0), log).status == "unknown_stat"


def test_verifier_value_at_tolerance_passes():
    log, ref = _log_with({"x": 0.0})  # tol = max(0.5*rel, 0.5) = 0.5; diff exactly 0.5
    assert _verify_one(_ev(ref, "x", 0.5), log).status == "verified"


def test_verifier_value_just_outside_fails():
    log, ref = _log_with({"x": 0.0})
    assert _verify_one(_ev(ref, "x", 0.6), log).status == "value_mismatch"


def test_verifier_value_zero():
    log, ref = _log_with({"x": 0.0})
    assert _verify_one(_ev(ref, "x", 0.0), log).status == "verified"


def test_verifier_negative_values():
    log, ref = _log_with({"x": -10.0})
    assert _verify_one(_ev(ref, "x", -10.2), log).status == "verified"


def test_verifier_null_value_with_stat_is_partial():
    log, ref = _log_with({"x": 5.0})
    assert _verify_one(_ev(ref, "x", None), log).status == "verified_partial"


def test_verifier_nested_stat_found():
    log, ref = _log_with({"cases": [{"card_id": "C1", "value": 12.0}]})
    assert _verify_one(_ev(ref, "value", 12.0), log).status == "verified"


# --- triage ----------------------------------------------------------------

def test_select_filters_below_floor_and_orders_by_prior():
    kept = select_hypotheses(_full_triage().hypotheses, _AGENTS_CFG)
    # benign_anomaly (0.10) is below the 0.15 floor; the other four pass.
    assert len(kept) == 4 and kept[0].hypothesis == "position_spoofing"
    assert "benign_anomaly" not in {k.hypothesis for k in kept}


def test_select_caps_at_max_five():
    items = [TriageItem(hypothesis=h, prior=0.9, reason="r") for h in
             ("position_spoofing", "ghost_aircraft", "replay_duplicate",
              "sensor_fault", "benign_anomaly")]
    assert len(select_hypotheses(items, _AGENTS_CFG)) == 5


def test_select_floors_to_min_three_when_too_few_pass():
    items = [TriageItem(hypothesis="position_spoofing", prior=0.9, reason="r"),
             TriageItem(hypothesis="ghost_aircraft", prior=0.05, reason="r"),
             TriageItem(hypothesis="sensor_fault", prior=0.04, reason="r"),
             TriageItem(hypothesis="replay_duplicate", prior=0.03, reason="r"),
             TriageItem(hypothesis="benign_anomaly", prior=0.02, reason="r")]
    kept = select_hypotheses(items, _AGENTS_CFG)
    assert len(kept) == 3 and kept[0].hypothesis == "position_spoofing"


def test_select_dedups_keeping_max_prior():
    items = [TriageItem(hypothesis="sensor_fault", prior=0.2, reason="r"),
             TriageItem(hypothesis="sensor_fault", prior=0.8, reason="r"),
             TriageItem(hypothesis="position_spoofing", prior=0.5, reason="r"),
             TriageItem(hypothesis="ghost_aircraft", prior=0.5, reason="r")]
    kept = select_hypotheses(items, _AGENTS_CFG)
    sensor = [k for k in kept if k.hypothesis == "sensor_fault"]
    assert len(sensor) == 1 and sensor[0].prior == 0.8


def test_triage_fallback_on_parse_failure():
    alert = _alert()
    llm = FakeLLM(alert, triage=None)  # triage parse returns None -> fallback
    kept, raw, fallback = asyncio.run(run_triage(llm, alert, _AGENTS_CFG))
    assert fallback is True and raw is None and 3 <= len(kept) <= 5


def test_rule_priors_biases_matching_features():
    pri = {it.hypothesis: it.prior for it in rule_priors(_alert())}
    assert pri["position_spoofing"] > 0.2 and pri["ghost_aircraft"] > 0.2


# --- subagent --------------------------------------------------------------

def _registry(alert):
    return ToolRegistry(alert, _provider(alert.icao24), retriever=None, log=ToolLog())


def test_subagent_respects_tool_budget():
    alert = _alert()
    rep = HypothesisReport(hypothesis="position_spoofing", verdict="inconclusive",
                           confidence=0.2, evidence=[], inference="r")
    llm = FakeLLM(alert, subagent_report=rep, loop_forever_tools=True)
    item = TriageItem(hypothesis="position_spoofing", prior=0.9, reason="r")
    out = asyncio.run(run_subagent(llm, _registry(alert), alert, item, tool_call_limit=2))
    assert out.tool_calls_used == 2 and out.hypothesis == "position_spoofing"


def test_subagent_terminates_when_every_tool_call_errors():
    # 8B sometimes emits valid-looking calls with missing required args; registry.call
    # raises, the call never "succeeds", so the budget must count attempts, not
    # successes, or the loop never ends (the real config-D runaway).
    alert = _alert()
    rep = HypothesisReport(hypothesis="position_spoofing", verdict="inconclusive",
                           confidence=0.1, evidence=[], inference="r")
    llm = FakeLLM(alert, subagent_report=rep, loop_forever_tools=True, bad_args=True)
    item = TriageItem(hypothesis="position_spoofing", prior=0.9, reason="r")
    out = asyncio.run(run_subagent(llm, _registry(alert), alert, item, tool_call_limit=3))
    assert out.tool_calls_used == 0          # none succeeded
    assert llm.tool_turns <= 3               # loop stopped at the attempt cap


def test_subagent_inconclusive_on_parse_failure():
    alert = _alert()
    llm = FakeLLM(alert, subagent_report=None)  # final report never parses
    item = TriageItem(hypothesis="sensor_fault", prior=0.5, reason="r")
    out = asyncio.run(run_subagent(llm, _registry(alert), alert, item, tool_call_limit=4))
    assert out.verdict == "inconclusive" and out.hypothesis == "sensor_fault"


# --- adjudicator confidence cap -------------------------------------------

def test_adjudicator_caps_confidence_without_two_supports():
    alert = _alert()
    reg = _registry(alert)
    tr = reg.call("compute_kinematics", {"icao24": alert.icao24,
                                         "t_start": alert.t_start, "t_end": alert.t_end})
    v = tr.output["residual_kt_median"]
    report = HypothesisReport(hypothesis="position_spoofing", verdict="supported",
                              confidence=0.98,
                              evidence=[_ev(tr.ref_id, "residual_kt_median", v)],
                              inference="r")
    vr, _ = verify_report(report, reg.log)
    llm = FakeLLM(alert, adj_out=_AdjOut(verdict="position_spoofing", confidence=0.98))
    inc = asyncio.run(run_adjudicator(llm, alert, [verified_only(vr)], cfg=_AGENTS_CFG))
    assert inc.verdict == "position_spoofing" and inc.confidence == 0.9


def test_adjudicator_allows_high_confidence_with_two_supports():
    alert = _alert()
    reg = _registry(alert)
    k = reg.call("compute_kinematics", {"icao24": alert.icao24,
                                        "t_start": alert.t_start, "t_end": alert.t_end})
    i = reg.call("check_identity", {"icao24": alert.icao24,
                                    "t_start": alert.t_start, "t_end": alert.t_end})
    report = HypothesisReport(
        hypothesis="position_spoofing", verdict="supported", confidence=0.95,
        evidence=[_ev(k.ref_id, "residual_kt_median", k.output["residual_kt_median"]),
                  _ev(i.ref_id, "callsign_changes", i.output["callsign_changes"])],
        inference="r")
    vr, stats = verify_report(report, reg.log)
    assert stats.n_verified == 2
    llm = FakeLLM(alert, adj_out=_AdjOut(verdict="position_spoofing", confidence=0.95))
    inc = asyncio.run(run_adjudicator(llm, alert, [verified_only(vr)], cfg=_AGENTS_CFG))
    assert inc.confidence == 0.95 and len(inc.evidence_table) == 2


# --- adjudicator verdict constraint (D-038) --------------------------------

def test_adjudicator_rejects_uninvestigated_verdict():
    """The LLM names a hypothesis no subagent investigated -> inconclusive."""
    alert = _alert()
    reports = [HypothesisReport(hypothesis="ghost_aircraft", verdict="inconclusive",
                                confidence=0.5, evidence=[], inference="r"),
               HypothesisReport(hypothesis="benign_anomaly", verdict="refuted",
                                confidence=0.8, evidence=[], inference="r")]
    llm = FakeLLM(alert, adj_out=_AdjOut(verdict="position_spoofing", confidence=0.9))
    inc = asyncio.run(run_adjudicator(llm, alert, reports, cfg=_AGENTS_CFG))
    assert inc.verdict == "inconclusive" and inc.confidence == 0.0
    assert inc.meta["verdict_overridden"] and inc.meta["proposed_verdict"] == "position_spoofing"


def test_adjudicator_overrides_to_supported_hypothesis():
    """The LLM strays to an uninvestigated label but one hypothesis is supported."""
    alert = _alert()
    reports = [HypothesisReport(hypothesis="ghost_aircraft", verdict="supported",
                                confidence=0.6, evidence=[], inference="r"),
               HypothesisReport(hypothesis="benign_anomaly", verdict="refuted",
                                confidence=0.8, evidence=[], inference="r")]
    llm = FakeLLM(alert, adj_out=_AdjOut(verdict="position_spoofing", confidence=0.9))
    inc = asyncio.run(run_adjudicator(llm, alert, reports, cfg=_AGENTS_CFG))
    assert inc.verdict == "ghost_aircraft" and inc.confidence <= 0.6
    assert inc.meta["verdict_overridden"]


def test_adjudicator_keeps_explicit_inconclusive():
    """An explicit inconclusive is respected even when a hypothesis is supported."""
    alert = _alert()
    reports = [HypothesisReport(hypothesis="ghost_aircraft", verdict="supported",
                                confidence=0.6, evidence=[], inference="r")]
    llm = FakeLLM(alert, adj_out=_AdjOut(verdict="inconclusive", confidence=0.4))
    inc = asyncio.run(run_adjudicator(llm, alert, reports, cfg=_AGENTS_CFG))
    assert inc.verdict == "inconclusive" and not inc.meta["verdict_overridden"]


# --- orchestrator end-to-end ----------------------------------------------

def _d_llm(alert):
    rep = HypothesisReport(hypothesis="position_spoofing", verdict="supported",
                           confidence=0.8, evidence=[], inference="reasoning")
    return FakeLLM(alert, triage=_full_triage(), subagent_report=rep,
                   adj_out=_AdjOut(verdict="position_spoofing", confidence=0.95,
                                   recommended_action="investigate"))


def test_config_d_end_to_end(tmp_path):
    alert = _alert()
    inc, trace = orch.investigate_sync(
        alert, "D", provider=_provider(), retriever=None, run_dir=tmp_path,
        agents_cfg=_AGENTS_CFG, ablations_cfg=_ABLATIONS, models_cfg={"primary": {}},
        llm=_d_llm(alert))
    assert inc.alert_id == alert.alert_id
    assert inc.verdict == "position_spoofing" and inc.confidence == 0.9  # no verified support
    assert set(trace) >= {"triage", "subagents", "verification", "report",
                          "timing_s", "toollog", "llm_calls"}
    assert "triage" in trace["timing_s"] and "adjudication" in trace["timing_s"]
    assert any(k.startswith("subagent:") for k in trace["timing_s"])
    assert (tmp_path / "trace.json").exists()
    assert inc.meta["config"] == "D" and inc.meta["total_seconds"] >= 0
    # The orchestrator's ToolLog must be the one the registry writes to (an empty
    # ToolLog is falsy, so `log or ToolLog()` would silently drop it).
    assert trace["toollog"] and inc.meta["n_tool_calls"] >= 1


def test_config_a_end_to_end(tmp_path):
    alert = _alert()
    single = SingleAgentReport(hypothesis="position_spoofing", verdict="supported",
                               confidence=0.95, evidence=[], inference="reasoning",
                               alternatives=[{"hypothesis": "sensor_fault", "reason": "x"}])
    llm = FakeLLM(alert, single_report=single)
    inc, trace = orch.investigate_sync(
        alert, "A", provider=_provider(), retriever=None, run_dir=tmp_path,
        agents_cfg=_AGENTS_CFG, ablations_cfg=_ABLATIONS, models_cfg={"primary": {}}, llm=llm)
    assert inc.verdict == "position_spoofing" and inc.confidence == 0.9
    assert inc.meta["alternatives"] and trace["subagents"]
    assert "subagent:single" in trace["timing_s"]


def test_no_scenario_id_or_split_reaches_prompts(tmp_path):
    alert = _alert()
    llm = _d_llm(alert)
    orch.investigate_sync(alert, "D", provider=_provider(), retriever=None,
                          run_dir=tmp_path, agents_cfg=_AGENTS_CFG, ablations_cfg=_ABLATIONS,
                          models_cfg={"primary": {}}, llm=llm)
    blob = json.dumps(llm.seen, default=str)
    assert not re.search(r"\bS\d{4}\b", blob)
    assert "scenario_id" not in blob and "source_track" not in blob
    assert '"split"' not in blob
    assert set(alert.model_dump()) == {"alert_id", "icao24", "t_start", "t_end",
                                       "score", "top_features", "summary"}
