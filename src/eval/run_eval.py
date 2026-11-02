"""M8 evaluation runner: configs A and D over the test split, resumable.

Ground truth is `alert_map.json` (alert -> scenario) + `splits.json` (scenario ->
label). The label is used only to score the saved verdict; it never enters the
pipeline (the leakage test still holds). Only test scenarios that produced an
alert are investigated; the rest are recorded as detector misses
(EVALUATION_PROTOCOL §9). Each case writes one JSON under `cases/`, so a run
resumes by skipping cases already present.

Note (2026-11-02): the detector alerted on 10 of 25 test scenarios, all
`ghost_aircraft` and `replay_duplicate`; the other 15 are missed. The A-vs-D
comparison is therefore over 10 alerts / 2 classes — say so with every number.

CLI: `make eval` → `python -m eval.run_eval [--config A|D|both] [--resume]
[--limit N] [--run-id ID]`.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

from agents.orchestrator import investigate_sync
from common.config import REPO_ROOT, get_settings, load_yaml
from common.logging import get_logger
from common.schemas import Alert

log = get_logger("eval.run_eval")


def _git_commit() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                             timeout=10, cwd=REPO_ROOT)
        return out.stdout.strip() or "unknown"
    except Exception:  # noqa: BLE001
        return "unknown"


def _ollama_digest(model: str) -> str:
    try:
        out = subprocess.run(["ollama", "show", model], capture_output=True, text=True,
                             timeout=30)
        return (out.stdout or out.stderr).strip()[:400]
    except Exception:  # noqa: BLE001
        return "unavailable"


def load_index(data_dir: Path) -> tuple[dict, dict, dict, dict]:
    scen_dir = data_dir / "scenarios"
    splits = json.loads((scen_dir / "splits.json").read_text(encoding="utf-8"))
    amap = json.loads((scen_dir / "alert_map.json").read_text(encoding="utf-8"))
    alerts = {a["alert_id"]: a
              for a in json.loads((scen_dir / "alerts.json").read_text(encoding="utf-8"))}
    scn = {s["scenario_id"]: s for s in splits["scenarios"]}
    return splits, amap, alerts, scn


def select_cases(splits: dict, amap: dict, alerts: dict,
                 split: str = "test") -> tuple[list[tuple[str, dict]], list[str]]:
    """Return ([(alert_id, scenario)], [missed scenario_id]) for the split."""
    s2a: dict[str, list[str]] = {}
    for aid, sid in amap.items():
        if aid in alerts:
            s2a.setdefault(sid, []).append(aid)
    cases, missed = [], []
    for s in splits["scenarios"]:
        if s["split"] != split:
            continue
        aids = sorted(s2a.get(s["scenario_id"], []))
        if aids:
            cases.append((aids[0], s))
        else:
            missed.append(s["scenario_id"])
    cases.sort(key=lambda c: c[0])
    return cases, missed


def _ranked_labels(incident, config: str) -> list[str]:
    out = [r.hypothesis for r in incident.ranked]
    if config == "A":
        out += [a.get("hypothesis") for a in incident.meta.get("alternatives", [])
                if isinstance(a, dict)]
    seen: list[str] = []
    for h in out:
        if h and h not in seen:
            seen.append(h)
    return seen


def build_case_record(alert_id: str, scenario: dict, incident, trace: dict,
                      config: str) -> dict:
    label = scenario["label"]
    ranked = _ranked_labels(incident, config)
    ver = trace.get("verification", [])
    tot = sum(e.get("n_total", 0) for e in ver)
    verified = sum(e.get("n_verified", 0) for e in ver)
    partial = sum(e.get("n_partial", 0) for e in ver)
    failed = sum(e.get("n_failed", 0) for e in ver)
    m = incident.meta
    calls = [{"stage": c.get("stage"), "mode": c.get("mode"),
              "tool_calls_count": c.get("tool_calls_count", 0),
              "tool_call_valid": c.get("tool_call_valid"), "parse_ok": c.get("parse_ok")}
             for c in trace.get("llm_calls", [])]
    return {
        "alert_id": alert_id, "scenario_id": scenario["scenario_id"], "config": config,
        "label": label, "verdict": incident.verdict,
        "correct": incident.verdict == label,
        "top2_correct": label in ranked[:2], "ranked": ranked,
        "confidence": incident.confidence, "inconclusive": incident.verdict == "inconclusive",
        "evidence_total": tot, "evidence_verified": verified,
        "evidence_partial": partial, "evidence_failed": failed,
        "support_rate": (verified / tot) if tot else None,
        "n_tool_calls": m.get("n_tool_calls"), "n_llm_calls": m.get("n_llm_calls"),
        "total_seconds": m.get("total_seconds"), "stage_seconds": m.get("stage_seconds"),
        "triage_fallback": trace.get("triage", {}).get("fallback"),
        "llm_calls": calls,
    }


def run(configs: list[str], *, provider, retriever, run_dir: Path, split: str = "test",
        resume: bool = True, limit: int | None = None, data_dir: Path | None = None,
        llm_factory=None, agents_cfg: dict | None = None, models_cfg: dict | None = None,
        ablations_cfg: dict | None = None) -> dict:
    data_dir = data_dir or (REPO_ROOT / get_settings().data_dir).resolve()
    models_cfg = models_cfg if models_cfg is not None else load_yaml("models")
    agents_cfg = agents_cfg if agents_cfg is not None else load_yaml("agents")
    ablations_cfg = ablations_cfg if ablations_cfg is not None else load_yaml("ablations")

    splits, amap, alerts, scn = load_index(data_dir)
    cases, missed = select_cases(splits, amap, alerts, split)
    if limit is not None:
        cases = cases[:limit]

    run_dir.mkdir(parents=True, exist_ok=True)
    cases_dir = run_dir / "cases"
    traces_dir = run_dir / "traces"
    cases_dir.mkdir(exist_ok=True)
    traces_dir.mkdir(exist_ok=True)

    (run_dir / "missed.json").write_text(json.dumps(
        {"split": split, "n_test": sum(1 for s in splits["scenarios"] if s["split"] == split),
         "n_evaluated": len(cases), "missed_scenarios": missed,
         "missed_by_label": _by_label(scn, missed)}, indent=2), encoding="utf-8")

    config_path = run_dir / "config.json"
    if not config_path.exists():
        primary = models_cfg.get("primary", {}).get("model", "")
        triage = models_cfg.get("triage", {}).get("model", "")
        config_path.write_text(json.dumps({
            "configs": configs, "split": split, "git_commit": _git_commit(),
            "seeds": {"primary_seed": models_cfg.get("primary", {}).get("seed")},
            "models": {"primary": primary, "triage": triage},
            "model_digests": {primary: _ollama_digest(primary) if not llm_factory else "fake",
                              triage: _ollama_digest(triage) if not llm_factory else "fake"},
            "agents_cfg": agents_cfg, "ablations": ablations_cfg.get("configs", {}),
        }, indent=2), encoding="utf-8")

    done, ran = 0, 0
    for config in configs:
        for alert_id, scenario in cases:
            case_path = cases_dir / f"{config}__{alert_id}.json"
            if resume and case_path.exists():
                done += 1
                continue
            alert = Alert(**alerts[alert_id])
            kwargs = dict(provider=provider, retriever=retriever,
                          run_dir=traces_dir / f"{config}__{alert_id}",
                          agents_cfg=agents_cfg, models_cfg=models_cfg,
                          ablations_cfg=ablations_cfg)
            if llm_factory is not None:
                kwargs["llm"] = llm_factory(alert, config)
            t0 = time.perf_counter()
            incident, trace = investigate_sync(alert, config, **kwargs)
            rec = build_case_record(alert_id, scenario, incident, trace, config)
            case_path.write_text(json.dumps(rec, indent=2, default=str), encoding="utf-8")
            ran += 1
            done += 1
            log.info("[%s] %s %s -> %s (%.0fs, %d/%d)", config, alert_id, scenario["label"],
                     incident.verdict, time.perf_counter() - t0, done, len(cases) * len(configs))

    summary = {"run_dir": str(run_dir), "configs": configs, "n_cases": len(cases),
               "n_missed": len(missed), "ran": ran, "already_done": done - ran}
    (run_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def _by_label(scn: dict, scenario_ids: list[str]) -> dict:
    out: dict[str, int] = {}
    for sid in scenario_ids:
        lab = scn.get(sid, {}).get("label", "unknown")
        out[lab] = out.get(lab, 0) + 1
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="M8 evaluation over the test split (resumable).")
    ap.add_argument("--config", default="both", choices=["A", "D", "both"])
    ap.add_argument("--split", default="test")
    ap.add_argument("--resume", action="store_true", help="skip cases already written")
    ap.add_argument("--limit", type=int, default=None, help="evaluate only the first N alerts")
    ap.add_argument("--run-id", default=None, help="results/<run-id>; default derived from split")
    args = ap.parse_args()

    from tools.registry import default_provider, default_retriever

    configs = ["A", "D"] if args.config == "both" else [args.config]
    run_id = args.run_id or f"{args.split}_{time.strftime('%Y%m%dT%H%M%S', time.gmtime())}"
    run_dir = REPO_ROOT / "results" / run_id
    provider = default_provider()
    retriever = default_retriever()
    summary = run(configs, provider=provider, retriever=retriever, run_dir=run_dir,
                  split=args.split, resume=args.resume, limit=args.limit)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
