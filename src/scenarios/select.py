"""M3: pick real source tracks from the Parquet store for scenario injection.

Read-only DuckDB over the M2 store. Selection is deterministic given a seeded
numpy Generator, so the whole scenario set regenerates identically. A scenario
only ever draws source tracks from the hours of its own split group (hour-based
split, D-029), which the leakage test relies on.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import duckdb
import numpy as np
import pandas as pd

from common.config import REPO_ROOT, get_settings, load_yaml

ALL_COLUMNS = [
    "time", "icao24", "lat", "lon", "velocity", "heading", "vertrate",
    "callsign", "onground", "alert", "spi", "squawk",
    "baroaltitude", "geoaltitude", "lastposupdate", "lastcontact",
]


def hour_groups() -> dict[str, list[int]]:
    cfg = load_yaml("scenarios")["day_split"]
    if cfg.get("method") != "by_hour":
        raise ValueError("expected by_hour split for the single available day (D-029)")
    return {k: list(v) for k, v in cfg["hour_groups"].items()}


def connect(parquet_dir: str | None = None) -> duckdb.DuckDBPyConnection:
    data_dir = (REPO_ROOT / get_settings().data_dir).resolve()
    pq = parquet_dir or str(data_dir / "parquet" / "states" / "**" / "*.parquet")
    pq = pq.replace("\\", "/")
    con = duckdb.connect()
    con.execute("PRAGMA threads=2")
    con.execute(
        f"CREATE VIEW states AS SELECT * FROM read_parquet('{pq}', hive_partitioning=1)"
    )
    return con


@dataclass
class SourceTrack:
    icao24: str
    hour: int
    df: pd.DataFrame  # good airborne points, sorted by time
    ref: str = field(default="")

    def __post_init__(self) -> None:
        if not self.ref:
            t0, t1 = int(self.df["time"].iloc[0]), int(self.df["time"].iloc[-1])
            self.ref = f"{self.icao24}:{self.hour}:{t0}-{t1}"

    @property
    def n_points(self) -> int:
        return len(self.df)


def _candidates(con: duckdb.DuckDBPyConnection, hours: list[int], min_points: int) -> pd.DataFrame:
    """(icao24, hour, c) for airborne aircraft with >= min_points good points in a single hour."""
    hrs = ",".join(str(h) for h in hours)
    return con.execute(
        f"""
        SELECT icao24, hour, count(*) AS c
        FROM states
        WHERE hour IN ({hrs}) AND onground = false
          AND lat IS NOT NULL AND lon IS NOT NULL
          AND velocity IS NOT NULL AND heading IS NOT NULL
        GROUP BY icao24, hour
        HAVING count(*) >= {min_points}
        ORDER BY c DESC, icao24, hour
        """
    ).df()


def _fetch(con: duckdb.DuckDBPyConnection, icao24: str, hour: int) -> pd.DataFrame:
    df = con.execute(
        f"SELECT {', '.join(ALL_COLUMNS)} FROM states "
        "WHERE icao24 = ? AND hour = ? AND onground = false "
        "AND lat IS NOT NULL AND lon IS NOT NULL "
        "AND velocity IS NOT NULL AND heading IS NOT NULL "
        "ORDER BY time",
        [icao24, hour],
    ).df()
    df["time"] = df["time"].astype("int64")
    return df


def pick_source(
    con: duckdb.DuckDBPyConnection,
    hours: list[int],
    rng: np.random.Generator,
    *,
    min_points: int,
    duration_s: int,
    used: set[str],
    pool: int = 300,
) -> SourceTrack:
    """Pick one source track with a contiguous ~10 s run of at least duration_s."""
    need = max(min_points, duration_s // 10 + 1)
    cand = _candidates(con, hours, need)
    cand = cand[~cand["icao24"].isin(used)]
    if cand.empty:
        raise RuntimeError(f"no candidate source tracks in hours {hours} with >= {need} points")
    top = cand.head(pool).reset_index(drop=True)
    idx = int(rng.integers(0, len(top)))
    row = top.iloc[idx]
    icao24, hour = str(row["icao24"]), int(row["hour"])
    df = _fetch(con, icao24, hour)
    seg = _contiguous_window(df, duration_s)
    used.add(icao24)
    return SourceTrack(icao24=icao24, hour=hour, df=seg.reset_index(drop=True))


def _contiguous_window(df: pd.DataFrame, duration_s: int) -> pd.DataFrame:
    """First contiguous run (dt <= 20 s) covering at least duration_s; else the densest slice."""
    t = df["time"].to_numpy()
    n = len(t)
    start = 0
    best = (0, n)  # fallback: whole track
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
    start, end = best
    return df.iloc[start:end].copy()
