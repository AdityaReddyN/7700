"""M3: fresh injectors for the four synthetic labels.

Written from scratch for this event (D-009). Each injector takes a real source
segment (from select.py) and returns the modified track plus a `params` dict for
reproducibility. All randomness comes from a seeded numpy Generator, so output
is deterministic. Difficulty scales the signal: easy = strong, hard = subtle
(near thresholds). Positions are degrees; offsets convert km->deg locally.
"""

from __future__ import annotations

import math
from collections.abc import Callable

import numpy as np
import pandas as pd

_KM_PER_DEG_LAT = 110.574
_KT_TO_MS = 0.514444


def _km_per_deg_lon(lat: float) -> float:
    return 111.320 * math.cos(math.radians(lat))


def _offset_deg(lat: float, dx_km_e: float, dy_km_n: float) -> tuple[float, float]:
    dlat = dy_km_n / _KM_PER_DEG_LAT
    dlon = dx_km_e / max(_km_per_deg_lon(lat), 1e-6)
    return dlat, dlon


def _mag(rng: np.random.Generator, lo: float, hi: float, difficulty: str) -> float:
    """Sample a magnitude; hard = near the low (subtle) end, easy = high (obvious)."""
    if difficulty == "easy":
        return float(rng.uniform(lo + 0.6 * (hi - lo), hi))
    if difficulty == "hard":
        return float(rng.uniform(lo, lo + 0.34 * (hi - lo)))
    return float(rng.uniform(lo, hi))


def _bearing_components(rng: np.random.Generator) -> tuple[float, float]:
    theta = float(rng.uniform(0, 2 * math.pi))
    return math.cos(theta), math.sin(theta)  # (east, north) unit components


# --- position_spoofing -----------------------------------------------------

def position_spoofing(
    df: pd.DataFrame, rng: np.random.Generator, cfg: dict, difficulty: str, mode: str
) -> tuple[pd.DataFrame, dict]:
    out = df.copy().reset_index(drop=True)
    t = out["time"].to_numpy()
    e, n = _bearing_components(rng)
    params: dict = {"mode": mode, "difficulty": difficulty}

    if mode == "drift":
        rate = _mag(rng, *cfg["drift_rate_km_per_min"], difficulty)  # km/min
        elapsed_min = (t - t[0]) / 60.0
        off_km = rate * elapsed_min
        params["drift_rate_km_per_min"] = rate
    elif mode == "jump":
        offset = _mag(rng, *cfg["jump_offset_km"], difficulty)  # km
        start = len(out) // 2
        off_km = np.where(np.arange(len(out)) >= start, offset, 0.0)
        params.update({"jump_offset_km": offset, "jump_start_index": int(start)})
    elif mode == "velocity_offset":
        lo, hi = cfg["velocity_scale"]
        # hard = scale near 1.0 (subtle); easy = far from 1.0.
        spread = {"easy": (0.6, 1.0), "medium": (0.3, 1.0), "hard": (0.05, 0.34)}[difficulty]
        frac = float(rng.uniform(*spread))
        scale = 1.0 + frac * ((hi - 1.0) if rng.random() < 0.5 else (lo - 1.0))
        out["velocity"] = out["velocity"] * scale
        params["velocity_scale"] = scale
        return out, params
    else:
        raise ValueError(f"unknown position_spoofing mode {mode}")

    lat0 = float(out["lat"].iloc[0])
    dlat, dlon = _offset_deg(lat0, e, n)  # unit per km
    out["lat"] = out["lat"] + dlat * off_km
    out["lon"] = out["lon"] + dlon * off_km
    params["bearing_en"] = [round(e, 3), round(n, 3)]
    return out, params


# --- ghost_aircraft --------------------------------------------------------

def ghost_aircraft(
    template: pd.DataFrame, rng: np.random.Generator, cfg: dict, difficulty: str,
    new_icao24: str,
) -> tuple[pd.DataFrame, dict]:
    row0 = template.iloc[0]
    t0 = int(row0["time"])
    duration_min = int(_mag(rng, *cfg["duration_min"], "medium"))
    n = max(6, duration_min * 6)  # 10 s cadence
    cruise_kt = float(rng.uniform(*cfg["cruise_kt"]))
    speed_ms = cruise_kt * _KT_TO_MS
    heading = float(row0["heading"]) if pd.notna(row0["heading"]) else float(rng.uniform(0, 360))
    # hard = noisier (looks more real); easy = pristine (obvious ghost).
    noise_m = _mag(rng, *cfg["position_noise_m"], "easy" if difficulty == "hard" else "hard")

    lat = float(row0["lat"])
    lon = float(row0["lon"])
    e = math.sin(math.radians(heading))
    nth = math.cos(math.radians(heading))
    step_km = speed_ms * 10 / 1000.0
    dlat, dlon = _offset_deg(lat, e, nth)

    times, lats, lons = [], [], []
    for i in range(n):
        jlat = float(rng.normal(0, noise_m / 1000.0 / _KM_PER_DEG_LAT))
        jlon = float(rng.normal(0, noise_m / 1000.0 / max(_km_per_deg_lon(lat), 1e-6)))
        times.append(t0 + i * 10)
        lats.append(lat + dlat * step_km * i + jlat)
        lons.append(lon + dlon * step_km * i + jlon)

    alt = float(row0["baroaltitude"]) if pd.notna(row0["baroaltitude"]) else 10000.0
    out = pd.DataFrame(
        {
            "time": np.array(times, dtype="int64"),
            "icao24": new_icao24,
            "lat": lats,
            "lon": lons,
            "velocity": speed_ms,
            "heading": heading,
            "vertrate": 0.0,
            "callsign": pd.NA,
            "onground": False,
            "alert": False,
            "spi": False,
            "squawk": pd.NA,
            "baroaltitude": alt,
            "geoaltitude": alt,
            "lastposupdate": [float(x) for x in times],
            "lastcontact": [float(x) for x in times],
        }
    )
    params = {
        "cruise_kt": round(cruise_kt, 1), "duration_min": duration_min,
        "position_noise_m": round(noise_m, 1), "heading": round(heading, 1),
        "difficulty": difficulty, "new_icao24": new_icao24,
    }
    return out, params


