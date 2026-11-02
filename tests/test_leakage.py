"""M3 leakage test: enforce that no test-split info can reach KB/prompts/alerts.

Hermetic checks on synthetic catalogs, plus an integration pass over the real
data/scenarios/splits.json when it exists (skipped on a fresh checkout).
"""

import json
from pathlib import Path

import pandas as pd
import pytest

from common.config import REPO_ROOT, get_settings
from scenarios import leakage

_GROUPS = {"kb": [0, 1], "dev": [2, 3], "test": [4, 5]}
_T = 1_575_849_600  # 2019-12-09 00:00:00 UTC


def _scn(sid, label, split, icao, hour, dur=300, **params):
    t0 = _T + hour * 3600
    return {"scenario_id": sid, "label": label, "split": split, "difficulty": "medium",
            "icao24": icao, "t_start": t0, "t_end": t0 + dur, "n_points": 10,
            "params": params, "source_track_ref": f"{icao}:{hour}:{t0}-{t0 + dur}"}


def _clean_catalog():
    return {
        "hour_groups": _GROUPS,
        "scenarios": [
            _scn("S0001", "position_spoofing", "kb", "aaa111", 0),
            _scn("S0002", "ghost_aircraft", "dev", "bbb222", 2),
            _scn("S0003", "sensor_fault", "test", "ccc333", 4),
            _scn("S0004", "replay_duplicate", "test", "ddd444", 5,
                 mode="window_copy", source_window=[_T + 5 * 3600, _T + 5 * 3600 + 200]),
        ],
    }


def test_clean_catalog_has_no_violations():
    assert leakage.run_all(_clean_catalog(), kb_dir=Path("nonexistent"), tracks_columns=["time"]) == []


def test_overlapping_hour_groups_flagged():
    bad = {"a": [1, 2], "b": [2, 3]}
    assert leakage.check_hour_groups_disjoint(bad)


def test_cross_split_overlap_flagged():
    cat = _clean_catalog()
    # Add a kb scenario on the same aircraft and overlapping window as a test one.
    cat["scenarios"].append(_scn("S0005", "sensor_fault", "kb", "ccc333", 4))
    assert leakage.check_cross_split_overlap(cat["scenarios"])


def test_replay_source_outside_group_flagged():
    cat = _clean_catalog()
    cat["scenarios"].append(
        _scn("S0006", "replay_duplicate", "test", "eee555", 5,
             mode="window_copy", source_window=[_T + 0 * 3600, _T + 0 * 3600 + 200])  # kb hour
    )
    assert leakage.check_source_windows_in_group(cat["scenarios"], cat["hour_groups"])


def test_test_ids_in_kb_flagged(tmp_path):
    kb = tmp_path / "kb" / "cards"
    kb.mkdir(parents=True)
    (kb / "C001.md").write_text("see scenario S0003 for details", encoding="utf-8")
    assert leakage.check_no_test_ids_in_kb(tmp_path / "kb", {"S0003"})
    assert leakage.check_no_test_ids_in_kb(tmp_path / "kb", {"S0099"}) == []  # not a test id


def test_generated_kb_cards_carry_no_test_ids(tmp_path):
    """M6: cards generated from a catalog that includes test scenarios leak no test id."""
    from kb.cards import generate_cards

    cat = {"scenarios": (
        [_scn(f"S000{i}", lab, "kb", f"kb{i}", 0)
         for i, lab in enumerate(["position_spoofing", "ghost_aircraft",
                                   "replay_duplicate", "sensor_fault", "benign_anomaly"], 1)]
        + [_scn(f"S000{i}", lab, "kb", f"kc{i}", 1)
           for i, lab in enumerate(["position_spoofing", "ghost_aircraft",
                                     "replay_duplicate", "sensor_fault", "benign_anomaly"], 6)]
        + [_scn("S9001", "sensor_fault", "test", "tst001", 4)]
    )}
    cols = ["time", "icao24", "lat", "lon", "velocity", "heading", "vertrate",
            "callsign", "squawk", "baroaltitude", "geoaltitude"]

    def loader(scn):
        return pd.DataFrame({"time": [0, 10, 20], "icao24": scn["icao24"],
                             "lat": [50.0, 50.01, 50.02], "lon": 8.0, "velocity": 200.0,
                             "heading": 0.0, "vertrate": 0.0, "callsign": "A",
                             "squawk": "1", "baroaltitude": 1e4, "geoaltitude": 1e4})[cols]

    generate_cards(cat, loader, tmp_path / "kb" / "cards")
    test_ids = {s["scenario_id"] for s in cat["scenarios"] if s["split"] == "test"}
    assert leakage.check_no_test_ids_in_kb(tmp_path / "kb", test_ids) == []


def test_tracks_and_alert_schema_have_no_label():
    assert leakage.check_tracks_no_label(["time", "icao24", "scenario_id"]) == []
    assert leakage.check_tracks_no_label(["time", "label"])
    assert leakage.check_alert_schema_no_label() == []


def test_real_catalog_is_clean_if_present():
    path = REPO_ROOT / "data" / "scenarios" / "splits.json"
    if not path.exists():
        pytest.skip("no generated scenarios; run `make scenarios`")
    catalog = json.loads(path.read_text(encoding="utf-8"))
    data_dir = (REPO_ROOT / get_settings().data_dir).resolve()
    tracks = pd.read_parquet(data_dir / "scenarios" / "tracks.parquet")
    violations = leakage.run_all(
        catalog, kb_dir=REPO_ROOT / "data" / "kb", tracks_columns=list(tracks.columns)
    )
    assert violations == [], violations
