"""M4 detector tests: hermetic, no real data.

Synthetic tracks exercise each feature and the Isolation Forest / rule scorers,
plus the threshold-tuning and metrics helpers and the no-label guarantee on the
Alert objects the detector builds.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from common.schemas import Alert
from detector import alerts as alerts_mod
from detector.baseline import Baseline
from detector.features import (
    FEATURE_NAMES,
    compute_features,
    feature_vector,
    mad,
    robust_z,
)
from detector.flagger import RuleFlagger
from detector.model import IsolationForestDetector

_MS_PER_DEG_LAT = 111_320.0


def _normal_track(v_ms: float = 200.0, n: int = 60, t0: int = 0, jitter_m: float = 0.0,
                  seed: int = 0) -> pd.DataFrame:
    """A straight northbound track whose positions agree with its reported speed."""
    rng = np.random.default_rng(seed)
    dlat = (v_ms * 10.0) / _MS_PER_DEG_LAT
    lat = 50.0 + np.arange(n) * dlat
    lon = np.full(n, 8.0)
    if jitter_m:
        lat = lat + rng.normal(0, jitter_m / _MS_PER_DEG_LAT, n)
        lon = lon + rng.normal(0, jitter_m / _MS_PER_DEG_LAT, n)
    return pd.DataFrame({
        "time": t0 + np.arange(n) * 10,
        "icao24": "abc123",
        "lat": lat, "lon": lon,
        "velocity": v_ms, "heading": 0.0, "vertrate": 0.0,
        "callsign": "DLH123", "squawk": "1000",
        "baroaltitude": 10000.0, "geoaltitude": 10000.0,
    })


def test_normal_track_is_quiet():
    f = compute_features(_normal_track())
    assert f["speed_resid_kt_med"] < 5.0
    assert f["largest_jump_km"] < 3.0
    assert f["dup_pairs"] == 0.0
    assert f["identity_missing"] == 0.0
    assert f["missing_frac"] < 0.05


def test_position_jump_shows_in_features():
    df = _normal_track()
    df.loc[30:, "lat"] = df.loc[30:, "lat"] + 0.5  # ~55 km northward step
    f = compute_features(df)
    assert f["largest_jump_km"] > 10.0
    assert f["speed_resid_kt_max"] > 100.0


def test_address_duplicate_shows_dup_pairs():
    df = _normal_track(n=30)
    dup = df.copy()
    dup["time"] = dup["time"] + 2
    dup["lat"] = dup["lat"] + 1.5  # ~160 km away
    both = pd.concat([df, dup], ignore_index=True)
    f = compute_features(both)
    assert f["dup_pairs"] >= 1.0


def test_ghost_track_has_no_identity_and_constant_speed():
    df = _normal_track(n=40)
    df["callsign"] = pd.NA
    df["squawk"] = pd.NA
    f = compute_features(df)
    assert f["identity_missing"] == 1.0
    assert f["vel_cv"] == 0.0


def test_dropout_shows_gap_and_missing():
    df = _normal_track(n=60)
    df = df.drop(index=range(20, 35)).reset_index(drop=True)  # 150 s hole
    f = compute_features(df)
    assert f["max_gap_s"] >= 150.0
    assert f["missing_frac"] > 0.1


def test_compute_features_handles_degenerate_input():
    assert compute_features(pd.DataFrame()) == dict.fromkeys(FEATURE_NAMES, 0.0)
    one = _normal_track(n=1)
    f = compute_features(one)
    assert all(np.isfinite(v) for v in f.values())


def _baseline_from_normals(n: int = 80) -> Baseline:
    mats = []
    for s in range(n):
        v = 180.0 + (s % 20) * 4.0
        mats.append(feature_vector(compute_features(
            _normal_track(v_ms=v, jitter_m=15.0, seed=s))))
    matrix = np.vstack(mats)
    median = np.median(matrix, axis=0)
    mad_vec = np.array([mad(matrix[:, j]) for j in range(matrix.shape[1])])
    return Baseline(matrix=matrix, median=median, mad=mad_vec,
                    feature_names=FEATURE_NAMES, n_windows=n, hours=[6])


def test_isolation_forest_scores_outlier_above_normal():
    base = _baseline_from_normals()
    det = IsolationForestDetector(
        {"n_estimators": 100, "contamination": "auto", "random_state": 42}).fit(base)
    normal = feature_vector(compute_features(_normal_track(v_ms=210.0, jitter_m=15.0, seed=999)))
    jump = _normal_track(n=60)
    jump.loc[30:, "lat"] = jump.loc[30:, "lat"] + 0.5
    outlier = feature_vector(compute_features(jump))
    assert det.score(outlier) > det.score(normal)


def test_isolation_forest_is_deterministic():
    base = _baseline_from_normals()
    vec = feature_vector(compute_features(_normal_track(v_ms=205.0, jitter_m=15.0, seed=7)))
    s1 = IsolationForestDetector({"random_state": 42}).fit(base).score(vec)
    s2 = IsolationForestDetector({"random_state": 42}).fit(base).score(vec)
    assert s1 == s2


def test_rule_flagger_scores_outlier_above_normal():
    base = _baseline_from_normals()
    fl = RuleFlagger({"z_flag": 4.0}).fit(base)
    normal = feature_vector(compute_features(_normal_track(v_ms=210.0, jitter_m=15.0, seed=321)))
    dup = _normal_track(n=30)
    d2 = dup.copy()
    d2["time"] = d2["time"] + 2
    d2["lat"] = d2["lat"] + 1.5
    outlier = feature_vector(compute_features(pd.concat([dup, d2], ignore_index=True)))
    assert fl.score(outlier) > fl.score(normal)


def test_robust_z_handles_constant_baseline():
    assert robust_z(0.0, 0.0, 0.0) == 0.0
    assert robust_z(5.0, 0.0, 0.0) == 50.0  # capped, finite
    assert abs(robust_z(10.0, 0.0, 2.0)) > 0.0


def test_threshold_tuning_meets_target_recall():
    dev = [{"score": s, "is_positive": True} for s in (0.9, 0.8, 0.7, 0.6, 0.5)]
    dev += [{"score": s, "is_positive": False} for s in (0.1, 0.2)]
    thr = alerts_mod._tune_threshold(dev, 0.8)
    recall = sum(r["score"] >= thr for r in dev if r["is_positive"]) / 5
    assert recall >= 0.8


def test_threshold_from_budget_caps_false_positive_rate():
    base = np.linspace(0.0, 1.0, 1000)  # 1000 normal scores in [0, 1]
    thr = alerts_mod._threshold_from_budget(base, 0.05)
    rate = float(np.mean(base >= thr))
    assert abs(rate - 0.05) < 0.02  # roughly the top 5% of normal traffic
    # A tighter budget raises the threshold (flags fewer).
    assert alerts_mod._threshold_from_budget(base, 0.01) > thr


def test_split_metrics_counts():
    rows = [
        {"label": "position_spoofing", "score": 1.0},
        {"label": "ghost_aircraft", "score": 0.1},
        {"label": "benign_anomaly", "score": 1.0},
        {"label": "benign_anomaly", "score": 0.0},
    ]
    m = alerts_mod._split_metrics(rows, threshold=0.5)
    assert m["tp"] == 1 and m["n_positive"] == 2
    assert m["fp"] == 1 and m["n_benign"] == 2
    assert m["recall"] == 0.5 and m["benign_flag_rate"] == 0.5


def test_built_alert_carries_no_label_or_scenario_id():
    base = _baseline_from_normals()
    jump = _normal_track(n=60)
    jump.loc[30:, "lat"] = jump.loc[30:, "lat"] + 0.5
    vec = feature_vector(compute_features(jump))
    top = alerts_mod._top_features(vec, base)
    alert = Alert(alert_id="alert_abc123_0_600", icao24="abc123", t_start=0, t_end=600,
                  score=1.23, top_features=top, summary=alerts_mod._summary(top))
    blob = alert.model_dump_json()
    assert "label" not in Alert.model_fields
    assert "scenario_id" not in blob and "position_spoofing" not in blob
    assert len(top) == 3 and all({"name", "z"} == set(t) for t in top)