# --- replay_duplicate ------------------------------------------------------

def replay_window_copy(
    df: pd.DataFrame, rng: np.random.Generator, cfg: dict, difficulty: str,
) -> tuple[pd.DataFrame, dict]:
    """Re-emit an earlier sub-window of this aircraft, shifted later in time."""
    out = df.copy().reset_index(drop=True)
    win_min = int(_mag(rng, *cfg["window_min"], "medium"))
    win_pts = max(6, min(win_min * 6, len(out)))
    offset_min = _mag(rng, *cfg["window_copy_offset_min"], difficulty)
    offset_s = int(offset_min * 60)
    src = out.iloc[:win_pts].copy()
    copy = src.copy()
    copy["time"] = copy["time"] + offset_s
    # altitude-shifted replay is the hard variant.
    if difficulty == "hard":
        shift = float(rng.uniform(200, 600))
        copy["baroaltitude"] = copy["baroaltitude"] + shift
        copy["geoaltitude"] = copy["geoaltitude"] + shift
    merged = pd.concat([out, copy], ignore_index=True).sort_values("time", kind="mergesort")
    params = {
        "mode": "window_copy", "window_min": win_min,
        "window_copy_offset_min": round(offset_min, 1),
        "source_window": [int(src["time"].iloc[0]), int(src["time"].iloc[-1])],
        "difficulty": difficulty,
    }
    return merged.reset_index(drop=True), params


def replay_address_duplicate(
    df: pd.DataFrame, rng: np.random.Generator, cfg: dict, difficulty: str,
) -> tuple[pd.DataFrame, dict]:
    """Same address at two distant positions at (nearly) the same times."""
    out = df.copy().reset_index(drop=True)
    dist_km = _mag(rng, *cfg["address_offset_km"], difficulty)
    e, n = _bearing_components(rng)
    lat0 = float(out["lat"].iloc[0])
    dlat, dlon = _offset_deg(lat0, e, n)
    dup = out.copy()
    dup["time"] = dup["time"] + int(rng.integers(1, 5))
    dup["lat"] = dup["lat"] + dlat * dist_km
    dup["lon"] = dup["lon"] + dlon * dist_km
    merged = pd.concat([out, dup], ignore_index=True).sort_values("time", kind="mergesort")
    params = {
        "mode": "address_duplicate", "address_offset_km": round(dist_km, 1),
        "difficulty": difficulty,
    }
    return merged.reset_index(drop=True), params


# --- sensor_fault ----------------------------------------------------------

def sensor_fault(
    df: pd.DataFrame, rng: np.random.Generator, cfg: dict, difficulty: str,
) -> tuple[pd.DataFrame, dict]:
    out = df.copy().reset_index(drop=True)
    modes = ["noise", "dropout", "stuck", "jitter"]
    k = int(rng.integers(1, 3))  # 1 or 2
    chosen = list(rng.choice(modes, size=k, replace=False))
    params: dict = {"modes": chosen, "difficulty": difficulty}

    if "noise" in chosen:
        sigma_m = _mag(rng, *cfg["noise_sigma_m"], difficulty)
        lat0 = float(out["lat"].iloc[0])
        out["lat"] = out["lat"] + rng.normal(0, sigma_m / 1000.0 / _KM_PER_DEG_LAT, len(out))
        out["lon"] = out["lon"] + rng.normal(
            0, sigma_m / 1000.0 / max(_km_per_deg_lon(lat0), 1e-6), len(out)
        )
        params["noise_sigma_m"] = round(sigma_m, 1)
    if "dropout" in chosen and len(out) > 12:
        frac = _mag(rng, *cfg["dropout_fraction"], difficulty)
        dur_s = int(_mag(rng, *cfg["dropout_duration_s"], "medium"))
        span = max(2, dur_s // 10)
        start = int(rng.integers(0, max(1, len(out) - span)))
        idx = np.arange(start, start + span)
        drop = rng.random(len(idx)) < frac
        out = out.drop(index=idx[drop]).reset_index(drop=True)
        params.update({"dropout_fraction": round(frac, 2), "dropout_duration_s": dur_s})
    if "stuck" in chosen and len(out) > 8:
        dur_s = int(_mag(rng, *cfg["stuck_duration_s"], "medium"))
        span = max(2, dur_s // 10)
        start = int(rng.integers(0, max(1, len(out) - span)))
        field = str(rng.choice(["baroaltitude", "lat", "velocity"]))
        out.loc[start : start + span - 1, field] = out.loc[start, field]
        params.update({"stuck_field": field, "stuck_duration_s": dur_s})
    if "jitter" in chosen:
        jit = int(_mag(rng, *cfg["timestamp_jitter_s"], difficulty))
        out["time"] = out["time"] + rng.integers(-jit, jit + 1, len(out))
        params["timestamp_jitter_s"] = jit

    out["time"] = out["time"].astype("int64")
    return out.reset_index(drop=True), params


IcaoChecker = Callable[[str], bool]


def synth_icao24(rng: np.random.Generator, exists: IcaoChecker) -> str:
    """A 6-hex address not present in the data (ghost_aircraft)."""
    for _ in range(100):
        cand = "".join(rng.choice(list("0123456789abcdef"), size=6))
        if not exists(cand):
            return cand
    raise RuntimeError("could not find an unused icao24")
