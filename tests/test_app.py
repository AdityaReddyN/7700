"""M9 app tests: hermetic, loader-only (no Streamlit runtime).

Importing `app.streamlit_app` would call `main()` outside a Streamlit context,
so these tests exercise only `app.loader` over synthetic `results/`/`runs/`
directories, plus the no-leakage property of what the app surfaces.
"""

from __future__ import annotations

import json

import pandas as pd
import plotly.graph_objects as go

from app import loader, plots


def _track_df():
    # A drifting track: lon steps grow, so position-implied speed diverges upward.
    t0 = 1_575_867_610
    rows = []
    for i in range(10):
        rows.append({"scenario_id": "S0001", "time": t0 + i * 10, "icao24": "0d09e5",
                     "lat": 46.6 + i * 0.001, "lon": -72.8 + i * 0.002 * (1 + i / 5),
                     "velocity": 200.0, "vertrate": 0.0, "baroaltitude": 10000.0})
    return pd.DataFrame(rows)


def _trace():
    aid = "alert_aa0001_100_390"
    return {
        "investigation_id": "inv_x", "config": "D",
        "alert": {"alert_id": aid, "icao24": "aa0001", "t_start": 100, "t_end": 390,
                  "score": 0.07, "top_features": [{"name": "identity_missing", "z": 50.0}],
                  "summary": "no callsign"},
        "triage": {"kept": [{"hypothesis": "ghost_aircraft", "prior": 0.4, "reason": "r"}],
                   "fallback": False},
        "subagents": [{"hypothesis": "ghost_aircraft", "verdict": "inconclusive",
                       "confidence": 0.5, "evidence": [{"claim": "c", "ref_id": "calc:x:1",
                       "stat": "s", "value": 1.0, "verified": True}],
                       "inference": "i", "tool_calls_used": 2}],
        "verification": [{"hypothesis": "ghost_aircraft", "n_total": 1, "n_verified": 1,
                          "n_partial": 0, "n_failed": 0, "items": []}],
        "report": {"alert_id": aid, "verdict": "inconclusive", "confidence": 0.0,
                   "ranked": [], "evidence_table": [], "excluded_evidence_count": 0,
                   "inference": "none", "meta": {"verdict_overridden": True,
                                                 "proposed_verdict": "position_spoofing"}},
        "timing_s": {"triage": 25.5, "subagent:ghost_aircraft": 90.2,
                     "verification": 0.0, "adjudication": 42.1},
        "toollog": {"calc:x:1": {"ref_id": "calc:x:1", "tool": "k", "args": {},
                                 "output": {"s": 1.0}}},
        "llm_calls": [],
    }


def _make_run(tmp_path):
    run = tmp_path / "results" / "r1"
    (run / "cases").mkdir(parents=True)
    (run / "traces" / "D__alert_aa0001_100_390").mkdir(parents=True)
    for cfg in ("A", "D"):
        (run / "cases" / f"{cfg}__alert_aa0001_100_390.json").write_text(json.dumps(
            {"alert_id": "alert_aa0001_100_390", "config": cfg, "label": "ghost_aircraft",
             "verdict": "inconclusive", "total_seconds": 100.0}))
    (run / "traces" / "D__alert_aa0001_100_390" / "trace.json").write_text(
        json.dumps(_trace()))
    (run / "metrics.json").write_text(json.dumps({"D": {"accuracy": {"n": 1}}}))
    (run / "missed.json").write_text(json.dumps(
        {"n_test": 25, "n_evaluated": 10, "missed_scenarios": ["S0006"],
         "missed_by_label": {"position_spoofing": 5}}))
    return run


def test_eval_runs_and_loaders(tmp_path):
    run = _make_run(tmp_path)
    runs = loader.eval_runs(tmp_path / "results")
    assert runs == [run]
    by_config = loader.load_cases(run)
    assert set(by_config) == {"A", "D"} and len(by_config["D"]) == 1
    assert loader.load_metrics(run)["D"]["accuracy"]["n"] == 1
    assert loader.load_missed(run)["n_evaluated"] == 10


def test_load_trace_and_toollog(tmp_path):
    run = _make_run(tmp_path)
    tr = loader.load_trace(run, "D", "alert_aa0001_100_390")
    assert tr and tr["report"]["verdict"] == "inconclusive"
    assert loader.toollog_output(tr, "calc:x:1") == {"s": 1.0}
    assert loader.toollog_output(tr, "missing") is None


def test_stage_steps_order_and_timing():
    steps = loader.stage_steps(_trace())
    assert [s["kind"] for s in steps] == ["triage", "subagent", "verification", "adjudication"]
    assert steps[0]["seconds"] == 25.5
    assert steps[1]["body"]["verification"]["n_verified"] == 1
    assert steps[-1]["body"]["meta"]["verdict_overridden"] is True


def test_live_runs(tmp_path):
    rd = tmp_path / "runs" / "inv_1"
    rd.mkdir(parents=True)
    (rd / "trace.json").write_text(json.dumps(_trace()))
    assert loader.live_runs(tmp_path / "runs") == [rd]


def test_app_surfaces_no_leakage():
    """Nothing the app renders from a trace carries a scenario id, split or label."""
    blob = json.dumps(loader.stage_steps(_trace())) + json.dumps(_trace()["alert"])
    assert "scenario_id" not in blob and '"split"' not in blob
    import re
    assert not re.search(r"\bS\d{4}\b", blob)


# --- track helpers + plots -------------------------------------------------

def test_track_window_and_implied_speed():
    df = _track_df()
    win = loader.track_window(df, "0d09e5", df["time"].iloc[0], df["time"].iloc[-1])
    assert len(win) == 10
    speeds = loader.implied_speed_kt(win)
    assert speeds[0] is None and all(s > 0 for s in speeds[1:])
    # drift: implied speed should increase as the steps grow
    assert speeds[-1] > speeds[1]
    assert loader.track_by_scenario(df, "S0001").shape[0] == 10
    assert loader.track_by_scenario(df, "NOPE").empty


def test_models_and_headline_run(tmp_path):
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "models.yaml").write_text(
        "primary:\n  backend: ollama\n  model: llama3.1:8b\ntriage:\n  model: llama3.2:3b\n")
    mu = loader.models_used(cfg)
    assert mu["primary"] == "llama3.1:8b" and mu["triage"] == "llama3.2:3b"
    res = tmp_path / "results"
    (res / "test_final" / "cases").mkdir(parents=True)
    (res / "test_final" / "metrics.json").write_text("{}")
    assert loader.headline_run(res).name == "test_final"


def test_plots_return_figures():
    df = _track_df()
    for fig in (plots.track_map(df), plots.speed_drift(df), plots.residual(df),
                plots.altitude(df)):
        assert isinstance(fig, go.Figure) and len(fig.data) >= 1
    # empty input yields a valid (annotated) figure, not a crash
    assert isinstance(plots.track_map(pd.DataFrame()), go.Figure)
