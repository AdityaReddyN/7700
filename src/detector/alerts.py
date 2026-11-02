"""M4: run the detector over the scenarios and real traffic, write deliverables.

Primary detector is the Isolation Forest (D-030); set ``method: rules`` in
``config/detector.yaml`` to fall back to the rule-based flagger. The threshold is
tuned on the DEV split only and the TEST split is scored once with it.

Outputs:
  data/scenarios/alerts.json      Alert objects for flagged dev+test windows (no label)
  data/scenarios/alert_map.json   alert_id -> scenario_id (eval join, never shown to the model)
  results/detector/metrics.json   recall/precision/alert-rate, all with n
  results/detector/report.md      the same numbers, with small-sample caveats

Every number in the report comes from this run's files (AGENTS non-negotiable #3).
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from common.config import REPO_ROOT, get_settings, load_yaml
from common.ids import alert_id as make_alert_id
from common.logging import get_logger
from common.schemas import Alert
from detector.baseline import Baseline, build_baseline, features_matrix, sample_windows
from detector.features import FEATURE_NAMES, compute_features, feature_vector, robust_z
from detector.flagger import RuleFlagger
from detector.model import IsolationForestDetector
from scenarios.select import connect

log = get_logger("detector.alerts")

SYNTHETIC = ("position_spoofing", "ghost_aircraft", "replay_duplicate", "sensor_fault")

_SUMMARY_PHRASE = {
    "speed_resid_kt_med": "Position-implied speed disagrees with the reported speed",
    "speed_resid_kt_max": "Position-implied speed disagrees with the reported speed",
    "largest_jump_km": "A large position step appears between consecutive reports",
    "max_gap_s": "A stretch of expected position reports is missing",
    "missing_frac": "A stretch of expected position reports is missing",
    "dup_pairs": "The same address reports from distant positions within a few seconds",
    "scatter_m": "Position reports scatter more than a smooth track",
    "max_stuck_run": "The reported position holds unchanged across several reports",
    "time_irregularity": "Report timing is irregular",
    "vertrate_mismatch_ms": "Reported climb rate disagrees with the altitude change",
    "identity_missing": "The track carries no callsign or squawk",
    "vel_cv": "The reported speed is unusually constant",
}


def _top_features(vec: np.ndarray, baseline: Baseline, k: int = 3) -> list[dict]:
    zs = [
        (FEATURE_NAMES[j],
         robust_z(float(vec[j]), float(baseline.median[j]), float(baseline.mad[j])))
        for j in range(vec.size)
    ]
    zs.sort(key=lambda p: abs(p[1]), reverse=True)
    return [{"name": name, "z": round(z, 2)} for name, z in zs[:k]]


def _summary(top: list[dict]) -> str:
    if not top:
        return "Flagged as anomalous by the detector."
    phrase = _SUMMARY_PHRASE.get(top[0]["name"], "Unusual track behaviour")
    return f"{phrase} (z={top[0]['z']:.1f})."


def _build_detector(det_cfg: dict):
    method = det_cfg.get("method", "isolation_forest")
    if method == "rules":
        return RuleFlagger(det_cfg.get("rules", {}))
    return IsolationForestDetector(det_cfg.get("isolation_forest", {}))


def _tune_threshold(dev_rows: list[dict], target_recall: float) -> float:
    """Legacy policy: the threshold that reaches target recall on dev positives."""
    pos = sorted((r["score"] for r in dev_rows if r["is_positive"]), reverse=True)
    if not pos:
        return float("inf")
    k = max(1, math.ceil(target_recall * len(pos)))
    k = min(k, len(pos))
    return float(pos[k - 1])


def _threshold_from_budget(base_scores: np.ndarray, target_rate: float) -> float:
    """Operating point: flag the top ``target_rate`` fraction of normal traffic (D-031)."""
    if base_scores.size == 0:
        return float("inf")
    return float(np.quantile(base_scores, 1.0 - target_rate))


def _split_metrics(rows: list[dict], threshold: float) -> dict:
    by_class: dict[str, dict[str, int]] = {}
    tp = fp = pos_total = benign_total = 0
    for r in rows:
        flagged = r["score"] >= threshold
        lab = r["label"]
        by_class.setdefault(lab, {"total": 0, "flagged": 0})
        by_class[lab]["total"] += 1
        by_class[lab]["flagged"] += int(flagged)
        if lab in SYNTHETIC:
            pos_total += 1
            tp += int(flagged)
        elif lab == "benign_anomaly":
            benign_total += 1
            fp += int(flagged)
    recall = tp / pos_total if pos_total else None
    precision = tp / (tp + fp) if (tp + fp) else None
    benign_rate = fp / benign_total if benign_total else None
    return {
        "n_positive": pos_total, "n_benign": benign_total,
        "tp": tp, "fp": fp,
        "recall": recall, "precision": precision, "benign_flag_rate": benign_rate,
        "per_class": {
            lab: {
                "total": by_class.get(lab, {}).get("total", 0),
                "flagged": by_class.get(lab, {}).get("flagged", 0),
                "recall": (by_class[lab]["flagged"] / by_class[lab]["total"])
                if by_class.get(lab, {}).get("total") else None,
            }
            for lab in (*SYNTHETIC, "benign_anomaly")
        },
    }


def run_detector(
    out_data: Path | None = None,
    out_results: Path | None = None,
    method_override: str | None = None,
    write_alerts: bool = True,
) -> dict:
    det_cfg = load_yaml("detector")
    if method_override:
        det_cfg = {**det_cfg, "method": method_override}
    data_dir = (REPO_ROOT / get_settings().data_dir).resolve()
    scen_dir = out_data or (data_dir / "scenarios")
    results_dir = out_results or (REPO_ROOT / "results" / "detector")
    results_dir.mkdir(parents=True, exist_ok=True)

    catalog = json.loads((scen_dir / "splits.json").read_text(encoding="utf-8"))
    by_sid = {s["scenario_id"]: s for s in catalog["scenarios"]}
    tracks = pd.read_parquet(scen_dir / "tracks.parquet", engine="pyarrow")
    exclude = {str(s["icao24"]) for s in catalog["scenarios"]}

    con = connect()
    baseline = build_baseline(con, det_cfg, exclude)
    detector = _build_detector(det_cfg)
    detector.fit(baseline)
    log.info("baseline %d windows; detector=%s", baseline.n_windows, detector.method)

    # Score every scenario window.
    rows: list[dict] = []
    vectors: dict[str, np.ndarray] = {}
    for sid, g in tracks.groupby("scenario_id", sort=True):
        rec = by_sid[str(sid)]
        vec = feature_vector(compute_features(g))
        vectors[str(sid)] = vec
        rows.append({
            "scenario_id": str(sid), "split": rec["split"], "label": rec["label"],
            "icao24": str(rec["icao24"]), "t_start": int(rec["t_start"]),
            "t_end": int(rec["t_end"]), "score": detector.score(vec),
            "is_positive": rec["label"] in SYNTHETIC,
        })

    dev_rows = [r for r in rows if r["split"] == "dev"]
    thr_cfg = det_cfg.get("threshold", {})
    target_recall = float(thr_cfg.get("target_dev_recall", 0.8))
    target_rate = thr_cfg.get("target_alert_rate")
    base_scores = detector.score_many(baseline.matrix)
    if thr_cfg.get("value") is not None:
        threshold, policy = float(thr_cfg["value"]), "config"
    elif target_rate is not None:
        threshold = _threshold_from_budget(base_scores, float(target_rate))
        policy = "dev_fp_budget"
    else:
        threshold, policy = _tune_threshold(dev_rows, target_recall), "dev_recall"
    baseline_fp_rate = float(np.mean(base_scores >= threshold)) if base_scores.size else None

    # Build alerts for flagged dev+test windows (kb windows are for retrieval, not alerts).
    alerts: list[dict] = []
    alert_map: dict[str, str] = {}
    for r in rows:
        if r["split"] == "kb" or r["score"] < threshold:
            continue
        top = _top_features(vectors[r["scenario_id"]], baseline)
        aid = make_alert_id(r["icao24"], r["t_start"], r["t_end"])
        alert = Alert(
            alert_id=aid, icao24=r["icao24"], t_start=r["t_start"], t_end=r["t_end"],
            score=round(r["score"], 4), top_features=top, summary=_summary(top),
        )
        alerts.append(alert.model_dump())
        alert_map[aid] = r["scenario_id"]

    # Alert rate on real (uninjected) traffic from a disjoint hour sample.
    ars = det_cfg["alert_rate_sample"]
    real_windows = sample_windows(
        con, list(ars["hours"]), n_tracks=int(ars["tracks"]),
        window_s=int(det_cfg["baseline"]["window_s"]),
        min_points=int(det_cfg["baseline"]["min_points"]),
        seed=int(ars["seed"]), exclude_icao24=exclude,
    )
    real_scores = detector.score_many(features_matrix(real_windows))
    real_flagged = int(np.sum(real_scores >= threshold))
    real_rate = (real_flagged / len(real_scores)) if len(real_scores) else None

    metrics = {
        "method": detector.method,
        "threshold": threshold,
        "threshold_policy": policy,
        "target_alert_rate": target_rate,
        "baseline_fp_rate": baseline_fp_rate,
        "target_dev_recall": target_recall,
        "n_features": len(FEATURE_NAMES),
        "feature_names": list(FEATURE_NAMES),
        "baseline": {"n_windows": baseline.n_windows, "hours": baseline.hours},
        "dev": _split_metrics(dev_rows, threshold),
        "test": _split_metrics([r for r in rows if r["split"] == "test"], threshold),
        "real_alert_rate": {
            "hours": list(ars["hours"]), "n_sampled": len(real_scores),
            "n_flagged": real_flagged, "rate": real_rate,
        },
        "n_alerts": len(alerts),
        "per_scenario": [
            {k: r[k] for k in ("scenario_id", "split", "label", "score", "is_positive")}
            | {"flagged": r["score"] >= threshold}
            for r in rows
        ],
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
    }

    if write_alerts:
        (scen_dir / "alerts.json").write_text(json.dumps(alerts, indent=2), encoding="utf-8")
        (scen_dir / "alert_map.json").write_text(
            json.dumps(alert_map, indent=2), encoding="utf-8")
    (results_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    (results_dir / "report.md").write_text(_render_report(metrics), encoding="utf-8")
    log.info("wrote %d alerts; test recall=%s real alert rate=%s",
             len(alerts), metrics["test"]["recall"], real_rate)
    return metrics


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{100 * x:.0f}%"


def _render_report(m: dict) -> str:
    def class_table(split: str) -> str:
        s = m[split]
        lines = ["| class | flagged / total | recall |", "|---|---|---|"]
        for lab in (*SYNTHETIC, "benign_anomaly"):
            c = s["per_class"][lab]
            kind = "flag rate" if lab == "benign_anomaly" else "recall"
            lines.append(
                f"| {lab} | {c['flagged']} / {c['total']} | {_pct(c['recall'])} ({kind}) |")
        return "\n".join(lines)

    ra = m["real_alert_rate"]
    op = (f"a {_pct(m['target_alert_rate'])} false-positive budget on normal dev-hour "
          f"traffic (D-031)" if m["threshold_policy"] == "dev_fp_budget"
          else f"policy '{m['threshold_policy']}'")
    return f"""# Detector report (M4)

