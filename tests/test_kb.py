"""M6 knowledge-base tests: hermetic, synthetic fixtures, no network/models."""

from __future__ import annotations

import re

import numpy as np
import pandas as pd
import yaml

from common.schemas import LABELS
from kb import build_index as bi
from kb.cards import generate_cards, select_kb_scenarios
from tools.retrieval import Card, CaseRetriever

_T = 1_575_849_600
_COLS = ["time", "icao24", "lat", "lon", "velocity", "heading", "vertrate",
         "callsign", "squawk", "baroaltitude", "geoaltitude"]
_MS_PER_DEG_LAT = 111_320.0


def _straight(icao, n=40, v_ms=200.0, t0=0, reported=None, callsign="DLH1", squawk="1000"):
    dlat = (v_ms * 10.0) / _MS_PER_DEG_LAT
    return pd.DataFrame({
        "time": t0 + np.arange(n) * 10, "icao24": icao,
        "lat": 50.0 + np.arange(n) * dlat, "lon": 8.0,
        "velocity": v_ms if reported is None else reported,
        "heading": 0.0, "vertrate": 0.0, "callsign": callsign, "squawk": squawk,
        "baroaltitude": 10000.0, "geoaltitude": 10000.0,
    })[_COLS]


def _track_for(label: str, icao: str) -> pd.DataFrame:
    """Synthetic track whose computed stats are distinctive per label."""
    if label == "position_spoofing":           # implied 200, reported 120 -> big residual
        return _straight(icao, reported=120.0)
    if label == "ghost_aircraft":              # self-consistent, no identity
        return _straight(icao, callsign=pd.NA, squawk=pd.NA)
    if label == "replay_duplicate":            # duplicate position far away
        base = _straight(icao, n=30)
        dup = base.copy()
        dup["time"] = dup["time"] + 2
        dup["lat"] = dup["lat"] + 1.5
        return pd.concat([base, dup], ignore_index=True)
    if label == "sensor_fault":                # dropout -> big gap
        return _straight(icao, n=40).drop(index=range(15, 30)).reset_index(drop=True)
    return _straight(icao, v_ms=180.0)          # benign: quiet, consistent


def _catalog(with_test=False):
    scen = []
    sid = 1
    for lab in LABELS:
        for _ in range(2):
            scen.append({"scenario_id": f"S{sid:04d}", "label": lab, "split": "kb",
                         "icao24": f"kb{sid:03d}", "t_start": _T, "t_end": _T + 390})
            sid += 1
    for lab in LABELS:  # dev
        scen.append({"scenario_id": f"S{sid:04d}", "label": lab, "split": "dev",
                     "icao24": f"dev{sid:03d}", "t_start": _T, "t_end": _T + 390})
        sid += 1
    if with_test:
        scen.append({"scenario_id": "S9001", "label": "sensor_fault", "split": "test",
                     "icao24": "tst001", "t_start": _T, "t_end": _T + 390})
    return {"scenarios": scen}


def _loader(scn):
    return _track_for(scn["label"], scn["icao24"])


# --- card generation -------------------------------------------------------

def test_generates_ten_cards_two_per_label(tmp_path):
    cards = generate_cards(_catalog(), _loader, tmp_path / "cards")
    assert len(cards) == 10
    counts = {lab: sum(c["label"] == lab for c in cards) for lab in LABELS}
    assert all(counts[lab] == 2 for lab in LABELS)
    assert [c["id"] for c in cards] == [f"C{i:03d}" for i in range(1, 11)]
    for c in cards:
        assert c["synthetic"] is True and c["source_split"] == "kb"
        assert c["title"] and c["signature"] and c["differentiators"] and c["outcome"]


def test_card_files_have_frontmatter_and_no_scenario_ids(tmp_path):
    generate_cards(_catalog(with_test=True), _loader, tmp_path / "cards")
    for path in (tmp_path / "cards").glob("C*.md"):
        raw = path.read_text(encoding="utf-8")
        assert raw.startswith("---")
        meta = yaml.safe_load(raw.split("---", 2)[1])
        assert {"id", "label", "title", "signature", "differentiators",
                "outcome", "synthetic", "source_split"} <= set(meta)
        assert not re.search(r"\bS\d{4}\b", raw)  # no scenario ids in the card


def test_generation_is_deterministic(tmp_path):
    a = generate_cards(_catalog(), _loader, tmp_path / "a")
    b = generate_cards(_catalog(), _loader, tmp_path / "b")
    assert a == b
    for cid in [f"C{i:03d}.md" for i in range(1, 11)]:
        assert (tmp_path / "a" / cid).read_text() == (tmp_path / "b" / cid).read_text()


