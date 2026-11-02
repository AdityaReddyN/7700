"""M7 orchestrator: run one alert through config A or config D, timed and traced.

Sequential by default on the CPU laptop (`max_concurrency: 1`); the semaphore is
real so the design is honest and can be raised if measured to help (ARCHITECTURE
§10). Every stage is timed; one trace is written to `runs/<inv_id>/trace.json`
with the stage names from ARCHITECTURE §8. A failed stage degrades to an
inconclusive result rather than crashing the investigation.

CLI: `python -m agents.orchestrator [--alert-id ID] [--config A|D]` over
`data/scenarios/alerts.json` (make run-case).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

from agents.adjudicator import _evidence_table, _supporting_count, run_adjudicator
from agents.llm import LLMClient
from agents.subagent import run_single_agent, run_subagent
from agents.triage import run_triage
from agents.verifier import verified_only, verify_report
from common.config import REPO_ROOT, load_yaml
from common.ids import new_investigation_id
from common.logging import get_logger
from common.schemas import Alert, HypothesisReport, IncidentReport
from tools.registry import ToolRegistry, default_provider, default_retriever
from tools.toollog import ToolLog

log = get_logger("agents.orchestrator")


def _cfg_for(config_name: str, ablations: dict) -> dict:
    configs = ablations.get("configs", {})
    if config_name not in configs:
        raise ValueError(f"unknown config {config_name!r}; have {sorted(configs)}")
    return configs[config_name]


def _models_summary(models_cfg: dict, llm: LLMClient) -> dict:
    return {stage: llm.model_for(stage) for stage in ("triage", "subagent", "adjudication")}


async def investigate(alert: Alert, config_name: str, *, provider, retriever,
                      run_dir: Path | None = None, models_cfg: dict | None = None,
                      agents_cfg: dict | None = None, ablations_cfg: dict | None = None,
                      llm: LLMClient | None = None,
                      write_trace: bool = True) -> tuple[IncidentReport, dict]:
    models_cfg = models_cfg if models_cfg is not None else load_yaml("models")
    agents_cfg = agents_cfg if agents_cfg is not None else load_yaml("agents")
    ablations_cfg = ablations_cfg if ablations_cfg is not None else load_yaml("ablations")
    ablation = _cfg_for(config_name, ablations_cfg)

    inv_id = new_investigation_id()
    run_dir = run_dir or (REPO_ROOT / "runs" / inv_id)
    run_dir.mkdir(parents=True, exist_ok=True)

    toollog = ToolLog(max_chars=int(agents_cfg.get("tool_output_max_chars", 1600)))
    registry = ToolRegistry(alert, provider, retriever, toollog)
    if llm is None:
        llm = LLMClient(models_cfg=models_cfg, agents_cfg=agents_cfg,
                        log_path=run_dir / "llm_calls.jsonl", alert_id=alert.alert_id,
                        config_name=config_name)
    sem = asyncio.Semaphore(int(agents_cfg.get("max_concurrency", 1)))
    max_tokens = agents_cfg.get("max_tokens", {})
    timing: dict[str, float] = {}
    trace: dict = {"investigation_id": inv_id, "config": config_name,
                   "alert": alert.model_dump()}

    async def _timed(name, coro):
        t0 = time.perf_counter()
        out = await coro
        timing[name] = round(time.perf_counter() - t0, 2)
        return out

    if config_name == "D":
        incident = await _run_config_d(llm, registry, alert, ablation, agents_cfg,
                                       max_tokens, sem, timing, trace, _timed)
    else:
        incident = await _run_config_a(llm, registry, alert, ablation, agents_cfg,
                                       max_tokens, timing, trace, _timed)

    incident.meta.update({
        "config": config_name, "models": _models_summary(models_cfg, llm),
        "stage_seconds": timing, "total_seconds": round(sum(timing.values()), 2),
        "n_llm_calls": len(llm.calls), "n_tool_calls": len(toollog),
        "prompt_tokens": sum(c["prompt_tokens"] for c in llm.calls),
        "completion_tokens": sum(c["completion_tokens"] for c in llm.calls),
    })
    trace["report"] = incident.model_dump()
    trace["timing_s"] = timing
    trace["toollog"] = toollog.as_dict()
    trace["llm_calls"] = llm.calls
    if write_trace:
        (run_dir / "trace.json").write_text(json.dumps(trace, indent=2, default=str),
                                            encoding="utf-8")
    log.info("config %s: verdict=%s confidence=%.2f in %.1fs (%d llm calls, %d tool calls)",
             config_name, incident.verdict, incident.confidence,
             incident.meta["total_seconds"], len(llm.calls), len(toollog))
    return incident, trace


async def _run_config_d(llm, registry, alert, ablation, agents_cfg, max_tokens,
                        sem, timing, trace, _timed) -> IncidentReport:
    kept, raw_triage, fallback = await _timed(
        "triage", run_triage(llm, alert, agents_cfg,
                             max_tokens=int(max_tokens.get("triage", 300))))
    trace["triage"] = {"kept": [it.model_dump() for it in kept],
                       "raw": raw_triage.model_dump() if raw_triage else None,
                       "fallback": fallback}

    limit = int(agents_cfg.get("subagent_tool_call_limit", 4))
    reports: list[HypothesisReport] = []
    for item in kept:
        async with sem:  # concurrency 1 by default; sequential on this CPU
            report = await _timed(
                f"subagent:{item.hypothesis}",
                run_subagent(llm, registry, alert, item, tool_call_limit=limit,
                             max_tokens=int(max_tokens.get("subagent", 700))))
        reports.append(report)
    trace["subagents"] = [r.model_dump() for r in reports]

    t0 = time.perf_counter()
    verified_reports: list[HypothesisReport] = []
    verifications = []
    excluded = 0
    for report in reports:
        vr, stats = verify_report(report, registry.log)
        excluded += stats.n_failed
        verified_reports.append(verified_only(vr))
        verifications.append({"hypothesis": report.hypothesis, **stats.as_dict()})
    timing["verification"] = round(time.perf_counter() - t0, 2)
    trace["verification"] = verifications

    incident = await _timed(
        "adjudication",
        run_adjudicator(llm, alert, verified_reports, excluded_count=excluded,
                        cfg=agents_cfg, max_tokens=int(max_tokens.get("adjudicator", 900)),
                        meta={"triage_fallback": fallback}))
    return incident


async def _run_config_a(llm, registry, alert, ablation, agents_cfg, max_tokens,
                        timing, trace, _timed) -> IncidentReport:
    limit = int(agents_cfg.get("config_a_tool_call_limit", 8))
    report, alternatives = await _timed(
        "subagent:single", run_single_agent(llm, registry, alert, tool_call_limit=limit,
                                            max_tokens=int(max_tokens.get("subagent", 700))))
    trace["subagents"] = [report.model_dump()]
    trace["alternatives"] = alternatives

    t0 = time.perf_counter()
    vr, stats = verify_report(report, registry.log)
    vr = verified_only(vr)
    timing["verification"] = round(time.perf_counter() - t0, 2)
    trace["verification"] = [{"hypothesis": report.hypothesis, **stats.as_dict()}]

    # Config A has no adjudicator model call: the verdict is the single agent's,
    # with the same evidence verification and confidence cap so A and D compare.
    cap = float(agents_cfg.get("confidence_cap_single_evidence", 0.9))
    if report.verdict == "supported":
        verdict = report.hypothesis
        confidence = report.confidence
        if _supporting_count([vr], verdict) < 2:
            confidence = min(confidence, cap)
    else:
        verdict, confidence = "inconclusive", min(report.confidence, cap)
    return IncidentReport(
        alert_id=alert.alert_id, verdict=verdict, confidence=round(confidence, 3),
        ranked=[vr], evidence_table=_evidence_table([vr]),
        excluded_evidence_count=stats.n_failed, inference=report.inference,
        would_change_my_mind=report.would_disprove,
        recommended_action="(config A: single agent; no adjudicator stage)",
        meta={"alternatives": alternatives})


def investigate_sync(alert: Alert, config_name: str, **kwargs) -> tuple[IncidentReport, dict]:
    return asyncio.run(investigate(alert, config_name, **kwargs))


def _load_alert(alert_id: str | None) -> Alert:
    path = REPO_ROOT / "data" / "scenarios" / "alerts.json"
    alerts = json.loads(path.read_text(encoding="utf-8"))
    if not alerts:
        raise SystemExit("no alerts in data/scenarios/alerts.json; run `make alerts`")
    if alert_id:
        match = [a for a in alerts if a["alert_id"] == alert_id]
        if not match:
            raise SystemExit(f"alert_id {alert_id!r} not found")
        return Alert(**match[0])
    return Alert(**alerts[0])


def main() -> None:
    ap = argparse.ArgumentParser(description="Run one alert through the pipeline (M7).")
    ap.add_argument("--alert-id", default=None, help="alert_id; default = first alert")
    ap.add_argument("--config", default="D", choices=["A", "D"], help="ablation config")
    args = ap.parse_args()

    alert = _load_alert(args.alert_id)
    provider = default_provider()
    retriever = default_retriever()
    incident, _ = investigate_sync(alert, args.config, provider=provider, retriever=retriever)
    print(f"alert {alert.alert_id} [config {args.config}] -> {incident.verdict} "
          f"(confidence {incident.confidence}, {incident.meta.get('total_seconds')}s, "
          f"{incident.meta.get('n_tool_calls')} tool calls)")
    print(f"evidence items (verified): {len(incident.evidence_table)}; "
          f"excluded: {incident.excluded_evidence_count}")


if __name__ == "__main__":
    main()
