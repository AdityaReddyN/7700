"""M8 summary (`make summarize`): build summary.csv/.md, figures and the spot-check.

Reads only `results/<run_id>/` (case records + traces) — nothing is hand-typed
(AGENTS non-negotiable #3). Writes `summary.csv` (one row per case), `summary.md`
(tables with the n=10 / 15-missed caveat), figures, and the §8 spot-check CSV
template (10 sampled evidence items per config for a human to fill).
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

from common.config import REPO_ROOT
from common.logging import get_logger
from eval import figures as fig
from eval import metrics as M

log = get_logger("eval.summarize")

_CSV_COLS = ["config", "alert_id", "scenario_id", "label", "verdict", "correct",
             "top2_correct", "confidence", "evidence_total", "evidence_verified",
             "support_rate", "n_tool_calls", "total_seconds", "inconclusive"]


def latest_run_dir() -> Path:
    runs = [p for p in (REPO_ROOT / "results").iterdir()
            if p.is_dir() and (p / "cases").exists()]
    if not runs:
        raise SystemExit("no eval runs under results/ with a cases/ folder")
    return max(runs, key=lambda p: p.stat().st_mtime)


def load_cases(run_dir: Path) -> dict[str, list[dict]]:
    by_config: dict[str, list[dict]] = {}
    for path in sorted((run_dir / "cases").glob("*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        by_config.setdefault(rec["config"], []).append(rec)
    return by_config


def write_csv(run_dir: Path, by_config: dict[str, list[dict]]) -> Path:
    out = run_dir / "summary.csv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=_CSV_COLS)
        w.writeheader()
        for cases in by_config.values():
            for c in cases:
                w.writerow({k: c.get(k) for k in _CSV_COLS})
    return out


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{100 * x:.0f}%"


def _detector_and_missed(run_dir: Path) -> tuple[dict | None, dict | None]:
    missed = None
    mp = run_dir / "missed.json"
    if mp.exists():
        missed = json.loads(mp.read_text(encoding="utf-8"))
    det = None
    dp = REPO_ROOT / "results" / "detector" / "metrics.json"
    if dp.exists():
        det = json.loads(dp.read_text(encoding="utf-8"))
    return det, missed


def write_md(run_dir: Path, by_config: dict[str, list[dict]], mbc: dict) -> Path:
    det, missed = _detector_and_missed(run_dir)
    n_eval = missed.get("n_evaluated") if missed else (
        len(next(iter(by_config.values()))) if by_config else 0)
    n_test = missed.get("n_test") if missed else "?"
    lines = [
        "# Evaluation summary (M8)", "",
        f"**n = {n_eval} evaluated of {n_test} test scenarios, one run per config.** "
        "The detector alerted on only these; the rest are missed detections (below), so "
        "the A-vs-D comparison covers a biased subset — read every number with that in mind.",
        "",
    ]
    if missed:
        n_missed = len(missed.get("missed_scenarios", []))
        lines += ["## Detector coverage on test", "",
                  f"- evaluated (had an alert): **{missed.get('n_evaluated')}** of "
                  f"{missed.get('n_test')}",
                  f"- missed (no alert, pipeline never ran): **{n_missed}**",
                  f"- missed by label: {missed.get('missed_by_label')}", ""]
    for config in by_config:
        m = mbc[config]
        acc, ci = m["accuracy"], m["top1_ci"]
        es = m["evidence_support"]
        lines += [
            f"## Config {config} (n={acc['n']})", "",
            f"- top-1 accuracy: **{_pct(acc['top1'])}** ({acc['top1_count']}/{acc['n']}); "
            f"95% bootstrap CI [{_pct(ci['lo'])}, {_pct(ci['hi'])}]",
            f"- top-2 accuracy: {_pct(acc['top2'])} ({acc['top2_count']}/{acc['n']})",
            f"- evidence support rate: {_pct(es['support_rate'])} "
            f"({es['verified']}/{es['n_items']} items; {es['partial']} partial, "
            f"{es['failed']} failed)",
            f"- inconclusive: {_pct(m['inconclusive']['rate'])} "
            f"({m['inconclusive']['inconclusive']}/{m['inconclusive']['n']})",
            f"- tool-call validity: {_pct(m['llm_quality']['tool_call_validity'])} "
            f"({m['llm_quality']['n_tool_turns']} tool turns); structured parse "
            f"{_pct(m['llm_quality']['structured_parse_rate'])} "
            f"({m['llm_quality']['n_structured']} calls)",
            f"- latency per investigation: p50 {m['latency']['p50']}s, "
            f"max {m['latency']['max']}s (one CPU laptop)",
            "",
            "| label | n | precision | recall | f1 |",
            "|---|---|---|---|---|",
        ]
        for lab, pc in m["per_class"].items():
            lines.append(f"| {lab} | {pc['n']} | {_pct(pc['precision'])} | "
                         f"{_pct(pc['recall'])} | {_pct(pc['f1'])} |")
        lines.append("")
    lines += ["_Numbers from this run's case records; figures alongside. "
              "Small n: treat as directional, not conclusive._", ""]
    out = run_dir / "summary.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def write_spotcheck(run_dir: Path, by_config: dict[str, list[dict]], *,
                    per_config: int = 10, seed: int = 0) -> Path:
    rng = random.Random(seed)
    rows: list[dict] = []
    for config, cases in by_config.items():
        items: list[dict] = []
        for c in cases:
            trace_path = run_dir / "traces" / f"{config}__{c['alert_id']}" / "trace.json"
            if not trace_path.exists():
                continue
            trace = json.loads(trace_path.read_text(encoding="utf-8"))
            toollog = trace.get("toollog", {})
            for sa in trace.get("subagents", []):
                for ev in sa.get("evidence", []):
                    ref = ev.get("ref_id", "")
                    snip = json.dumps(toollog.get(ref, {}).get("output", {}), default=str)[:200] \
                        if ref in toollog else "(ref not in toollog)"
                    items.append({"alert_id": c["alert_id"], "config": config,
                                  "evidence_claim": ev.get("claim", ""), "ref_id": ref,
                                  "tool_output_snippet": snip,
                                  "verifier_verified": ev.get("verified"),
                                  "human_supports_y_n": "", "notes": ""})
        rng.shuffle(items)
        rows.extend(items[:per_config])
    out = run_dir / "spotcheck_template.csv"
    cols = ["alert_id", "config", "evidence_claim", "ref_id", "tool_output_snippet",
            "verifier_verified", "human_supports_y_n", "notes"]
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    return out


def make_figures(run_dir: Path, by_config: dict[str, list[dict]], mbc: dict) -> list[Path]:
    fdir = run_dir / "figures"
    fdir.mkdir(exist_ok=True)
    paths = [fig.accuracy_by_config(mbc, fdir / "accuracy_by_config.png"),
             fig.latency_per_case(by_config, fdir / "latency_per_case.png")]
    if "D" in mbc:
        paths.append(fig.confusion_matrix(mbc["D"]["confusion"], fdir / "confusion_D.png"))
        paths.append(fig.calibration(mbc["D"]["calibration"], fdir / "calibration_D.png"))
    return paths


def summarize(run_dir: Path) -> dict:
    by_config = load_cases(run_dir)
    if not by_config:
        raise SystemExit(f"no case records under {run_dir}/cases")
    mbc = {config: M.all_metrics(cases) for config, cases in by_config.items()}
    (run_dir / "metrics.json").write_text(json.dumps(mbc, indent=2), encoding="utf-8")
    write_csv(run_dir, by_config)
    write_md(run_dir, by_config, mbc)
    write_spotcheck(run_dir, by_config)
    make_figures(run_dir, by_config, mbc)
    log.info("summarised %s (%s)", run_dir.name,
             ", ".join(f"{k}:{len(v)}" for k, v in by_config.items()))
    return mbc


def main() -> None:
    ap = argparse.ArgumentParser(description="Summarise an eval run (make summarize).")
    ap.add_argument("--run-id", default=None, help="results/<run-id>; default = latest")
    args = ap.parse_args()
    run_dir = (REPO_ROOT / "results" / args.run_id) if args.run_id else latest_run_dir()
    summarize(run_dir)
    print(f"wrote {run_dir}/summary.csv, summary.md, metrics.json, figures/, "
          "spotcheck_template.csv")


if __name__ == "__main__":
    main()
