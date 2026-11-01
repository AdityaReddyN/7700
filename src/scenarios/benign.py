"""M3: find benign_anomaly examples (holding patterns, go-arounds) in real data.

These are NOT injected: they are real, harmless manoeuvres found by rule, then
checked by eye (SCENARIO_SPEC §5). This module finds candidates and writes a
plot per candidate for the human to confirm; accepted ones become scenarios.
If fewer than needed are found, the caller reduces the count and reports it —
no padding with unchecked examples.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from scenarios.select import _fetch  # noqa: E402

_KM_PER_DEG_LAT = 110.574
_NM_KM = 1.852
_HOLD_WINDOW_S = 360
_HOLD_TURN_DEG = 360.0
_HOLD_RADIUS_NM = 5.0


@dataclass
class BenignCandidate:
    icao24: str
    hour: int
    kind: str  # "holding" | "go_around"
    t_start: int
    t_end: int
    df: pd.DataFrame
    metrics: dict

    @property
    def ref(self) -> str:
        return f"{self.icao24}:{self.hour}:{self.t_start}-{self.t_end}"


def _wrap180(d: float) -> float:
    return (d + 180.0) % 360.0 - 180.0


def _radius_nm(lat: np.ndarray, lon: np.ndarray) -> float:
    lat0 = float(lat.mean())
    x = (lon - lon.mean()) * 111.320 * math.cos(math.radians(lat0))
    y = (lat - lat.mean()) * _KM_PER_DEG_LAT
    return float(np.sqrt(x * x + y * y).max() / _NM_KM)


def _holding_window(df: pd.DataFrame) -> dict | None:
    """Return metrics for the first ~6 min window that turns >=360 deg in a small radius."""
    t = df["time"].to_numpy()
    hdg = df["heading"].to_numpy()
    lat = df["lat"].to_numpy()
    lon = df["lon"].to_numpy()
    n = len(df)
    for i in range(n):
        j = i
        turn = 0.0
        while j + 1 < n and (t[j + 1] - t[i]) <= _HOLD_WINDOW_S:
            if t[j + 1] - t[j] <= 20:
                turn += abs(_wrap180(hdg[j + 1] - hdg[j]))
            j += 1
            if turn >= _HOLD_TURN_DEG:
                rad = _radius_nm(lat[i : j + 1], lon[i : j + 1])
                if rad <= _HOLD_RADIUS_NM:
                    return {"turn_deg": round(turn, 1), "radius_nm": round(rad, 2),
                            "i": i, "j": j}
                break
    return None


def _candidate_aircraft(con, hours: list[int], min_points: int) -> list[tuple[str, int]]:
    hrs = ",".join(str(h) for h in hours)
    rows = con.execute(
        f"""
        SELECT icao24, hour, count(*) c FROM states
        WHERE hour IN ({hrs}) AND onground = false
          AND lat IS NOT NULL AND heading IS NOT NULL
        GROUP BY icao24, hour HAVING count(*) >= {min_points}
        ORDER BY c DESC, icao24, hour
        """
    ).fetchall()
    return [(str(r[0]), int(r[1])) for r in rows]


def find_holdings(con, hours: list[int], need: int, scan_cap: int = 2000) -> list[BenignCandidate]:
    found: list[BenignCandidate] = []
    for icao24, hour in _candidate_aircraft(con, hours, min_points=36)[:scan_cap]:
        df = _fetch(con, icao24, hour)
        if len(df) < 36:
            continue
        m = _holding_window(df)
        if m:
            seg = df.iloc[m["i"] : m["j"] + 1].reset_index(drop=True)
            found.append(BenignCandidate(
                icao24, hour, "holding",
                int(seg["time"].iloc[0]), int(seg["time"].iloc[-1]), seg, m,
            ))
            if len(found) >= need:
                break
    return found


def plot_candidate(cand: BenignCandidate, out_path) -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 4))
    ax1.plot(cand.df["lon"], cand.df["lat"], "-o", ms=2)
    ax1.set_title(f"{cand.kind} {cand.icao24} h{cand.hour}")
    ax1.set_xlabel("lon")
    ax1.set_ylabel("lat")
    ax1.axis("equal")
    ax2.plot((cand.df["time"] - cand.df["time"].iloc[0]), cand.df["heading"], "-o", ms=2)
    ax2.set_title(f"turn={cand.metrics.get('turn_deg')}deg r={cand.metrics.get('radius_nm')}nm")
    ax2.set_xlabel("t (s)")
    ax2.set_ylabel("heading")
    fig.tight_layout()
    fig.savefig(out_path, dpi=90)
    plt.close(fig)
