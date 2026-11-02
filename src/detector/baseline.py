"""M4: build the normal-traffic baseline for the detector.

Samples real aircraft windows from the configured baseline hours (the dev group,
disjoint from the test hours, so no test traffic is seen), excludes any icao24
used as a scenario source, computes the feature matrix, and records per-feature
median/MAD for z-scores. Sampling is seeded, so the baseline is reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass

import duckdb
import numpy as np
import pandas as pd

from detector.features import FEATURE_NAMES, compute_features, feature_vector, mad


@dataclass
class Baseline:
    matrix: np.ndarray          # (n_windows, n_features) real normal windows
    median: np.ndarray          # per-feature median
    mad: np.ndarray             # per-feature MAD
    feature_names: tuple[str, ...]
    n_windows: int
    hours: list[int]


def _contiguous_window(df: pd.DataFrame, duration_s: int) -> pd.DataFrame:
    """First contiguous run (dt <= 20 s) covering >= duration_s; else densest slice."""
    t = df["time"].to_numpy()
    n = len(t)
    best = (0, n)
    i = 0
    while i < n - 1:
        j = i
        while j + 1 < n and (t[j + 1] - t[j]) <= 20:
            if t[j + 1] - t[i] >= duration_s:
                return df.iloc[i : j + 2].copy()
            j += 1
        if j - i > best[1] - best[0]:
            best = (i, j + 1)
        i = j + 1
    s, e = best
    return df.iloc[s:e].copy()


def sample_windows(
    con: duckdb.DuckDBPyConnection,
    hours: list[int],
    *,
    n_tracks: int,
    window_s: int,
    min_points: int,
    seed: int,
    exclude_icao24: set[str],
) -> list[pd.DataFrame]:
    """Deterministically sample up to n_tracks airborne aircraft windows."""
    hrs = ",".join(str(h) for h in hours)
    cand = con.execute(
        f"""
        SELECT icao24, hour, count(*) AS c
        FROM states
        WHERE hour IN ({hrs}) AND onground = false
          AND lat IS NOT NULL AND lon IS NOT NULL
          AND velocity IS NOT NULL
        GROUP BY icao24, hour
        HAVING count(*) >= {min_points}
        ORDER BY icao24, hour
        """
    ).df()
    cand = cand[~cand["icao24"].isin(exclude_icao24)].reset_index(drop=True)
    if cand.empty:
        return []
    rng = np.random.default_rng(seed)
    take = min(n_tracks, len(cand))
    pick = rng.choice(len(cand), size=take, replace=False)
    windows: list[pd.DataFrame] = []
    cols = ("time, icao24, lat, lon, velocity, heading, vertrate, callsign, "
            "squawk, baroaltitude, geoaltitude")
    for k in sorted(pick.tolist()):
        row = cand.iloc[k]
        df = con.execute(
            f"SELECT {cols} FROM states "
            "WHERE icao24 = ? AND hour = ? AND onground = false "
            "AND lat IS NOT NULL AND lon IS NOT NULL AND velocity IS NOT NULL "
            "ORDER BY time",
            [str(row["icao24"]), int(row["hour"])],
        ).df()
        df["time"] = df["time"].astype("int64")
        seg = _contiguous_window(df, window_s)
        if len(seg) >= min_points:
            windows.append(seg.reset_index(drop=True))
    return windows


def features_matrix(windows: list[pd.DataFrame]) -> np.ndarray:
    if not windows:
        return np.empty((0, len(FEATURE_NAMES)), dtype="float64")
    return np.vstack([feature_vector(compute_features(w)) for w in windows])


def build_baseline(
    con: duckdb.DuckDBPyConnection, det_cfg: dict, exclude_icao24: set[str]
) -> Baseline:
    bcfg = det_cfg["baseline"]
    windows = sample_windows(
        con, list(bcfg["hours"]),
        n_tracks=int(bcfg["sample_tracks"]),
        window_s=int(bcfg["window_s"]),
        min_points=int(bcfg["min_points"]),
        seed=int(bcfg["seed"]),
        exclude_icao24=exclude_icao24,
    )
    matrix = features_matrix(windows)
    if matrix.shape[0] == 0:
        raise RuntimeError("baseline is empty; check the Parquet store and baseline hours")
    median = np.median(matrix, axis=0)
    mad_vec = np.array([mad(matrix[:, j]) for j in range(matrix.shape[1])])
    return Baseline(
        matrix=matrix, median=median, mad=mad_vec,
        feature_names=FEATURE_NAMES, n_windows=matrix.shape[0], hours=list(bcfg["hours"]),
    )
