"""M4: per-window track features for the detector.

Pure functions over a single track's state records (one window of one icao24).
Features are chosen to react to the four injected signatures without naming any
label, and are built to be robust to short or degenerate windows (they never
raise and always return finite floats). Rates, medians and fractions are used in
preference to raw counts so a feature means roughly the same on a 2-minute ghost
window and a 10-minute cruise window.

The feature vector is the only thing the detector sees; it carries no label, no
scenario id and no split name.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Fixed order. Both the Isolation Forest matrix and the rule z-scores use it.
FEATURE_NAMES: tuple[str, ...] = (
    "speed_resid_kt_med",    # reported vs position-implied speed (median), kt
    "speed_resid_kt_max",    # reported vs position-implied speed (max), kt
    "largest_jump_km",       # largest step between consecutive positions, km
    "max_gap_s",             # largest time gap between consecutive points, s
    "missing_frac",          # fraction of expected 10 s samples that are absent
    "dup_pairs",             # near-simultaneous points far apart (same address)
    "scatter_m",             # median position second-difference magnitude, m
    "max_stuck_run",         # longest run of a frozen lat/lon position
    "time_irregularity",     # spread of inter-sample gaps / median gap
    "vertrate_mismatch_ms",  # reported climb rate vs observed d(alt)/dt, m/s
    "identity_missing",      # fraction of points with no callsign and no squawk
    "vel_cv",                # coefficient of variation of reported speed
)

_KT_PER_MS = 1.0 / 0.514444
_EARTH_R_M = 6_371_000.0
_CADENCE_S = 10.0
# A near-simultaneous pair this far apart implies two aircraft on one address.
_DUP_TIME_TOL_S = 5.0
_DUP_DIST_KM = 10.0


def _haversine_m(
    lat1: np.ndarray, lon1: np.ndarray, lat2: np.ndarray, lon2: np.ndarray
) -> np.ndarray:
    """Great-circle distance in metres between paired points (degrees in)."""
    p1 = np.radians(lat1)
    p2 = np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlmb = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    return 2 * _EARTH_R_M * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def _local_xy_m(lat: np.ndarray, lon: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Equirectangular projection to local metres about the window's first point."""
    lat0 = float(lat[0])
    x = np.radians(lon - lon[0]) * np.cos(np.radians(lat0)) * _EARTH_R_M
    y = np.radians(lat - lat[0]) * _EARTH_R_M
    return x, y


def _longest_frozen_run(lat: np.ndarray, lon: np.ndarray) -> int:
    """Longest run of consecutive points whose position does not change at all."""
    if lat.size < 2:
        return 0
    same = (np.diff(lat) == 0.0) & (np.diff(lon) == 0.0)
    best = run = 0
    for s in same:
        run = run + 1 if s else 0
        best = max(best, run)
    return best + 1 if best else 0


def _finite(x: float, default: float = 0.0) -> float:
    return float(x) if np.isfinite(x) else default