Method: **{m['method']}** (Isolation Forest is primary; rule-based flagger is the
fallback, D-030). Threshold {m['threshold']:.4f}, set by {op}; the achieved
false-positive rate on the baseline was {_pct(m['baseline_fp_rate'])}. The
**test** split was scored once with it. Recall is whatever this operating point
yields — the detector is deliberately simple and favours a believable alert rate
over catching every subtle injection.

Baseline: {m['baseline']['n_windows']} real airborne windows from hours
{m['baseline']['hours']} (dev-group hours, disjoint from the test hours — no test
traffic is seen). {m['n_features']} features per window.

**Small samples.** Each split has only a handful of scenarios per class
(dev: {m['dev']['n_positive']} injected + {m['dev']['n_benign']} benign;
test: {m['test']['n_positive']} injected + {m['test']['n_benign']} benign). Read
every rate as indicative, not precise.

## Dev

Overall injected recall {_pct(m['dev']['recall'])}
({m['dev']['tp']}/{m['dev']['n_positive']}); precision {_pct(m['dev']['precision'])};
benign flag rate {_pct(m['dev']['benign_flag_rate'])}.

{class_table('dev')}

## Test (scored once)

Overall injected recall {_pct(m['test']['recall'])}
({m['test']['tp']}/{m['test']['n_positive']}); precision {_pct(m['test']['precision'])};
benign flag rate {_pct(m['test']['benign_flag_rate'])}.

{class_table('test')}

## Alert rate on real traffic

{ra['n_flagged']} of {ra['n_sampled']} uninjected real windows from hours
{ra['hours']} were flagged: **{_pct(ra['rate'])}**. This is a false-positive proxy
on unlabelled real traffic, not a measured precision.

Total alerts written for the pipeline: {m['n_alerts']} (dev + test flagged windows).

_Generated {m['generated_utc']}. Every number here traces to
`results/detector/metrics.json`._
"""


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Run the ADS-B detector over scenarios and traffic.")
    ap.add_argument(
        "--method", choices=["isolation_forest", "rules"],
        help="override config/detector.yaml method (for a baseline comparison)")
    ap.add_argument(
        "--tag",
        help="write metrics to results/detector/<tag>/ and skip rewriting alerts.json")
    args = ap.parse_args()

    if args.method or args.tag:
        tag = args.tag or args.method
        run_detector(
            out_results=REPO_ROOT / "results" / "detector" / tag,
            method_override=args.method,
            write_alerts=False,
        )
    else:
        run_detector()


if __name__ == "__main__":
    main()
