# Knowledge-base retrieval report (M6)

BM25 over **10 case cards** (2 per label, from KB-split scenarios only). Dense embeddings, RRF and reference passages are deferred (D-033).

Evaluated **15** dev scenarios (0 skipped), top-4 retrieval per query. The query is built from each scenario's computed stats with no label; the true label is compared only after retrieval.

- recall@1: **33%**
- recall@2: **53%**
- recall@4: **73%**

## Per label

| label | n | recall@1 | recall@2 | recall@4 |
|---|---|---|---|---|
| position_spoofing | 3 | 67% | 67% | 100% |
| ghost_aircraft | 3 | 0% | 100% | 100% |
| replay_duplicate | 3 | 100% | 100% | 100% |
| sensor_fault | 3 | 0% | 0% | 33% |
| benign_anomaly | 3 | 0% | 0% | 33% |

**Expected high — only 10 cards.** The index is deliberately tiny, so high recall is unsurprising and establishes neither generalisation nor anomaly-detection quality; it only checks that a correct-label card is reachable from a scenario's computed profile. The M5 tools do not expose identity *presence*, so `ghost_aircraft` reads as a quiet track and may retrieve less reliably.

**Quiet classes and the tie-break.** Quiet classes (`ghost_aircraft`, `benign_anomaly`) produce near-identical computed profiles, so several cards tie on the retrieval score and ranking falls to the deterministic `card_id` tie-break. The reported `ghost_aircraft` recall@4 of 1.0 is therefore partly a tie-break artifact — ghost cards happen to sort ahead of `benign_anomaly` cards under equal scores — and does **not** demonstrate strong retrieval discrimination for quiet classes, especially `ghost_aircraft` versus `benign_anomaly`.

_Numbers from this run; see `results/kb/recall_at4.json`._