def test_only_kb_scenarios_are_read(tmp_path):
    seen = []

    def spy(scn):
        seen.append(scn["scenario_id"])
        return _loader(scn)

    cat = _catalog(with_test=True)
    generate_cards(cat, spy, tmp_path / "cards")
    kb_ids = {s["scenario_id"] for s in cat["scenarios"] if s["split"] == "kb"}
    assert set(seen) == kb_ids  # no dev/test scenario was ever loaded


def test_select_kb_is_sorted_and_kb_only():
    kb = select_kb_scenarios(_catalog(with_test=True))
    assert len(kb) == 10 and all(s["split"] == "kb" for s in kb)
    assert kb == sorted(kb, key=lambda s: (LABELS.index(s["label"]), s["scenario_id"]))


# --- index + parsing -------------------------------------------------------

def test_build_index_schema_and_roundtrip(tmp_path):
    cards_dir = tmp_path / "kb" / "cards"
    generate_cards(_catalog(), _loader, cards_dir)
    records = bi.build_index(cards_dir, tmp_path / "kb" / "index.json")
    assert len(records) == 10
    for r in records:
        assert set(r) == {"card_id", "label", "title", "text"}
        assert r["card_id"].startswith("C") and r["text"]
    parsed = bi.parse_card(cards_dir / "C001.md")
    assert parsed["card_id"] == "C001" and parsed["label"] in LABELS


def test_case_retriever_from_kb_loads(tmp_path):
    cards_dir = tmp_path / "kb" / "cards"
    generate_cards(_catalog(), _loader, cards_dir)
    bi.build_index(cards_dir, tmp_path / "kb" / "index.json")
    r = CaseRetriever.from_kb(tmp_path / "kb")
    assert len(r.cards) == 10
    hits = r.search("duplicatepositions positionjump", "", k=4)
    assert hits and any(h["label"] == "replay_duplicate" for h in hits)


# --- recall@4 --------------------------------------------------------------

class _FakeRetriever:
    """Returns controlled hits per query, to test recall counting in isolation."""

    def __init__(self, table):
        self._table = table  # query -> list of label strings (ranked)

    def search(self, query, hypothesis, k=4):
        labels = self._table.get(query, [])
        return [{"card_id": f"X{i}", "label": lab} for i, lab in enumerate(labels[:k])]


def test_recall_eval_known_result():
    retr = _FakeRetriever({
        "q_pos": ["position_spoofing", "sensor_fault"],   # correct at rank 1
        "q_sensor": ["ghost_aircraft", "sensor_fault"],   # correct at rank 2
        "q_ghost": ["benign_anomaly", "replay_duplicate"],  # never correct
    })
    dev = [{"label": "position_spoofing"}, {"label": "sensor_fault"},
           {"label": "ghost_aircraft"}]
    qmap = {"position_spoofing": "q_pos", "sensor_fault": "q_sensor",
            "ghost_aircraft": "q_ghost"}
    m = bi.recall_eval(dev, retr, lambda s: (qmap[s["label"]], True), k=4)
    assert m["n_dev_evaluated"] == 3 and m["n_dev_skipped"] == 0
    assert m["recall@1"] == 1 / 3   # only position at rank 1
    assert m["recall@2"] == 2 / 3   # position + sensor within top 2
    assert m["recall@4"] == 2 / 3
    assert m["per_label"]["position_spoofing"]["recall@1"] == 1.0
    assert m["per_label"]["ghost_aircraft"]["recall@4"] == 0.0


def test_recall_eval_skips_empty_query():
    retr = CaseRetriever([Card("C1", "sensor_fault", "t", "dropout gap noise")])
    m = bi.recall_eval([{"label": "sensor_fault"}], retr, lambda s: ("", False), k=4)
    assert m["n_dev_evaluated"] == 0 and m["n_dev_skipped"] == 1
    assert m["recall@4"] is None


def test_recall_eval_integration_with_generated_cards(tmp_path):
    cat = _catalog()
    cards_dir = tmp_path / "kb" / "cards"
    generate_cards(cat, _loader, cards_dir)
    bi.build_index(cards_dir, tmp_path / "kb" / "index.json")
    retr = CaseRetriever.from_kb(tmp_path / "kb")
    dev = [s for s in cat["scenarios"] if s["split"] == "dev"]
    m = bi.recall_eval(dev, retr, bi._scenario_query(_loader), k=4)
    assert m["n_dev_evaluated"] == 5
    assert m["recall@4"] is not None and m["recall@4"] > 0.0
