"""M3: assemble the 50 labelled scenarios, assign splits, write outputs.

Deterministic from `global_seed`. Each scenario draws its source only from its
split group's hours (hour-based split, D-029). Outputs:
  data/scenarios/tracks.parquet   state columns + scenario_id (NO label)
  data/scenarios/splits.json      ground-truth catalog (labels, params) — eval only
  data/scenarios/benign_plots/    one PNG per benign candidate for the eye-check
The label never enters tracks.parquet, so the scenario-aware view the tools use
cannot leak it. alert_map.json (alert_id -> scenario_id) is produced in M4.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from common.config import REPO_ROOT, get_settings, load_yaml
from common.logging import get_logger
from scenarios import benign, inject
from scenarios.select import ALL_COLUMNS, connect, hour_groups, pick_source

log = get_logger("scenarios.split")

LABELS = ["position_spoofing", "ghost_aircraft", "replay_duplicate", "sensor_fault",
          "benign_anomaly"]
SPLIT_SLOTS = ["kb", "kb", "dev", "dev", "dev", "test", "test", "test", "test", "test"]
DIFFICULTY_SLOTS = ["easy", "medium", "hard", "easy", "medium", "hard", "easy", "medium",
                    "hard", "hard"]
POS_MODES = ["drift", "jump", "velocity_offset", "drift", "jump", "velocity_offset",
             "drift", "jump", "drift", "velocity_offset"]
REPLAY_MODES = ["window_copy", "address_duplicate"] * 5


def _coerce(df: pd.DataFrame) -> pd.DataFrame:
    df = df[ALL_COLUMNS].copy()
    df["time"] = df["time"].astype("int64")
    for c in ["lat", "lon", "velocity", "heading", "vertrate",
              "baroaltitude", "geoaltitude", "lastposupdate", "lastcontact"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")
    for c in ["icao24", "callsign", "squawk"]:
        df[c] = df[c].astype("string")
    for c in ["onground", "alert", "spi"]:
        df[c] = df[c].astype("boolean")
    return df


def _record(scenario_id, label, split, difficulty, df, params, ref) -> dict:
    return {
        "scenario_id": scenario_id, "label": label, "split": split,
        "difficulty": difficulty, "icao24": str(df["icao24"].iloc[0]),
        "t_start": int(df["time"].min()), "t_end": int(df["time"].max()),
        "n_points": int(len(df)), "params": params, "source_track_ref": ref,
    }


def build(seed_base: int | None = None, out_dir: Path | None = None) -> dict:
    cfg = load_yaml("scenarios")
    gseed = int(seed_base if seed_base is not None else cfg["global_seed"])
    inj = cfg["injectors"]
    groups = hour_groups()
    con = connect()
    existing = {r[0] for r in con.execute("SELECT DISTINCT icao24 FROM states").fetchall()}

    data_dir = (REPO_ROOT / get_settings().data_dir).resolve()
    out_dir = out_dir or (data_dir / "scenarios")
    plots_dir = out_dir / "benign_plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    used: set[str] = set()
    records: list[dict] = []
    frames: list[pd.DataFrame] = []
    idx = 0

    def add(label, split, difficulty, df, params, ref):
        nonlocal idx
        idx += 1
        sid = f"S{idx:04d}"
        df = _coerce(df)
        df.insert(0, "scenario_id", sid)
        frames.append(df)
        records.append(_record(sid, label, split, difficulty, df, params, ref))

    # --- four synthetic labels ---
    for label in LABELS[:4]:
        for slot in range(10):
            split, diff = SPLIT_SLOTS[slot], DIFFICULTY_SLOTS[slot]
            rng = np.random.default_rng([gseed, idx + 1])
            hrs = groups[split]
            if label == "position_spoofing":
                src = pick_source(con, hrs, rng, min_points=48, duration_s=600, used=used)
                df, params = inject.position_spoofing(src.df, rng, inj[label], diff,
                                                       POS_MODES[slot])
                df["icao24"] = src.icao24
                add(label, split, diff, df, params, src.ref)
            elif label == "ghost_aircraft":
                src = pick_source(con, hrs, rng, min_points=12, duration_s=120, used=used)
                new = inject.synth_icao24(rng, lambda c: c in existing)
                existing.add(new)
                df, params = inject.ghost_aircraft(src.df, rng, inj[label], diff, new)
                add(label, split, diff, df, params, src.ref)
            elif label == "replay_duplicate":
                src = pick_source(con, hrs, rng, min_points=48, duration_s=600, used=used)
                if REPLAY_MODES[slot] == "window_copy":
                    df, params = inject.replay_window_copy(src.df, rng, inj[label], diff)
                else:
                    df, params = inject.replay_address_duplicate(src.df, rng, inj[label], diff)
                df["icao24"] = src.icao24
                add(label, split, diff, df, params, src.ref)
            elif label == "sensor_fault":
                src = pick_source(con, hrs, rng, min_points=48, duration_s=600, used=used)
                df, params = inject.sensor_fault(src.df, rng, inj[label], diff)
                df["icao24"] = src.icao24
                add(label, split, diff, df, params, src.ref)

    # --- benign_anomaly (real, rule-found, provisional until eye-checked) ---
    need = {"kb": 2, "dev": 3, "test": 5}
    benign_found = 0
    for split, count in need.items():
        cands = benign.find_holdings(con, groups[split], need=count, scan_cap=1500)
        if len(cands) < count:
            log.warning("benign %s: found %d of %d requested", split, len(cands), count)
        # The sharpest-turn candidate in the test split is marked as the confounder.
        for ci, c in enumerate(cands[:count]):
            benign_found += 1
            confounder = (split == "test" and ci == int(np.argmax(
                [x.metrics["turn_deg"] for x in cands[:count]])))
            params = {"kind": c.kind, "provisional_eye_check": True,
                      "confounder": bool(confounder), **c.metrics}
            benign.plot_candidate(c, plots_dir / f"{split}_{c.icao24}_{c.hour}.png")
            add("benign_anomaly", split, "medium", c.df, params, c.ref)

    tracks = pd.concat(frames, ignore_index=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    tracks.to_parquet(out_dir / "tracks.parquet", engine="pyarrow", index=False)

    catalog = {
        "global_seed": gseed,
        "method": "by_hour",
        "hour_groups": groups,
        "counts": {"total": len(records), "benign_found": benign_found},
        "scenarios": records,
    }
    (out_dir / "splits.json").write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    log.info("built %d scenarios (%d benign) -> %s", len(records), benign_found, out_dir)
    return catalog


def main() -> None:
    build()


if __name__ == "__main__":
    main()
