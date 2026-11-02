"""M8 metrics: pure functions over the saved case records (EVALUATION_PROTOCOL §4, §6).

Every function takes `cases` — a list of the dicts written by `run_eval` — so
nothing here reads a model or recomputes a verdict. Small-sample caveats live in
the summary text, not here. Bootstrap CIs use a fixed seed for reproducibility.
"""

from __future__ import annotations

import random
from statistics import median

from common.schemas import LABELS

VERDICTS = (*LABELS, "inconclusive")


def accuracy(cases: list[dict]) -> dict:
    n = len(cases)
    top1 = sum(1 for c in cases if c["correct"])
    top2 = sum(1 for c in cases if c.get("top2_correct"))
    return {"n": n, "top1": top1 / n if n else None, "top2": top2 / n if n else None,
            "top1_count": top1, "top2_count": top2}


def per_class(cases: list[dict], labels: tuple[str, ...] = LABELS) -> dict:
    out: dict[str, dict] = {}
    for lab in labels:
        actual = [c for c in cases if c["label"] == lab]
        predicted = [c for c in cases if c["verdict"] == lab]
        tp = sum(1 for c in actual if c["verdict"] == lab)
        prec = tp / len(predicted) if predicted else None
        rec = tp / len(actual) if actual else None
        f1 = (2 * prec * rec / (prec + rec)) if (prec and rec) else (0.0 if actual else None)
        out[lab] = {"n": len(actual), "n_predicted": len(predicted), "tp": tp,
                    "precision": prec, "recall": rec, "f1": f1}
    return out


def confusion(cases: list[dict], labels: tuple[str, ...] = LABELS) -> dict:
    cols = list(VERDICTS)
    idx = {v: i for i, v in enumerate(cols)}
    mat = [[0] * len(cols) for _ in labels]
    for i, lab in enumerate(labels):
        for c in cases:
            if c["label"] == lab and c["verdict"] in idx:
                mat[i][idx[c["verdict"]]] += 1
    return {"rows": list(labels), "cols": cols, "matrix": mat}


def evidence_support(cases: list[dict]) -> dict:
    tot = sum(c.get("evidence_total", 0) for c in cases)
    ver = sum(c.get("evidence_verified", 0) for c in cases)
    par = sum(c.get("evidence_partial", 0) for c in cases)
    fail = sum(c.get("evidence_failed", 0) for c in cases)
    return {"n_items": tot, "verified": ver, "partial": par, "failed": fail,
            "support_rate": ver / tot if tot else None,
            "unsupported_rate": fail / tot if tot else None}


def inconclusive_rate(cases: list[dict]) -> dict:
    n = len(cases)
    k = sum(1 for c in cases if c.get("inconclusive"))
    return {"n": n, "inconclusive": k, "rate": k / n if n else None}


def llm_quality(cases: list[dict]) -> dict:
    tool_turns = tool_valid = struct = struct_ok = 0
    for c in cases:
        for call in c.get("llm_calls", []):
            if call.get("mode") == "native_tools" and call.get("tool_calls_count", 0) > 0:
                tool_turns += 1
                tool_valid += 1 if call.get("tool_call_valid") else 0
            if call.get("mode") == "json_schema":
                struct += 1
                struct_ok += 1 if call.get("parse_ok") else 0
    return {"n_tool_turns": tool_turns,
            "tool_call_validity": tool_valid / tool_turns if tool_turns else None,
            "n_structured": struct,
            "structured_parse_rate": struct_ok / struct if struct else None}


def latency(cases: list[dict]) -> dict:
    secs = [c["total_seconds"] for c in cases if c.get("total_seconds") is not None]
    return {"n": len(secs), "p50": median(secs) if secs else None,
            "max": max(secs) if secs else None}


def calibration(cases: list[dict]) -> list[dict]:
    bands = [("<0.5", lambda x: x < 0.5), ("0.5-0.7", lambda x: 0.5 <= x <= 0.7),
             (">0.7", lambda x: x > 0.7)]
    out = []
    for name, pred in bands:
        band = [c for c in cases if pred(c["confidence"])]
        correct = sum(1 for c in band if c["correct"])
        out.append({"band": name, "n": len(band), "correct": correct,
                    "accuracy": correct / len(band) if band else None})
    return out


def bootstrap_ci(cases: list[dict], metric: str, *, n_resamples: int = 1000,
                 seed: int = 0, alpha: float = 0.05) -> dict:
    """95% bootstrap CI over cases for 'top1' or 'support' (EVALUATION_PROTOCOL §6)."""
    if not cases:
        return {"point": None, "lo": None, "hi": None, "n": 0, "n_resamples": n_resamples}
    rng = random.Random(seed)

    def stat(sample: list[dict]) -> float | None:
        if metric == "top1":
            return sum(1 for c in sample if c["correct"]) / len(sample)
        tot = sum(c.get("evidence_total", 0) for c in sample)
        return (sum(c.get("evidence_verified", 0) for c in sample) / tot) if tot else None

    point = stat(cases)
    draws = []
    for _ in range(n_resamples):
        sample = [cases[rng.randrange(len(cases))] for _ in cases]
        s = stat(sample)
        if s is not None:
            draws.append(s)
    draws.sort()
    if not draws:
        return {"point": point, "lo": None, "hi": None, "n": len(cases),
                "n_resamples": n_resamples}
    lo = draws[int((alpha / 2) * len(draws))]
    hi = draws[min(len(draws) - 1, int((1 - alpha / 2) * len(draws)))]
    return {"point": point, "lo": lo, "hi": hi, "n": len(cases), "n_resamples": n_resamples}


def detector_summary(detector_metrics: dict | None, missed: dict | None) -> dict:
    """Pull detector recall/FP from results/detector + the missed.json counts."""
    out: dict = {"missed": missed or {}}
    if detector_metrics:
        out["detector"] = {k: detector_metrics.get(k) for k in
                           ("test", "dev", "precision", "recall", "alert_rate")
                           if k in detector_metrics}
    return out


def all_metrics(cases: list[dict]) -> dict:
    return {
        "accuracy": accuracy(cases),
        "per_class": per_class(cases),
        "confusion": confusion(cases),
        "evidence_support": evidence_support(cases),
        "inconclusive": inconclusive_rate(cases),
        "llm_quality": llm_quality(cases),
        "latency": latency(cases),
        "calibration": calibration(cases),
        "top1_ci": bootstrap_ci(cases, "top1"),
        "support_ci": bootstrap_ci(cases, "support"),
    }