def compute_features(df: pd.DataFrame) -> dict[str, float]:
    """Compute the feature dict for one track window. Never raises."""
    feats = dict.fromkeys(FEATURE_NAMES, 0.0)
    if df is None or len(df) == 0:
        return feats

    d = df.sort_values("time", kind="mergesort").reset_index(drop=True)
    t = pd.to_numeric(d["time"], errors="coerce").to_numpy(dtype="float64")
    lat = pd.to_numeric(d["lat"], errors="coerce").to_numpy(dtype="float64")
    lon = pd.to_numeric(d["lon"], errors="coerce").to_numpy(dtype="float64")
    vel = pd.to_numeric(d.get("velocity"), errors="coerce").to_numpy(dtype="float64")
    n = len(d)

    # Identity: a point with neither callsign nor squawk.
    def _blank(col: str) -> np.ndarray:
        if col not in d:
            return np.ones(n, dtype=bool)
        s = d[col].astype("string").str.strip()
        return s.isna().to_numpy() | (s == "").to_numpy()

    feats["identity_missing"] = _finite((_blank("callsign") & _blank("squawk")).mean())

    # Speed coefficient of variation (0 for a perfectly constant ghost cruise).
    vfin = vel[np.isfinite(vel)]
    if vfin.size >= 2 and np.nanmean(vfin) > 1e-6:
        feats["vel_cv"] = _finite(np.nanstd(vfin) / np.nanmean(vfin))

    if n < 2:
        return feats

    dt = np.diff(t)
    pos = dt > 0
    # Timing: gaps, missing samples, cadence irregularity.
    if pos.any():
        dtp = dt[pos]
        feats["max_gap_s"] = _finite(dtp.max())
        med_gap = float(np.median(dtp))
        feats["time_irregularity"] = _finite(np.std(dtp) / med_gap) if med_gap > 0 else 0.0
    span = t[-1] - t[0]
    if span > 0:
        expected = span / _CADENCE_S + 1.0
        feats["missing_frac"] = _finite(max(0.0, 1.0 - n / expected))

    # Step distances between consecutive positions.
    step_m = _haversine_m(lat[:-1], lon[:-1], lat[1:], lon[1:])
    feats["largest_jump_km"] = _finite(np.nanmax(step_m) / 1000.0)

    # Reported vs position-implied speed. Compare the implied step speed with the
    # mean reported speed over the step; large where positions and velocity disagree.
    with np.errstate(divide="ignore", invalid="ignore"):
        implied = np.where(pos, step_m / dt, np.nan)
    rep_pair = (vel[:-1] + vel[1:]) / 2.0
    resid_ms = np.abs(implied - rep_pair)
    resid_ms = resid_ms[np.isfinite(resid_ms)]
    if resid_ms.size:
        feats["speed_resid_kt_med"] = _finite(np.median(resid_ms) * _KT_PER_MS)
        feats["speed_resid_kt_max"] = _finite(resid_ms.max() * _KT_PER_MS)

    # Near-simultaneous points far apart => one address, two places.
    dup = 0
    order = np.argsort(t, kind="mergesort")
    ts, las, los = t[order], lat[order], lon[order]
    i = 0
    while i < n:
        j = i + 1
        while j < n and (ts[j] - ts[i]) <= _DUP_TIME_TOL_S:
            if _haversine_m(
                np.array([las[i]]), np.array([los[i]]),
                np.array([las[j]]), np.array([los[j]]),
            )[0] / 1000.0 > _DUP_DIST_KM:
                dup += 1
            j += 1
        i += 1
    feats["dup_pairs"] = float(dup)

    # Position scatter: median magnitude of the second difference, in metres.
    if n >= 3:
        x, y = _local_xy_m(lat, lon)
        d2x = x[2:] - 2 * x[1:-1] + x[:-2]
        d2y = y[2:] - 2 * y[1:-1] + y[:-2]
        feats["scatter_m"] = _finite(np.median(np.hypot(d2x, d2y)))

    feats["max_stuck_run"] = float(_longest_frozen_run(lat, lon))

    # Reported climb rate vs observed altitude change.
    if "baroaltitude" in d and "vertrate" in d:
        alt = pd.to_numeric(d["baroaltitude"], errors="coerce").to_numpy(dtype="float64")
        vr = pd.to_numeric(d["vertrate"], errors="coerce").to_numpy(dtype="float64")
        with np.errstate(divide="ignore", invalid="ignore"):
            obs = np.where(pos, np.diff(alt) / dt, np.nan)
        mism = np.abs(obs - (vr[:-1] + vr[1:]) / 2.0)
        mism = mism[np.isfinite(mism)]
        if mism.size:
            feats["vertrate_mismatch_ms"] = _finite(np.median(mism))

    return feats


def feature_vector(feats: dict[str, float]) -> np.ndarray:
    """Features as a fixed-order 1-D array."""
    return np.array([feats[name] for name in FEATURE_NAMES], dtype="float64")


def mad(x: np.ndarray) -> float:
    """Median absolute deviation."""
    x = np.asarray(x, dtype="float64")
    if x.size == 0:
        return 0.0
    return float(np.median(np.abs(x - np.median(x))))


def robust_z(value: float, med: float, mad_: float, *, cap: float = 50.0) -> float:
    """Signed robust z-score; MAD floored so near-constant baselines stay finite."""
    scale = 1.4826 * mad_
    if scale <= 1e-9:
        # Near-constant baseline: any departure is anomalous but kept finite.
        if abs(value - med) <= 1e-9:
            return 0.0
        return float(np.sign(value - med) * cap)
    return float(np.clip((value - med) / scale, -cap, cap))
