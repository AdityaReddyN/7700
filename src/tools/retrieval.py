"""M5: `retrieve_cases` over the BM25 knowledge-base index (ARCHITECTURE §3.5).

The KB index is built in M6; until it exists this tool reads an optional
`index.json` and returns an empty list when it is absent (D-032). Retrieved text
is data, not instructions (AGENTS non-negotiable #7) — the caller's prompt says
so. Each returned card is citable by `case:<card_id>`.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from rank_bm25 import BM25Okapi

from common.ids import hash8, ref_case

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tok(text: str) -> list[str]:
    return _TOKEN_RE.findall(str(text).lower())


def _snippet(text: str, limit: int = 160) -> str:
    text = " ".join(str(text).split())
    first = re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0]
    return first if len(first) <= limit else first[:limit].rstrip() + "…"


@dataclass
class Card:
    card_id: str
    label: str
    title: str
    text: str


def load_cards(kb_dir: Path) -> list[Card]:
    """Load cards from `<kb_dir>/index.json` (list of {card_id,label,title,text}).

    Returns an empty list if the index is absent, so the tool degrades cleanly
    before M6 builds it.
    """
    index = Path(kb_dir) / "index.json"
    if not index.exists():
        return []
    data = json.loads(index.read_text(encoding="utf-8"))
    return [Card(c["card_id"], c.get("label", ""), c.get("title", ""), c.get("text", ""))
            for c in data]


class CaseRetriever:
    """BM25 over case cards. Empty retriever returns no results."""

    def __init__(self, cards: list[Card]) -> None:
        self.cards = list(cards)
        self._bm25 = BM25Okapi([_tok(f"{c.title} {c.text}") for c in self.cards]) \
            if self.cards else None

    @classmethod
    def from_kb(cls, kb_dir: Path) -> CaseRetriever:
        return cls(load_cards(kb_dir))

    def search(self, query: str, hypothesis: str, k: int = 4) -> list[dict]:
        if not self.cards or self._bm25 is None:
            return []
        tokens = _tok(f"{query} {hypothesis}")
        if not tokens:
            return []
        scores = self._bm25.get_scores(tokens)
        if float(scores.max()) > 1e-9:
            # Normal case: BM25 has positive signal. Rank by it, keep positives.
            rank = [-scores[i] for i in range(len(self.cards))]
            kept = [scores[i] > 1e-9 for i in range(len(self.cards))]
        else:
            # BM25 is degenerate here: every query term is common across this tiny
            # corpus, so its IDF is <= 0 and containing a term LOWERS the score.
            # Fall back to shared-token overlap, where a match never hurts.
            qset = set(tokens)
            overlap = [len(qset & set(_tok(f"{c.title} {c.text}"))) for c in self.cards]
            if max(overlap) == 0:
                return []
            rank = [-o for o in overlap]
            kept = [o > 0 for o in overlap]
        order = sorted(range(len(self.cards)), key=lambda i: (rank[i], self.cards[i].card_id))
        out = []
        for i in order[: max(0, int(k))]:
            if not kept[i]:
                break
            c = self.cards[i]
            out.append({"card_id": c.card_id, "label": c.label, "title": c.title,
                        "snippet": _snippet(c.text)})
        return out


def retrieve_cases(retriever: CaseRetriever | None, alert_id: str, *, query: str,
                   hypothesis: str, k: int = 4) -> tuple[dict, str, list[tuple[str, dict]]]:
    """Return (model_output, ref_id, extra_entries).

    `extra_entries` are per-card (`case:<card_id>`, card) pairs the registry also
    logs so the verifier can resolve evidence that cites a specific card.
    """
    cases = retriever.search(query, hypothesis, k) if retriever is not None else []
    output = {"cases": cases}
    ref_id = f"case:q:{hash8({'query': query, 'hypothesis': hypothesis, 'k': k})}"
    extra = [(ref_case(c["card_id"]), c) for c in cases]
    return output, ref_id, extra
