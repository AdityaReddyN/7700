"""M5 tool tests: hermetic, no real data.

Synthetic tracks and a fake provider exercise the four data tools, the BM25
retriever, the ToolLog (dedup, truncation, full-vs-view) and the registry, plus
the no-leakage guarantee on every tool output.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from common.schemas import Alert, ToolResult
from tools import data_tools as dt
from tools.registry import ToolRegistry
from tools.retrieval import Card, CaseRetriever, retrieve_cases
from tools.toollog import ToolLog, truncate_output

_MS_PER_DEG_LAT = 111_320.0
_COLS = ["time", "icao24", "lat", "lon", "velocity", "heading", "vertrate",
         "callsign", "squawk", "baroaltitude", "geoaltitude"]


def _track(icao24="aaa111", v_ms=200.0, n=60, t0=0, callsign="DLH1", squawk="1000"):
    dlat = (v_ms * 10.0) / _MS_PER_DEG_LAT
    return pd.DataFrame({
        "time": t0 + np.arange(n) * 10,
        "icao24": icao24,
        "lat": 50.0 + np.arange(n) * dlat,
        "lon": 8.0,
        "velocity": v_ms, "heading": 0.0, "vertrate": 0.0,
        "callsign": callsign, "squawk": squawk,
        "baroaltitude": 10000.0, "geoaltitude": 10000.0,
    })[_COLS]


# --- shared computations ---------------------------------------------------

def test_window_summary_fields():
    s = dt.window_summary(_track(n=60))
    assert s["n_points"] == 60
    assert s["t_first"] == 0 and s["t_last"] == 590
    assert s["max_gap_s"] == 10.0 and s["missing_fraction"] < 0.05
    assert s["altitude_first_m"] == 10000.0


def test_kinematics_normal_vs_jump():
    norm = dt.kinematics(_track(n=60))
    assert norm["residual_kt_median"] < 5.0
    assert norm["largest_jump_km"] < 3.0
    jump = _track(n=60)
    jump.loc[30:, "lat"] = jump.loc[30:, "lat"] + 0.5
    kj = dt.kinematics(jump)
    assert kj["largest_jump_km"] > 10.0
    assert kj["residual_kt_max"] > 100.0
    assert kj["largest_jump_t"] == 300


def test_identity_changes_and_duplicates():
    df = _track(n=20)
    df.loc[10:, "squawk"] = "7700"
    ident = dt.identity(df)
    assert ident["squawk_changes"] == 1
    assert ident["callsign_changes"] == 0
    dup = pd.DataFrame({
        "time": [0, 2], "icao24": "x", "lat": [50.0, 51.5], "lon": [8.0, 8.0],
        "velocity": 200.0, "heading": 0.0, "vertrate": 0.0,
        "callsign": "A", "squawk": "1", "baroaltitude": 1e4, "geoaltitude": 1e4,
    })[_COLS]
    assert dt.identity(dup)["duplicate_position_pairs"] >= 1


def test_compute_features_degenerate():
    assert dt.kinematics(pd.DataFrame())["n_points_used"] == 0
    assert dt.window_summary(pd.DataFrame())["n_points"] == 0
    assert dt.identity(pd.DataFrame())["n_points"] == 0


# --- track provider --------------------------------------------------------

def test_provider_resolves_scenario_view():
    df = pd.concat([_track("aaa111", n=30, t0=0), _track("bbb222", n=30, t0=0)],
                   ignore_index=True)
    prov = dt.TrackProvider(con=None, scenario_tracks=df)
    got = prov.track("aaa111", 0, 200)
    assert len(got) == 21 and set(got["icao24"]) == {"aaa111"}
    assert prov.track("zzz999", 0, 200).empty  # no match, no real store


# --- compare_to_baseline ---------------------------------------------------

class _FakeProvider:
    def __init__(self, alert_track, baseline):
        self._alert = alert_track
        self._baseline = baseline

    def track(self, icao24, t_start, t_end):
        return self._alert

    def baseline_windows(self, hour):
        yield from self._baseline


def test_compare_to_baseline_flags_outlier():
    outlier = _track(n=60)
    outlier.loc[30:, "lat"] = outlier.loc[30:, "lat"] + 0.5  # big residual + jump
    baseline = [_track(v_ms=180.0 + i * 5, n=60) for i in range(20)]
    prov = _FakeProvider(outlier, baseline)
    out, ref_id = dt.compare_to_baseline(
        prov, "alert_x", alert_icao24="aaa111", alert_t_start=0, alert_t_end=590,
        feature="largest_jump_km", context="all")
    assert out["feature"] == "largest_jump_km"
    assert out["n_baseline"] == 20
    assert out["value"] > out["baseline_p95"]
    assert out["z"] is not None and out["z"] > 0
    assert ref_id.startswith("calc:alert_x:base:")


def test_compare_to_baseline_empty_baseline():
    prov = _FakeProvider(_track(n=60), [])
    out, _ = dt.compare_to_baseline(
        prov, "a", alert_icao24="aaa111", alert_t_start=0, alert_t_end=590,
        feature="residual_kt_median", context="all")
    assert out["n_baseline"] == 0 and out["baseline_median"] is None and out["z"] is None


# --- retrieval -------------------------------------------------------------

def _cards():
    return [
        Card("C01", "position_spoofing", "Drift spoof",
             "Position drifts away while the reported speed stays unchanged."),
        Card("C02", "ghost_aircraft", "Fabricated track",
             "A track with no callsign or squawk flying a perfectly straight path."),
        Card("C03", "replay_duplicate", "Address duplicate",
             "The same address reports from two distant positions at the same time."),
    ]


def test_retriever_ranks_and_empty():
    r = CaseRetriever(_cards())
    hits = r.search("same address two positions", "replay_duplicate", k=2)
    assert hits and hits[0]["card_id"] == "C03"
    assert CaseRetriever([]).search("anything", "ghost_aircraft") == []


def test_retrieve_cases_returns_extra_card_refs():
    r = CaseRetriever(_cards())
    output, ref_id, extra = retrieve_cases(r, "alert_x", query="ghost no squawk",
                                           hypothesis="ghost_aircraft", k=4)
    assert ref_id.startswith("case:q:")
    assert output["cases"] and all({"card_id", "label", "title", "snippet"} == set(c)
                                   for c in output["cases"])
    assert all(eid.startswith("case:") for eid, _ in extra)


# --- ToolLog ---------------------------------------------------------------

def test_toollog_dedup_and_views():
    log = ToolLog(max_chars=1600)
    v1 = log.record("compute_kinematics", {"a": 1}, {"x": 1.0}, "calc:a:kin:deadbeef")
    v2 = log.record("compute_kinematics", {"a": 1}, {"x": 1.0}, "calc:a:kin:deadbeef")
    assert v1 is v2 and len(log) == 1
    assert isinstance(v1, ToolResult)
    assert log.get_full("calc:a:kin:deadbeef").output == {"x": 1.0}


def test_truncate_output_trims_longest_list():
    big = {"cases": [{"card_id": f"C{i:02d}", "text": "x" * 200} for i in range(20)]}
    trimmed, cut = truncate_output(big, 400)
    assert cut and len(trimmed["cases"]) < 20
    small = {"value": 1.0, "z": 2.0}
    out, cut2 = truncate_output(small, 1600)
    assert out == small and cut2 is False


# --- registry --------------------------------------------------------------

def _registry(retriever=None):
    df = _track("aaa111", n=60)
    prov = dt.TrackProvider(con=None, scenario_tracks=df)
    alert = Alert(alert_id="alert_aaa111_0_590", icao24="aaa111", t_start=0, t_end=590,
                  score=1.0, summary="Unusual track behaviour.")
    return ToolRegistry(alert, prov, retriever=retriever)


def test_registry_dispatches_and_logs_ref_ids():
    reg = _registry()
    w = reg.call("get_track_window", {"icao24": "aaa111", "t_start": 0, "t_end": 590})
    assert w.ref_id == "win:alert_aaa111_0_590:0-590" and w.output["n_points"] == 60
    k = reg.call("compute_kinematics", {"icao24": "aaa111", "t_start": 0, "t_end": 590})
    assert k.ref_id.startswith("calc:alert_aaa111_0_590:kin:")
    i = reg.call("check_identity", {"icao24": "aaa111", "t_start": 0, "t_end": 590})
    assert i.ref_id.startswith("calc:alert_aaa111_0_590:id:")
    # identical call -> cached, no new log entry
    before = len(reg.log)
    reg.call("get_track_window", {"icao24": "aaa111", "t_start": 0, "t_end": 590})
    assert len(reg.log) == before


def test_registry_retrieve_logs_per_card():
    reg = _registry(retriever=CaseRetriever(_cards()))
    res = reg.call("retrieve_cases", {"query": "address two positions",
                                      "hypothesis": "replay_duplicate", "k": 3})
    assert res.ref_id.startswith("case:q:")
    assert any(rid.startswith("case:C") for rid in reg.log.as_dict())


def test_registry_rejects_unknown_tool():
    reg = _registry()
    try:
        reg.call("run_sql", {"q": "select 1"})
    except ValueError as e:
        assert "unknown tool" in str(e)
    else:
        raise AssertionError("expected ValueError for unknown tool")


# --- leakage ---------------------------------------------------------------

def test_tool_outputs_carry_no_label_or_scenario_id():
    reg = _registry(retriever=CaseRetriever(_cards()))
    for name, args in [
        ("get_track_window", {"icao24": "aaa111", "t_start": 0, "t_end": 590}),
        ("compute_kinematics", {"icao24": "aaa111", "t_start": 0, "t_end": 590}),
        ("check_identity", {"icao24": "aaa111", "t_start": 0, "t_end": 590}),
    ]:
        reg.call(name, args)
    blob = json.dumps(reg.log.as_dict())
    import re
    assert not re.search(r"\bS\d{4}\b", blob)
    assert "scenario_id" not in blob and "split" not in blob
    # the data-tool outputs never contain a class label
    data_only = {k: v for k, v in reg.log.as_dict().items() if not k.startswith("case:")}
    data_blob = json.dumps(data_only)
    for lab in ("position_spoofing", "ghost_aircraft", "replay_duplicate",
                "sensor_fault", "benign_anomaly"):
        assert lab not in data_blob
