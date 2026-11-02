"""M6: build the BM25 index from the case cards and evaluate recall@4 on dev.

`make kb` regenerates the cards, writes `data/kb/index.json` in the schema the
M5 `CaseRetriever` expects (`card_id, label, title, text`), then runs a label-
free recall evaluation over the dev split and writes `results/kb/`. Deterministic
and safe to rerun.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pandas as pd
import yaml

from common.config import REPO_ROOT, get_settings
from common.logging import get_logger
from common.schemas import LABELS
from kb.cards import compute_stats, generate_cards, signal_tokens
from tools.retrieval import CaseRetriever

log = get_logger("kb.build_index")

QueryFn = Callable[[dict], tuple[str, bool]]


def parse_card(path: Path) -> dict:
    """Parse one card file into the retriever record {card_id, label, title, text}."""
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---"):
        raise ValueError(f"card {path.name} has no YAML frontmatter")
    _, front, body = raw.split("---", 2)
    meta = yaml.safe_load(front) or {}
    # Index the discriminative signal tokens + the human signature. Differentiators
    # are excluded from the index text: they name other classes and would pollute
    # BM25 with cross-label vocabulary. They stay in the card file for the agent.
    text = " ".join(part for part in (
        meta.get("title", ""), meta.get("signals", ""),
        meta.get("signature", ""), meta.get("outcome", ""),
    ) if part).strip()
    return {"card_id": str(meta["id"]), "label": str(meta["label"]),
            "title": str(meta.get("title", "")), "text": text}


def build_index(cards_dir: Path, out_path: Path) -> list[dict]:
    """Parse all cards (sorted) into the index.json the M5 retriever consumes."""
    records = [parse_card(p) for p in sorted(cards_dir.glob("C*.md"))]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(records, indent=2), encoding="utf-8")
    return records


def _scenario_query(track_loader: Callable[[dict], pd.DataFrame]) -> QueryFn:
    def q(scn: dict) -> tuple[str, bool]:
        df = track_loader(scn)
        if df is None or len(df) == 0:
            return "", False
        query = signal_tokens(*compute_stats(df))
        return query, bool(query)  # no salient signal -> skip (nothing to match on)
    return q


def recall_eval(dev_scenarios: list[dict], retriever: CaseRetriever,
                query_fn: QueryFn, k: int = 4) -> dict:
    """Label-free recall@{1,2,k} on dev; the true label is used only after retrieval."""
    ks = sorted({1, 2, k})
    hit = {kk: 0 for kk in ks}
    per_label: dict[str, dict] = {
        lab: {"n": 0, **{f"recall@{kk}": 0 for kk in ks}} for lab in LABELS
    }
    evaluated = skipped = 0
    for scn in dev_scenarios:
        query, ok = query_fn(scn)
        if not ok:
            skipped += 1
            continue
        evaluated += 1
        true = scn["label"]
        per_label[true]["n"] += 1
        hits = retriever.search(query, "", k=k)
        labels = [h["label"] for h in hits]
        for kk in ks:
            if true in labels[:kk]:
                hit[kk] += 1
                per_label[true][f"recall@{kk}"] += 1
    metrics = {
        "n_dev_evaluated": evaluated,
        "n_dev_skipped": skipped,
        "k": k,
        "n_retrieved_per_query": k,
        **{f"recall@{kk}": (hit[kk] / evaluated if evaluated else None) for kk in ks},
        "per_label": {
            lab: {
                "n": per_label[lab]["n"],
                **{f"recall@{kk}": (per_label[lab][f"recall@{kk}"] / per_label[lab]["n"]
                                    if per_label[lab]["n"] else None) for kk in ks},
            }
            for lab in LABELS
        },
    }
    return metrics


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{100 * x:.0f}%"


def _render_report(m: dict, n_cards: int) -> str:
    lines = [
        "# Knowledge-base retrieval report (M6)",
        "",
        f"BM25 over **{n_cards} case cards** (2 per label, from KB-split scenarios only). "
        "Dense embeddings, RRF and reference passages are deferred (D-033).",
        "",
        f"Evaluated **{m['n_dev_evaluated']}** dev scenarios "
        f"({m['n_dev_skipped']} skipped), top-{m['k']} retrieval per query. The query is "
        "built from each scenario's computed stats with no label; the true label is "
        "compared only after retrieval.",
        "",
        f"- recall@1: **{_pct(m['recall@1'])}**",
        f"- recall@2: **{_pct(m['recall@2'])}**",
        f"- recall@4: **{_pct(m['recall@4'])}**",
        "",
        "## Per label",
        "",
        "| label | n | recall@1 | recall@2 | recall@4 |",
        "|---|---|---|---|---|",
    ]
    for lab in LABELS:
        p = m["per_label"][lab]
        lines.append(f"| {lab} | {p['n']} | {_pct(p['recall@1'])} | "
                     f"{_pct(p['recall@2'])} | {_pct(p.get('recall@4'))} |")
    lines += [
        "",
        "**Expected high — only 10 cards.** The index is deliberately tiny, so high "
        "recall is unsurprising and establishes neither generalisation nor anomaly-"
        "detection quality; it only checks that a correct-label card is reachable from "
        "a scenario's computed profile. The M5 tools do not expose identity *presence*, "
        "so `ghost_aircraft` reads as a quiet track and may retrieve less reliably.",
        "",
        "**Quiet classes and the tie-break.** Quiet classes (`ghost_aircraft`, "
        "`benign_anomaly`) produce near-identical computed profiles, so several cards "
        "tie on the retrieval score and ranking falls to the deterministic `card_id` "
        "tie-break. The reported `ghost_aircraft` recall@4 of 1.0 is therefore partly a "
        "tie-break artifact — ghost cards happen to sort ahead of `benign_anomaly` cards "
        "under equal scores — and does **not** demonstrate strong retrieval discrimination "
        "for quiet classes, especially `ghost_aircraft` versus `benign_anomaly`.",
        "",
        "_Numbers from this run; see `results/kb/recall_at4.json`._",
    ]
    return "\n".join(lines) + "\n"


def run(data_dir: Path | None = None, results_dir: Path | None = None) -> dict:
    data_dir = data_dir or (REPO_ROOT / get_settings().data_dir).resolve()
    results_dir = results_dir or (REPO_ROOT / "results" / "kb")
    scen_dir = data_dir / "scenarios"
    kb_dir = data_dir / "kb"
    cards_dir = kb_dir / "cards"

    catalog = json.loads((scen_dir / "splits.json").read_text(encoding="utf-8"))
    tracks = pd.read_parquet(scen_dir / "tracks.parquet", engine="pyarrow")

    def loader(scn: dict) -> pd.DataFrame:
        return tracks[tracks["scenario_id"] == scn["scenario_id"]]

    cards = generate_cards(catalog, loader, cards_dir)
    records = build_index(cards_dir, kb_dir / "index.json")
    retriever = CaseRetriever.from_kb(kb_dir)

    dev = [s for s in catalog["scenarios"] if s["split"] == "dev"]
    metrics = recall_eval(dev, retriever, _scenario_query(loader), k=4)
    metrics["n_cards"] = len(records)

    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "recall_at4.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    (results_dir / "report.md").write_text(_render_report(metrics, len(records)), encoding="utf-8")
    log.info("built %d cards; recall@4=%s (dev n=%d)", len(cards),
             metrics["recall@4"], metrics["n_dev_evaluated"])
    return metrics


def main() -> None:
    run()


if __name__ == "__main__":
    main()
