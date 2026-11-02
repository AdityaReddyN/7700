"""M8 evaluation tests: hermetic. Metrics on synthetic records; the runner and
summariser driven by an injected FakeLLM + synthetic provider (no Ollama)."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from common.schemas import HypothesisReport
from eval import metrics as M
from eval import run_eval, summarize
from test_agents import _AGENTS_CFG, FakeLLM, SingleAgentReport, _AdjOut, _full_triage

_T = 1_575_849_600
_COLS = ["time", "icao24", "lat", "lon", "velocity", "heading", "vertrate",
         "callsign", "squawk", "baroaltitude", "geoaltitude"]
_ABL = {"configs": {
    "A": {"tool_call_limit": 8}, "D": {"tool_call_limit": 3}}}


def _case(label, verdict, *, top2=False, conf=0.8, tot=2, ver=2, par=0, fail=0,
          secs=100.0, inc=False):
    return {"label": label, "verdict": verdict, "correct": verdict == label,
            "top2_correct": top2, "confidence": conf, "evidence_total": tot,
            "evidence_verified": ver, "evidence_partial": par, "evidence_failed": fail,
            "total_seconds": secs, "inconclusive": inc,
            "llm_calls": [{"mode": "native_tools", "tool_calls_count": 1, "tool_call_valid": True,
                           "parse_ok": True},
                          {"mode": "json_schema", "tool_calls_count": 0, "tool_call_valid": None,
                           "parse_ok": True}]}


# --- metrics ---------------------------------------------------------------

def _records():
    return [
        _case("position_spoofing", "position_spoofing", top2=True, conf=0.8),
        _case("sensor_fault", "position_spoofing", conf=0.4, ver=1, fail=1),
        _case("ghost_aircraft", "inconclusive", conf=0.3, tot=0, ver=0, inc=True),
    ]


def test_accuracy_and_classes():
    cs = _records()
    acc = M.accuracy(cs)
    assert acc["n"] == 3 and acc["top1"] == 1 / 3 and acc["top1_count"] == 1
    pc = M.per_class(cs)["position_spoofing"]
    assert pc["n"] == 1 and pc["n_predicted"] == 2 and pc["tp"] == 1
    assert pc["precision"] == 0.5 and pc["recall"] == 1.0


def test_confusion_shape_and_counts():
    conf = M.confusion(_records())
    assert len(conf["rows"]) == 5 and len(conf["cols"]) == 6  # 5 labels + inconclusive
    r = conf["rows"].index("position_spoofing")
    assert conf["matrix"][r][conf["cols"].index("position_spoofing")] == 1


def test_evidence_support_and_inconclusive():
    es = M.evidence_support(_records())
    assert es["n_items"] == 4 and es["verified"] == 3 and es["failed"] == 1
    assert es["support_rate"] == 0.75 and es["unsupported_rate"] == 0.25
    assert M.inconclusive_rate(_records())["rate"] == 1 / 3


def test_calibration_and_llm_quality():
    cal = {b["band"]: b for b in M.calibration(_records())}
    assert cal["<0.5"]["n"] == 2 and cal["<0.5"]["accuracy"] == 0.0
    assert cal[">0.7"]["n"] == 1 and cal[">0.7"]["accuracy"] == 1.0
    q = M.llm_quality(_records())
    assert q["n_tool_turns"] == 3 and q["tool_call_validity"] == 1.0
    assert q["n_structured"] == 3 and q["structured_parse_rate"] == 1.0


def test_bootstrap_ci_deterministic_and_bounded():
    cs = _records()
    a = M.bootstrap_ci(cs, "top1", seed=1)
    b = M.bootstrap_ci(cs, "top1", seed=1)
    assert a == b and a["point"] == 1 / 3
    assert 0.0 <= a["lo"] <= a["point"] <= a["hi"] <= 1.0


# --- runner + summary (hermetic, FakeLLM) ---------------------------------

def _track(icao):
    n = 30
    return pd.DataFrame({
        "time": _T + np.arange(n) * 10, "icao24": icao, "lat": 50.0 + np.arange(n) * 0.01,
        "lon": 8.0, "velocity": 120.0, "heading": 0.0, "vertrate": 0.0, "callsign": "A",
        "squawk": "1000", "baroaltitude": 1e4, "geoaltitude": 1e4})[_COLS]


def _make_data(tmp_path):
    scen_dir = tmp_path / "scenarios"
    scen_dir.mkdir(parents=True)
    scenarios = [
        {"scenario_id": "S0001", "label": "ghost_aircraft", "split": "test",
         "icao24": "aa0001", "t_start": _T, "t_end": _T + 290},
        {"scenario_id": "S0002", "label": "replay_duplicate", "split": "test",
         "icao24": "aa0002", "t_start": _T, "t_end": _T + 290},
        {"scenario_id": "S0003", "label": "sensor_fault", "split": "test",  # missed: no alert
         "icao24": "aa0003", "t_start": _T, "t_end": _T + 290},
    ]
    (scen_dir / "splits.json").write_text(json.dumps({"scenarios": scenarios}))
    alerts = [{"alert_id": f"alert_{s['icao24']}", "icao24": s["icao24"],
               "t_start": s["t_start"], "t_end": s["t_end"], "score": 0.07,
               "top_features": [{"name": "identity_missing", "z": 50.0}],
               "summary": "flagged"} for s in scenarios[:2]]
    (scen_dir / "alerts.json").write_text(json.dumps(alerts))
    (scen_dir / "alert_map.json").write_text(json.dumps(
        {"alert_aa0001": "S0001", "alert_aa0002": "S0002"}))
    tracks = pd.concat([_track("aa0001"), _track("aa0002")], ignore_index=True)
    return tmp_path, tracks


def _factory(tracks):
    from tools.data_tools import TrackProvider
    provider = TrackProvider(con=None, scenario_tracks=tracks, exclude_icao24=set())

    def make(alert, config):
        rep = HypothesisReport(hypothesis="ghost_aircraft", verdict="supported",
                               confidence=0.7, evidence=[], inference="r")
        single = SingleAgentReport(hypothesis="ghost_aircraft", verdict="supported",
                                   confidence=0.7, evidence=[], inference="r",
                                   alternatives=[{"hypothesis": "replay_duplicate", "reason": "x"}])
        return FakeLLM(alert, triage=_full_triage(), subagent_report=rep, single_report=single,
                       adj_out=_AdjOut(verdict="ghost_aircraft", confidence=0.6,
                                       recommended_action="check"))
    return provider, make


def test_run_eval_writes_cases_and_resumes(tmp_path):
    data_dir, tracks = _make_data(tmp_path / "data")
    provider, factory = _factory(tracks)
    run_dir = tmp_path / "results" / "test_run"
    s1 = run_eval.run(["A", "D"], provider=provider, retriever=None, run_dir=run_dir,
                      data_dir=data_dir, llm_factory=factory, agents_cfg=_AGENTS_CFG,
                      models_cfg={"primary": {}}, ablations_cfg=_ABL, resume=True)
    assert s1["n_cases"] == 2 and s1["n_missed"] == 1 and s1["ran"] == 4
    assert (run_dir / "config.json").exists()
    missed = json.loads((run_dir / "missed.json").read_text())
    assert missed["missed_scenarios"] == ["S0003"]
    assert len(list((run_dir / "cases").glob("*.json"))) == 4
    rec = json.loads((run_dir / "cases" / "D__alert_aa0001.json").read_text())
    assert rec["label"] == "ghost_aircraft" and rec["verdict"] == "ghost_aircraft"
    assert rec["correct"] is True and "stage_seconds" in rec
    # Resume: nothing re-runs.
    s2 = run_eval.run(["A", "D"], provider=provider, retriever=None, run_dir=run_dir,
                      data_dir=data_dir, llm_factory=factory, agents_cfg=_AGENTS_CFG,
                      models_cfg={"primary": {}}, ablations_cfg=_ABL, resume=True)
    assert s2["ran"] == 0


def test_summarize_builds_outputs(tmp_path):
    data_dir, tracks = _make_data(tmp_path / "data")
    provider, factory = _factory(tracks)
    run_dir = tmp_path / "results" / "test_run"
    run_eval.run(["A", "D"], provider=provider, retriever=None, run_dir=run_dir,
                 data_dir=data_dir, llm_factory=factory, agents_cfg=_AGENTS_CFG,
                 models_cfg={"primary": {}}, ablations_cfg=_ABL, resume=True)
    mbc = summarize.summarize(run_dir)
    assert set(mbc) == {"A", "D"}
    for name in ("summary.csv", "summary.md", "metrics.json", "spotcheck_template.csv"):
        assert (run_dir / name).exists()
    assert (run_dir / "figures" / "accuracy_by_config.png").exists()
    assert (run_dir / "figures" / "confusion_D.png").exists()
    body = (run_dir / "summary.md").read_text(encoding="utf-8")
    assert "missed detection" in body and "n = 2 evaluated of 3" in body
