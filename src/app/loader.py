"""Data loading for the M9 Streamlit app — pure, Streamlit-free, unit-testable.

Everything the app shows is read from `results/<run>/` (eval runs, committed for
the final run) or `runs/` (live investigation traces). No numbers are computed
here beyond trivial reshaping; metrics come from the committed `metrics.json`
(AGENTS non-negotiable #3). The functions never read a model or a label source,
so what reaches the UI carries no scenario id, split or label.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import pandas as pd

from common.config import REPO_ROOT

CONFIG_LABELS = {"A": "A — single agent", "D": "D — full pipeline"}

LABEL_BLURB = {
    "position_spoofing": "Reported positions drift away from where the aircraft's "
                         "reported velocity says it should be — the GPS/position is spoofed.",
    "ghost_aircraft": "A fabricated track with no genuine history and no identity "
                      "(no callsign or squawk).",
    "replay_duplicate": "An earlier window of a real track is re-broadcast, so the same "
                        "path repeats or one address appears in two places at once.",
    "sensor_fault": "Receiver noise: dropouts, repeated values or timestamp jitter.",
    "benign_anomaly": "A real, harmless manoeuvre such as a holding pattern or go-around.",
}


def scenario_tracks(data_dir: Path | None = None) -> pd.DataFrame:
    """All injected scenario tracks (data/scenarios/tracks.parquet), or empty."""
    root = data_dir or (REPO_ROOT / "data" / "scenarios")
    path = root / "tracks.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def scenarios_by_label(data_dir: Path | None = None) -> dict[str, list[dict]]:
    """Scenario metadata (from splits.json) grouped by label, for the gallery."""
    root = data_dir or (REPO_ROOT / "data" / "scenarios")
    path = root / "splits.json"
    if not path.exists():
        return {}
    out: dict[str, list[dict]] = {}
    for s in json.loads(path.read_text(encoding="utf-8")).get("scenarios", []):
        out.setdefault(s["label"], []).append(s)
    return out


def track_window(df: pd.DataFrame, icao24: str, t_start: int, t_end: int) -> pd.DataFrame:
    """Rows for one aircraft inside [t_start, t_end], time-sorted (for an alert)."""
    if df.empty:
        return df
    m = (df["icao24"] == icao24) & (df["time"] >= t_start) & (df["time"] <= t_end)
    return df[m].sort_values("time").reset_index(drop=True)


def track_by_scenario(df: pd.DataFrame, scenario_id: str) -> pd.DataFrame:
    if df.empty or "scenario_id" not in df.columns:
        return pd.DataFrame()
    return df[df["scenario_id"] == scenario_id].sort_values("time").reset_index(drop=True)


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def implied_speed_kt(df: pd.DataFrame) -> list[float | None]:
    """Position-implied ground speed (knots) between consecutive reports.

    This is the quantity that diverges from the reported velocity under position
    spoofing — the 'drift' the app makes visible. First point has no prior, so None.
    """
    if df.empty:
        return []
    out: list[float | None] = [None]
    lat, lon, t = df["lat"].tolist(), df["lon"].tolist(), df["time"].tolist()
    for i in range(1, len(df)):
        dt = t[i] - t[i - 1]
        if dt <= 0:
            out.append(None)
            continue
        m = _haversine_m(lat[i - 1], lon[i - 1], lat[i], lon[i])
        out.append((m / dt) * 1.943_844)  # m/s -> knots
    return out


def _results_dir(results_dir: Path | None = None) -> Path:
    return results_dir or (REPO_ROOT / "results")


def eval_runs(results_dir: Path | None = None) -> list[Path]:
    """Eval-run directories (those with a cases/ folder), newest first."""
    root = _results_dir(results_dir)
    if not root.exists():
        return []
    runs = [p for p in root.iterdir() if p.is_dir() and (p / "cases").exists()]
    return sorted(runs, key=lambda p: p.stat().st_mtime, reverse=True)


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_cases(run_dir: Path) -> dict[str, list[dict]]:
    """Case records grouped by config, each list sorted by alert_id."""
    by_config: dict[str, list[dict]] = {}
    for path in sorted((run_dir / "cases").glob("*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        by_config.setdefault(rec["config"], []).append(rec)
    for cases in by_config.values():
        cases.sort(key=lambda c: c["alert_id"])
    return by_config


def load_metrics(run_dir: Path) -> dict:
    return _read_json(run_dir / "metrics.json") or {}


def load_missed(run_dir: Path) -> dict | None:
    return _read_json(run_dir / "missed.json")


def load_run_config(run_dir: Path) -> dict:
    return _read_json(run_dir / "config.json") or {}


def detector_metrics() -> dict | None:
    """The committed detector metrics (per-class recall etc.), or None."""
    return _read_json(REPO_ROOT / "results" / "detector" / "metrics.json")


def models_used(config_dir: Path | None = None) -> dict:
    """The Llama models in use, read from config/models.yaml (for the Meta badge)."""
    import yaml
    root = config_dir or (REPO_ROOT / "config")
    path = root / "models.yaml"
    if not path.exists():
        return {}
    cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    primary = (cfg.get("primary") or {}).get("model")
    triage = (cfg.get("triage") or {}).get("model") or primary
    return {"primary": primary, "triage": triage,
            "backend": (cfg.get("primary") or {}).get("backend", "ollama")}


def headline_run(results_dir: Path | None = None) -> Path | None:
    """The run to headline on the overview: test_final if present, else newest."""
    root = _results_dir(results_dir)
    final = root / "test_final"
    if final.exists() and (final / "metrics.json").exists():
        return final
    runs = eval_runs(results_dir)
    return runs[0] if runs else None


def summary_rows(run_dir: Path) -> list[dict]:
    path = run_dir / "summary.csv"
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def figures(run_dir: Path) -> list[Path]:
    fdir = run_dir / "figures"
    return sorted(fdir.glob("*.png")) if fdir.exists() else []


def load_trace(run_dir: Path, config: str, alert_id: str) -> dict | None:
    return load_trace_file(run_dir / "traces" / f"{config}__{alert_id}" / "trace.json")


def live_runs(runs_dir: Path | None = None) -> list[Path]:
    """Live investigation run directories under runs/ (those with a trace.json)."""
    root = runs_dir or (REPO_ROOT / "runs")
    if not root.exists():
        return []
    dirs = [p for p in root.iterdir() if p.is_dir() and (p / "trace.json").exists()]
    return sorted(dirs, key=lambda p: p.stat().st_mtime, reverse=True)


def load_trace_file(path: Path) -> dict | None:
    return _read_json(path)


def stage_steps(trace: dict) -> list[dict]:
    """Normalise a trace into ordered replay steps with per-stage seconds.

    Each step: {kind, title, seconds, body} where body is a small dict the UI
    renders. Order: triage, one step per subagent, verification, adjudication.
    """
    timing = trace.get("timing_s", {}) or {}
    steps: list[dict] = []

    triage = trace.get("triage") or {}
    kept = triage.get("kept", [])
    steps.append({
        "kind": "triage", "title": "Triage — ranked hypotheses",
        "seconds": timing.get("triage"),
        "body": {"kept": kept, "fallback": triage.get("fallback")},
    })

    verif = {v.get("hypothesis"): v for v in trace.get("verification", [])}
    for sa in trace.get("subagents", []):
        hyp = sa.get("hypothesis")
        steps.append({
            "kind": "subagent", "title": f"Subagent — {hyp}",
            "seconds": timing.get(f"subagent:{hyp}"),
            "body": {
                "hypothesis": hyp, "verdict": sa.get("verdict"),
                "confidence": sa.get("confidence"),
                "evidence": sa.get("evidence", []),
                "inference": sa.get("inference", ""),
                "tool_calls_used": sa.get("tool_calls_used"),
                "verification": verif.get(hyp),
            },
        })

    steps.append({
        "kind": "verification", "title": "Verification (pure Python)",
        "seconds": timing.get("verification"),
        "body": {"per_hypothesis": trace.get("verification", [])},
    })

    report = trace.get("report") or {}
    steps.append({
        "kind": "adjudication", "title": "Adjudication — incident report",
        "seconds": timing.get("adjudication"),
        "body": report,
    })
    return steps


def toollog_output(trace: dict, ref_id: str) -> dict | None:
    entry = (trace.get("toollog") or {}).get(ref_id)
    return entry.get("output") if entry else None
