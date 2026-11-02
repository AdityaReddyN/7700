"""M5: the four data tools and the track provider (ARCHITECTURE §3.1-3.4).

All functions are read-only and deterministic. The alert's own track is resolved
by icao24 + window from the scenario view (`tracks.parquet`) when present, else
the real Parquet store (D-032); `compare_to_baseline` uses only real same-hour
traffic, excluding scenario aircraft. No output carries a label or scenario id.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import duckdb
import numpy as np
import pandas as pd

from common.ids import ref_calc, ref_window
from detector.features import _haversine_m

_KT_PER_MS = 1.0 / 0.514444
_CADENCE_S = 10.0
_DUP_TIME_TOL_S = 5.0
_DUP_DIST_KM = 10.0
_DAY_EPOCH = 1_575_849_600  # 2019-12-09 00:00:00 UTC (the one available day, D-029)
_BASELINE_MAX_AIRCRAFT = 150  # deterministic, bounded per-hour baseline
_BASELINE_MIN_POINTS = 30

_TRACK_COLS = ("time", "icao24", "lat", "lon", "velocity", "heading", "vertrate",
               "callsign", "squawk", "baroaltitude", "geoaltitude")
BASELINE_FEATURES = (
    "residual_kt_median", "largest_jump_km", "max_gap_s",
    "vertrate_vs_altitude_mismatch_ms_median",
)


def hour_of(ts: int) -> int:
    return int((int(ts) - _DAY_EPOCH) // 3600)


def _num(df: pd.DataFrame, col: str) -> np.ndarray:
    return pd.to_numeric(df[col], errors="coerce").to_numpy(dtype="float64")


# --- shared computations ---------------------------------------------------

def window_summary(df: pd.DataFrame) -> dict:
    """ARCHITECTURE §3.1 fields for one track window."""
    if df is None or len(df) == 0:
        return {"n_points": 0, "t_first": None, "t_last": None, "lat_first": None,
                "lon_first": None, "lat_last": None, "lon_last": None, "max_gap_s": 0.0,
                "missing_fraction": 0.0, "altitude_first_m": None, "altitude_last_m": None}
    d = df.sort_values("time", kind="mergesort").reset_index(drop=True)
    t = _num(d, "time")
    gaps = np.diff(t)
    gaps = gaps[gaps > 0]
    span = float(t[-1] - t[0])
    missing = max(0.0, 1.0 - len(d) / (span / _CADENCE_S + 1.0)) if span > 0 else 0.0
    alt = _num(d, "baroaltitude")
    return {
        "n_points": int(len(d)),
        "t_first": int(t[0]), "t_last": int(t[-1]),
        "lat_first": round(float(d["lat"].iloc[0]), 5),
        "lon_first": round(float(d["lon"].iloc[0]), 5),
        "lat_last": round(float(d["lat"].iloc[-1]), 5),
        "lon_last": round(float(d["lon"].iloc[-1]), 5),
        "max_gap_s": round(float(gaps.max()), 1) if gaps.size else 0.0,
        "missing_fraction": round(float(missing), 3),
        "altitude_first_m": None if not np.isfinite(alt[0]) else round(float(alt[0]), 1),
        "altitude_last_m": None if not np.isfinite(alt[-1]) else round(float(alt[-1]), 1),
    }


def kinematics(df: pd.DataFrame) -> dict:
    """ARCHITECTURE §3.2 fields: positions vs reported speed and vertical rate."""
    base = {
        "implied_speed_kt_median": 0.0, "reported_speed_kt_median": 0.0,
        "residual_kt_median": 0.0, "residual_kt_max": 0.0,
        "residual_slope_kt_per_min": 0.0, "largest_jump_km": 0.0,
        "largest_jump_t": None, "vertrate_vs_altitude_mismatch_ms_median": 0.0,
        "n_points_used": 0 if df is None else int(len(df)),
    }
    if df is None or len(df) < 2:
        return base
    d = df.sort_values("time", kind="mergesort").reset_index(drop=True)
    t = _num(d, "time")
    lat, lon = _num(d, "lat"), _num(d, "lon")
    vel = _num(d, "velocity")
    dt = np.diff(t)
    pos = dt > 0
    step_m = _haversine_m(lat[:-1], lon[:-1], lat[1:], lon[1:])

    jmax = int(np.nanargmax(step_m))
    base["largest_jump_km"] = round(float(step_m[jmax]) / 1000.0, 3)
    base["largest_jump_t"] = int(t[jmax + 1])

    rep_kt = vel * _KT_PER_MS
    base["reported_speed_kt_median"] = round(float(np.nanmedian(rep_kt)), 1)
    with np.errstate(divide="ignore", invalid="ignore"):
        implied_kt = np.where(pos, step_m / dt, np.nan) * _KT_PER_MS
    impl_fin = implied_kt[np.isfinite(implied_kt)]
    if impl_fin.size:
        base["implied_speed_kt_median"] = round(float(np.median(impl_fin)), 1)
    rep_pair_kt = (rep_kt[:-1] + rep_kt[1:]) / 2.0
    resid = np.abs(implied_kt - rep_pair_kt)
    mask = np.isfinite(resid)
    if mask.any():
        rvals = resid[mask]
        base["residual_kt_median"] = round(float(np.median(rvals)), 1)
        base["residual_kt_max"] = round(float(rvals.max()), 1)
        minutes = (t[:-1][mask] - t[0]) / 60.0
        if rvals.size >= 2 and np.ptp(minutes) > 0:
            slope = float(np.polyfit(minutes, rvals, 1)[0])
            base["residual_slope_kt_per_min"] = round(slope, 2)

    alt = _num(d, "baroaltitude")
    vr = _num(d, "vertrate")
    with np.errstate(divide="ignore", invalid="ignore"):
        obs = np.where(pos, np.diff(alt) / dt, np.nan)
    mism = np.abs(obs - (vr[:-1] + vr[1:]) / 2.0)
    mism = mism[np.isfinite(mism)]
    if mism.size:
        base["vertrate_vs_altitude_mismatch_ms_median"] = round(float(np.median(mism)), 2)
    return base


def identity(df: pd.DataFrame) -> dict:
    """ARCHITECTURE §3.4 fields: identity changes and duplicate positions."""
    if df is None or len(df) == 0:
        return {"callsign_changes": 0, "squawk_changes": 0,
                "duplicate_position_pairs": 0, "n_points": 0}
    d = df.sort_values("time", kind="mergesort").reset_index(drop=True)

    def _changes(col: str) -> int:
        if col not in d:
            return 0
        s = d[col].astype("string").str.strip()
        s = s[s.notna() & (s != "")]
        v = s.to_numpy()
        return int((v[1:] != v[:-1]).sum()) if v.size > 1 else 0

    t = _num(d, "time")
    lat, lon = _num(d, "lat"), _num(d, "lon")
    n = len(d)
    dup = 0
    i = 0
    while i < n:
        j = i + 1
        while j < n and (t[j] - t[i]) <= _DUP_TIME_TOL_S:
            km = _haversine_m(np.array([lat[i]]), np.array([lon[i]]),
                              np.array([lat[j]]), np.array([lon[j]]))[0] / 1000.0
            if km > _DUP_DIST_KM:
                dup += 1
            j += 1
        i += 1
    return {"callsign_changes": _changes("callsign"), "squawk_changes": _changes("squawk"),
            "duplicate_position_pairs": int(dup), "n_points": int(n)}


def _feature_value(df: pd.DataFrame, feature: str) -> float:
    if feature == "max_gap_s":
        return float(window_summary(df)["max_gap_s"])
    return float(kinematics(df).get(feature, 0.0))


# --- track provider --------------------------------------------------------

@dataclass
class TrackProvider:
    """Resolves tracks for the tools. Scenario view first, then the real store."""

    con: duckdb.DuckDBPyConnection | None = None   # real store (view 'states')
    scenario_tracks: pd.DataFrame | None = None     # tracks.parquet (all scenarios)
    exclude_icao24: set[str] = field(default_factory=set)

    def track(self, icao24: str, t_start: int, t_end: int) -> pd.DataFrame:
        if self.scenario_tracks is not None:
            st = self.scenario_tracks
            sel = st[(st["icao24"].astype("string") == str(icao24))
                     & (st["time"] >= int(t_start)) & (st["time"] <= int(t_end))]
            if len(sel):
                return sel.sort_values("time", kind="mergesort").reset_index(drop=True)
        if self.con is None:
            return pd.DataFrame(columns=list(_TRACK_COLS))
        hours = sorted({hour_of(t_start), hour_of(t_end)})
        hrs = ",".join(str(h) for h in hours)
        df = self.con.execute(
            f"SELECT {', '.join(_TRACK_COLS)} FROM states "
            f"WHERE icao24 = ? AND hour IN ({hrs}) AND time BETWEEN ? AND ? "
            "AND onground = false AND lat IS NOT NULL AND lon IS NOT NULL ORDER BY time",
            [str(icao24), int(t_start), int(t_end)],
        ).df()
        df["time"] = df["time"].astype("int64")
        return df

    def baseline_windows(self, hour: int):
        """Yield real aircraft windows in the hour, deterministic, scenario-free."""
        if self.con is None:
            return
        cand = self.con.execute(
            """
            SELECT icao24, count(*) AS c FROM states
            WHERE hour = ? AND onground = false
              AND lat IS NOT NULL AND lon IS NOT NULL AND velocity IS NOT NULL
            GROUP BY icao24 HAVING count(*) >= ? ORDER BY icao24
            """,
            [int(hour), _BASELINE_MIN_POINTS],
        ).df()
        cand = cand[~cand["icao24"].isin(self.exclude_icao24)]
        for ic in cand["icao24"].head(_BASELINE_MAX_AIRCRAFT).tolist():
            df = self.con.execute(
                f"SELECT {', '.join(_TRACK_COLS)} FROM states "
                "WHERE icao24 = ? AND hour = ? AND onground = false "
                "AND lat IS NOT NULL AND lon IS NOT NULL ORDER BY time",
                [str(ic), int(hour)],
            ).df()
            df["time"] = df["time"].astype("int64")
            yield df


# --- the four tools (return (output, ref_id)) ------------------------------

def get_track_window(provider: TrackProvider, alert_id: str, *, icao24: str,
                     t_start: int, t_end: int) -> tuple[dict, str]:
    df = provider.track(icao24, t_start, t_end)
    return window_summary(df), ref_window(alert_id, int(t_start), int(t_end))


def compute_kinematics(provider: TrackProvider, alert_id: str, *, icao24: str,
                       t_start: int, t_end: int) -> tuple[dict, str]:
    args = {"icao24": icao24, "t_start": int(t_start), "t_end": int(t_end)}
    df = provider.track(icao24, t_start, t_end)
    return kinematics(df), ref_calc(alert_id, "kin", args)


def check_identity(provider: TrackProvider, alert_id: str, *, icao24: str,
                   t_start: int, t_end: int) -> tuple[dict, str]:
    args = {"icao24": icao24, "t_start": int(t_start), "t_end": int(t_end)}
    df = provider.track(icao24, t_start, t_end)
    return identity(df), ref_calc(alert_id, "id", args)


def compare_to_baseline(provider: TrackProvider, alert_id: str, *, alert_icao24: str,
                        alert_t_start: int, alert_t_end: int,
                        feature: str, context: str = "all") -> tuple[dict, str]:
    if feature not in BASELINE_FEATURES:
        raise ValueError(f"unknown baseline feature: {feature}")
    args = {"feature": feature, "context": context}
    value = _feature_value(provider.track(alert_icao24, alert_t_start, alert_t_end), feature)
    hour = hour_of(alert_t_start)
    vals = np.array([_feature_value(w, feature) for w in provider.baseline_windows(hour)],
                    dtype="float64")
    if vals.size:
        med = float(np.median(vals))
        p95 = float(np.quantile(vals, 0.95))
        spread = float(np.median(np.abs(vals - med))) * 1.4826
        z = (value - med) / spread if spread > 1e-9 else (0.0 if abs(value - med) < 1e-9 else None)
    else:
        med = p95 = z = None
    out = {
        "feature": feature, "value": round(value, 3),
        "baseline_median": None if med is None else round(med, 3),
        "baseline_p95": None if p95 is None else round(p95, 3),
        "z": None if z is None else round(z, 2),
        "n_baseline": int(vals.size),
    }
    return out, ref_calc(alert_id, "base", args)
