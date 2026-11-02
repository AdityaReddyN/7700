"""M7 subagent: test one hypothesis with bounded, read-only tool calls.

Native Ollama tool-calling loop (measured working, API_NOTES §2) through the M5
`ToolRegistry`. At most `tool_call_limit` tool calls (4 for config D, 8 for the
config-A single agent), then one structured `HypothesisReport` is forced. A
parse failure is retried once inside the LLM wrapper, then recorded as
`inconclusive`; any tool/loop exception also yields an `inconclusive` report with
a note, and the investigation continues (ARCHITECTURE §2.4, §10).
"""

from __future__ import annotations

import json

from pydantic import Field

from agents.llm import LLMClient
from agents.prompts import CHEATSHEET, fill, load_prompt
from agents.triage import alert_json
from common.schemas import Alert, HypothesisReport, TriageItem
from tools.registry import TOOL_SPECS, ToolRegistry

_FINAL_INSTRUCTION = (
    "You have gathered your evidence. Now return ONLY the JSON object described "
    "above, citing ref_ids from the tool results you saw. No tool calls, no prose."
)


class SingleAgentReport(HypothesisReport):
    """Config-A output: a HypothesisReport plus brief ranked alternatives."""

    alternatives: list[dict] = Field(default_factory=list)  # {hypothesis, reason}


def _assistant_turn(text: str, tool_calls: list[dict]) -> dict:
    msg: dict = {"role": "assistant", "content": text or ""}
    if tool_calls:
        msg["tool_calls"] = [
            {"id": tc["id"], "type": "function",
             "function": {"name": tc["name"], "arguments": tc["arguments"]}}
            for tc in tool_calls
        ]
    return msg


def _inconclusive(hypothesis: str, note: str, tools_used: int) -> HypothesisReport:
    return HypothesisReport(
        hypothesis=hypothesis, verdict="inconclusive", confidence=0.0, evidence=[],
        inference=f"reasoning: {note}", would_disprove=[], next_checks=[],
        tool_calls_used=tools_used,
    )


async def _run_loop(llm: LLMClient, registry: ToolRegistry, alert: Alert, *,
                    stage: str, system: str, user: str, tool_call_limit: int,
                    schema: type[HypothesisReport], max_tokens: int):
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    used = 0        # tool calls that ran successfully (reported as tool_calls_used)
    attempts = 0    # every executed tool call; this is what bounds the loop
    # Tool-gathering turns. The budget counts ATTEMPTS, not successes: a model that
    # keeps emitting failing tool calls (e.g. missing required args) must still stop.
    while attempts < tool_call_limit:
        res = await llm.complete(stage, messages, tools=TOOL_SPECS, max_tokens=max_tokens)
        if res.error and not res.tool_calls:
            return None, used, res.error
        if not res.tool_calls:
            break
        messages.append(_assistant_turn(res.text, res.tool_calls))
        for tc in res.tool_calls:
            if attempts >= tool_call_limit:
                content = json.dumps({"error": "tool-call budget reached"})
            else:
                attempts += 1
                try:
                    args = json.loads(tc["arguments"] or "{}")
                    if not isinstance(args, dict):
                        raise ValueError("arguments were not a JSON object")
                    tr = registry.call(tc["name"], args)
                    # Surface the ref_id so the model can cite it (prompts require it).
                    content = json.dumps({"ref_id": tr.ref_id, "result": tr.output},
                                         default=str)
                    used += 1
                except Exception as exc:  # noqa: BLE001 - surfaced to the model as data
                    content = json.dumps({"error": str(exc)[:200]})
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": content})
    # Force the structured final report (no tools).
    messages.append({"role": "user", "content": _FINAL_INSTRUCTION})
    final = await llm.complete(stage, messages, response_schema=schema, max_tokens=max_tokens)
    return final.parsed, used, final.error


async def run_subagent(llm: LLMClient, registry: ToolRegistry, alert: Alert,
                       item: TriageItem, *, tool_call_limit: int = 4,
                       max_tokens: int = 700) -> HypothesisReport:
    """Config-D subagent: investigate one hypothesis, return a HypothesisReport."""
    hyp = item.hypothesis
    sheet = CHEATSHEET[hyp]
    user = fill(load_prompt("subagent"), hypothesis=hyp, definition=sheet["definition"],
                supports=sheet["supports"], refutes=sheet["refutes"],
                tool_call_limit=str(tool_call_limit), alert_json=alert_json(alert))
    try:
        parsed, used, err = await _run_loop(
            llm, registry, alert, stage="subagent", system=load_prompt("preamble"),
            user=user, tool_call_limit=tool_call_limit, schema=HypothesisReport,
            max_tokens=max_tokens)
    except Exception as exc:  # noqa: BLE001 - never crash the investigation
        return _inconclusive(hyp, f"subagent error: {str(exc)[:160]}", 0)
    if parsed is None:
        return _inconclusive(hyp, f"no valid report ({err or 'parse failed'})", used)
    # The subagent tests exactly this hypothesis; pin it and trust our tool count.
    return parsed.model_copy(update={"hypothesis": hyp, "tool_calls_used": used})


async def run_single_agent(llm: LLMClient, registry: ToolRegistry, alert: Alert,
                           *, tool_call_limit: int = 8,
                           max_tokens: int = 700) -> tuple[HypothesisReport, list[dict]]:
    """Config-A single agent: all tools, up to 8 calls, best hypothesis + alternatives."""
    user = fill(load_prompt("subagent_config_a"), tool_call_limit=str(tool_call_limit),
                alert_json=alert_json(alert))
    try:
        parsed, used, err = await _run_loop(
            llm, registry, alert, stage="single_agent", system=load_prompt("preamble"),
            user=user, tool_call_limit=tool_call_limit, schema=SingleAgentReport,
            max_tokens=max_tokens)
    except Exception as exc:  # noqa: BLE001
        return _inconclusive("benign_anomaly", f"single-agent error: {str(exc)[:160]}", 0), []
    if parsed is None:
        return _inconclusive("benign_anomaly", f"no valid report ({err or 'parse failed'})",
                             used), []
    alternatives = list(getattr(parsed, "alternatives", []) or [])
    report = HypothesisReport(**{k: v for k, v in parsed.model_dump().items()
                                 if k != "alternatives"})
    return report.model_copy(update={"tool_calls_used": used}), alternatives
