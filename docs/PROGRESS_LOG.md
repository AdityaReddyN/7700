# Progress log

Newest entries at the bottom. Each entry: date, milestone, what was done, tests and results, time per investigation if relevant, spend (local or hosted), deviations, next step, questions.

## 2026-10-27: Project initialised
- Original docs created. No code.

## 2026-10-29: Scope reset and context pack
- Scope cut to five labels, local-first inference, Streamlit app, 25-case test set. See DECISIONS.md D-010 to D-022.
- Ollama installed on the Lenovo Yoga. `llama3.1:8b` measured: 8.29 tokens/s generation, 37.23 tokens/s prompt evaluation.
- Modal balance is $1. Hosted calls limited to a few demonstration cases.
- Open gates: G1 (Llama eligibility), G2 (OpenSky permission), G3 (hourly CSV).
- Next step: M0 setup, then M1 smoke tests.

## 2026-11-01: M0 setup

Plan:
1. Create the repo skeleton from AGENTS.md section 6 (src packages, tests, data/kb, results).
2. Add `pyproject.toml` with pinned deps verified on the laptop; src layout, ruff + pytest config.
3. Add the Makefile with all section-6 targets; future-milestone targets point at their modules.
4. Write `src/common`: schemas (ARCHITECTURE 5 + ToolResult), ids/ref_ids, JSONL logging, YAML+.env config.
5. Write tests for schemas, ids, config, logging and a package-import smoke test.
6. Use a project `.venv`; run `make setup` then `make test`; stop at M0 for human confirmation before M1.

What was built: repo scaffold, Makefile, pyproject (pinned), `common` modules, 5 test files, README stub, .gitkeep for committed empty dirs. `.gitignore` now also covers `.venv/` and build artifacts.

Deviations: (a) `make` is not installed on Windows; used the existing GNU Make 3.82 (`mingw32-make`) and copied it to `make.exe` on PATH so `make` works. (b) Created a `.venv` at the human's request; `make setup` creates/uses it. (c) Added a root `README.md` stub (full README is M10) so the repo is not README-less.

Tests and results: `make setup` installed the pinned stack into `.venv` (exit 0). `make test` → 30 passed (schemas, ids, config, logging, package-import smoke). `make lint` (ruff) → clean.

Next step: await human confirmation, then M1 (Ollama smoke tests).

## 2026-11-01: Context-pack sync (gates resolved)

- Applied the human's documentation/config changelog: G1 accepted (Llama eligible, primary `llama3.1:8b`), G2 received, G3 partial (four days, one inspected). Updated AGENTS.md (gate table, model-gate logic, section 4 Glimmer bullet, section 5 stack, section 6 layout adds `docs/permissions/`, section 10 questions, line 3 stale phrase removed).
- `config/models.yaml`: added optional off-by-default `comparison` (Glimmer) block. `config/scenarios.yaml`: added `day_split` (by_day, null day lists) and replay `window_copy_offset_min` → `[10, 360]`.
- Docs: DATA_SPEC (G2 resolved, four-day coverage, day-split note), SCENARIO_SPEC (replay offset + same-day-group rule, day-based split in §6, leakage now covers replay source windows and dev scenarios), API_NOTES (Llama accepted), PROJECT_CONTEXT (Llama accepted), DEMO (narration names Llama primary), ROADMAP (G1/G2 done, G3 partial).
- DECISIONS: added D-023 (gates, settles D-011), D-024 (day split, proposed/default), D-025 (optional Glimmer comparison, off), D-026 (replay offsets). Renumbered the earlier Windows-build entry from D-023 to **D-027** to avoid an id collision (log rule: ids unique, entries not deleted).
- New `docs/permissions/` folder: README plus G1-llama.md and G2-opensky.md placeholders for the actual replies.
- `make test`: 30 passed. `make lint`: clean. No code changed; M0 still green.

## 2026-11-01: M1 model gate

Decisions in: D-028 (local Llama only, no third-party hosts, Glimmer declined), D-029 (raw data is one day 2019-12-09, 24 hourly `.csv.tar`; day-split falls back to hour-based). Propagated to AGENTS, config, DATA_SPEC, SCENARIO/PROJECT_CONTEXT, ROADMAP, API_NOTES.

Plan:
1. Confirm environment: Ollama present; `llama3.1:8b` and `llama3.2:3b` pulled (both present, 3 days old). Glimmer not pulled (and not needed, D-028).
2. Build `src/agents/llm.py`: a thin Ollama chat client (openai SDK → `http://localhost:11434/v1`, temperature 0, fixed seed) plus a `--smoke` CLI. Keep the full M7 wrapper for later.
3. Write 20 neutral hand-written dev prompts (no labels/scenario ids) in `src/agents/prompts/` for the tool-call and structured-output checks; add minimal OpenAI-format specs for the five tools (ARCHITECTURE §3).
4. Smoke checklist (API_NOTES §5): plain completion (timed, temp 0), tool-call validity ×20, `HypothesisReport` structured-output parse rate ×20, tokens/s, free RAM (psutil) + `ollama ps`, endpoint check. Write `results/smoke/<date>.json`.
5. Run on `llama3.1:8b` and `llama3.2:3b`; long run in the background (CPU ~8 tok/s). Record results in API_NOTES with the date.
6. Add a hermetic unit test (mocked client) so `make test` needs no Ollama; keep `make lint` clean.

Built: `src/agents/tool_specs.py` (5 tool schemas), `src/agents/prompts/dev_prompts.py` (20 neutral, leakage-checked prompts), `src/agents/llm.py` (thin Ollama client + `make smoke`). Added `tests/test_smoke_harness.py` (hermetic). Pinned `psutil==6.1.1`.

Tests and results: `make test` → 36 passed; `make lint` clean. Full smoke (`results/smoke/2026-11-01.json`, both models × 20 prompts) ran in the background in ~20 min:
- Endpoint, native tool calling, and JSON structured output all work via the `openai` SDK; `ollama ps` = 100% CPU for both.
- `llama3.1:8b` (primary): structured 20/20; tool-call 11/20 (9 fails = integer timestamps sent as strings); plain 1.82 tok/s.
- `llama3.2:3b` (triage): tool-call 20/20; structured 19/20; plain 4.36 tok/s.
- Speeds low due to memory pressure (0.6–1.4 GB free); re-measure with apps closed.

Deviations: Glimmer not tested (D-028). Speeds below the apps-closed baseline. M5 tool registry must coerce numeric-string args (8B quirk, logged in API_NOTES §6).

M1 done-criteria: Ollama + both models present; smoke run and recorded; G1 answered (yes) and primary set in config/models.yaml. M1 complete.

Next step: await confirmation, then M2 (convert the 2019-12-09 `.csv.tar` files to Parquet and write the data report).

## 2026-11-01: M2 data conversion and report

Schema verification (step 1): the raw files are tar → gzip → CSV (each tar also holds OpenSky `LICENSE.txt`/`README.txt`). The 16-column header matches DATA_SPEC §3 exactly; no schema deviation. One correction logged in DATA_SPEC §2 (format is tar→gz→csv, not a plain CSV in a tar).

Plan:
1. Done: verify the hour-00 header and the nested format; confirm it matches DATA_SPEC §3.
2. `src/data/convert.py` (Makefile `data`): per hour, untar → gunzip → pandas (typed; booleans mapped, callsign stripped, squawk string); cleaning per DATA_SPEC §4 (drop only icao24/time-null rows; keep feature-null rows); write `data/parquet/states/date=2019-12-09/hour=HH/part-0.parquet` sorted by icao24, time. Emit `results/data_report/convert_manifest.json` with SHA-256, sizes, rows before/after, null counts before/after.
3. `src/data/report.py` (Makefile `report`): read the manifest + Parquet (DuckDB) → `results/data_report/report.md` + `summary.json` (coverage, rows before/after, null rates, aircraft/hour, median snapshots/aircraft, flag shares, OpenSky attribution + G2 note).
4. Hermetic tests: synthetic tar→gz→csv fixture; assert parquet output, dtypes, partition path, cleaning drops only icao24/time-null rows; report assembles from a small parquet + manifest.
5. Run convert in the background (24 files, tight RAM) then report; record actual numbers here.

Memory: one hour at a time; sort within the hour. If a single hour OOMs under current low free RAM, chunk the read.

Results (M2 complete, 2026-11-01):
- Converted all 24 hours → `data/parquet/states/date=2019-12-09/hour=HH/` (1.5 GB, gitignored). ~14 s/hour; no OOM.
- `results/data_report/report.md` + `summary.json` + `convert_manifest.json` written (committed deliverable).
- Coverage: 2019-12-09 00:00:00 → 23:59:50 UTC (86,390 s, full day).
- Rows: 54,142,793 before and after cleaning; **0 rejected** (icao24 and time never null).
- Aircraft: 44,879 distinct; median 726 snapshots/aircraft.
- Null rate after cleaning: lat/lon 11.4%, velocity/heading 13.0%, vertrate 12.8%, callsign 9.0%, baroaltitude 7.5%, geoaltitude 18.9%, squawk 9.3%, time/icao24 0%.
- Flag share (reported, not features): onground 7.6%, alert 2.1%, spi 1.4%.
- Note: this day is far larger and less null-heavy than the old 2017 one-hour sample (31% null lat/lon) — the figures were re-measured, not assumed.

Tests/lint: `make test` 37 passed, `make lint` clean. DuckDB report over 54M rows ran in ~5 s.

M2 done-criteria met: hourly files converted to Parquet; data report with rows before/after, null rates, time coverage, aircraft counts. M2 complete.

Next step: await go for M3 (50 labelled scenarios, hour-based splits, leakage test).

## 2026-11-01: M3 scenarios, splits, leakage test

Data recon (step 1): the store is on a **10 s cadence** (median dt 10 s), up to 360 points/aircraft/hour; hour 12 has ~9,800 airborne aircraft with non-null lat/lon/velocity/heading, median 178 points each. Multi-minute windows give ample points for every injector.

Split (D-029 hour-based fallback), set in config/scenarios.yaml: kb = hours 00–05, dev = 06–11, test = 12–23 (disjoint). A scenario draws sources only from its group's hours; replay sources stay in-group.

Plan:
1. Done: recon cadence/density; set hour groups.
2. `scenarios/select.py`: deterministic candidate source tracks per group (airborne, non-null fields, enough contiguous 10 s points).
3. `scenarios/inject.py`: fresh injectors — position_spoofing (drift/jump/velocity_offset), ghost_aircraft (new icao24), replay_duplicate (window_copy/address_duplicate), sensor_fault (noise/dropout/stuck/jitter) + hard variants. Params from config; per-scenario seed.
4. `scenarios/benign.py`: rule-found holding/go-around + Matplotlib plots, marked provisional for the human eye-check.
5. `scenarios/split.py`: assemble 50 (10/label: 2 kb/3 dev/5 test), difficulty ~⅓ each; write data/scenarios/tracks.parquet + splits.json + scenarios catalog. alert_map.json comes in M4 (needs alerts).
6. `tests/test_leakage.py` + injector determinism/signature unit tests.
7. Generate, record actual counts + benign count; test + lint green.

Results (M3 complete, 2026-11-02):
- Built: `scenarios/select.py`, `inject.py`, `benign.py`, `split.py`, `leakage.py`. Makefile `scenarios` → `scenarios.split`.
- 50 scenarios, 10 per label, splits 2 kb / 3 dev / 5 test each. `data/scenarios/tracks.parquet` (3,348 rows, **no label column**) + `splits.json` catalog. Benign plots in `data/scenarios/benign_plots/` (gitignored).
- Difficulty: 12 easy / 22 medium / 16 hard (synthetic labels 3/3/4 each; benign uniformly "medium" — found anomalies aren't meaningfully gradeable). Position modes drift 4 / jump 3 / velocity_offset 3; replay window_copy 5 / address_duplicate 5.
- Benign: 10 holding patterns found by rule (turn ≥360°, radius <5 nm), 1 marked confounder. **Eye-checked and confirmed by the human on 2026-11-02** (plots reviewed); `provisional_eye_check` set to false in splits.json.
- Leakage test passes: disjoint hour groups, no cross-split aircraft/window overlap, replay source windows stay in-group, no test ids in `data/kb`, tracks/Alert carry no label.
- Tests: `make test` 55 passed (incl. injector determinism/signatures + hermetic leakage); `make lint` clean.

Notes for later:
- **M5 `check_identity`**: `address_duplicate` uses a few-second time shift (SCENARIO_SPEC §4.3), so "duplicate position, same time" needs a small time tolerance (e.g., ≤5 s), not exact-equal timestamps.
- `alert_map.json` (alert_id→scenario_id) is produced in M4 once alerts exist.
- Benign difficulty left uniform; revisit if the detector needs graded benign cases.

Next step: human confirms the benign holdings (eye-check); then M4.

## 2026-11-02: M4 detector (Isolation Forest primary, rule-based fallback)

Owner decision D-030: IsolationForest is the primary detector; the rule-based flagger is the fallback (selectable in `config/detector.yaml`). All docs updated. Fixed the stale AGENTS §2 G3 row (now RESOLVED, one day 2019-12-09 per D-029).

Plan:
1. Done: flip design in all docs; add `config/detector.yaml`; log D-030.
2. `detector/features.py`: per-window features (implied-vs-reported speed residual, largest jump, max gap, missing fraction, duplicate-position pairs with ≤5 s tolerance, vertrate/altitude mismatch, position scatter, callsign/squawk changes).
3. `detector/baseline.py` + `model.py`: sample real normal tracks (seeded, scenario aircraft excluded) → feature matrix; fit IsolationForest (random_state 42) and per-feature z-score stats; rule scorer as fallback.
4. `detector/flagger.py`: score a track (IF or rules), pick threshold on DEV to hit target recall, build `Alert` (no label/scenario_id; top_features from extreme z-scores).
5. `detector/alerts.py` (Makefile `alerts`): run over scenarios → alerts + `alert_map.json`; alert rate on a disjoint real sample; write `results/detector/metrics.json` + `report.md` (per-class recall, precision, benign flag rate, real alert rate; test scored once).
6. Tests: features on synthetic tracks, deterministic threshold, Alert carries no label, metrics math; extend leakage to built alerts.
7. Run, record metrics (small-sample caveats), test + lint green.

### M4 results

Built `src/detector/` (features, baseline, model, flagger, alerts) + 14 hermetic tests. Full suite 69 pass, ruff clean. 12 features per window; baseline = 3000 real airborne windows from dev-group hours (6–11), disjoint from test hours.

First run tuned the threshold to a 0.80 dev-recall target: 0.85 test recall but **61% of real traffic flagged** — unusable. Subtle `position_spoofing` (hard drift / near-unity velocity scale) and some `sensor_fault` windows score inside the normal-traffic bulk, so forcing recall drags the threshold into it. Changed the operating point to a **false-positive budget on normal dev-hour traffic** (flag the top 5%); logged as **D-031**. Recall is now reported at that operating point, not targeted.

Final numbers (all in `results/detector/`, small samples — dev 12+3, test 20+5):

| Detector | Threshold | Real alert rate | Benign FP | Test recall | Precision |
|---|---|---|---|---|---|
| **Isolation Forest** (primary) | 0.0474 | **4.7%** (94/2000) | 0% | 50% (10/20) | 100% |
| Rule-based (baseline, `--method rules`) | 50.0 (z cap) | 56% | 40% | 75% | 88% |

IF test per-class recall: `ghost_aircraft` 100%, `replay_duplicate` 100%, `sensor_fault` 0%, `position_spoofing` 0%. The detector reliably catches the two blatant classes at a believable alert rate with zero benign false positives; subtle position/sensor injections are a **feature-space limit, not a threshold one** (no sane threshold separates them). The downstream agents/tools are meant to do the nuanced work; the detector is deliberately simple.

Rule-based baseline (`results/detector/baseline_rules/`): **cannot hit the 5% budget** — several features are zero-inflated in normal traffic (MAD 0), so the robust z saturates at the cap (50) for any nonzero value and the budget quantile collapses to the cap. It catches more classes (position 20%, sensor 80%) only by flagging 56% of all traffic. This cleanly justifies D-030 (IF primary, rules as baseline). Not re-tuned — roadmap cut-order #1 says stop there.

Added a `--method/--tag` CLI to `detector.alerts` so the baseline writes to a separate results folder without touching the primary `alerts.json`/`alert_map.json`.

Deviations: D-031 (operating point = FP budget). Next step: M5 (five read-only tools + ToolLog); the detector's weak position/sensor recall is context for M5/M7 (the agents investigate what is flagged).

## 2026-11-02: M5 tools + ToolLog (plan)

Build the five read-only, deterministic tools (ARCHITECTURE §3) and the ToolLog (§4). Approved to ship `retrieve_cases` now degrading-to-empty until the M6 index exists.

1. `src/tools/toollog.py`: `ToolLog` maps `ref_id -> ToolResult` (full output kept for the verifier); identical tool+args return the same cached `ref_id`; model-facing view returns the truncated output. Enforces the size rule (`tool_output_max_chars` from `config/agents.yaml`, 1600) and sets `truncated`.
2. `src/tools/data_tools.py`: `TrackProvider` resolves the alert's own track by `icao24`+window from the scenario view (`tracks.parquet`) if rows exist there, else the real Parquet store — never via `scenario_id`/`alert_map`, so nothing leaks. Four tools: `get_track_window`, `compute_kinematics`, `check_identity` (on the alert track), `compare_to_baseline` (deterministic same-hour real aggregate via DuckDB `quantile_cont`, excluding scenario aircraft, cached). Reuses `detector/features.py` helpers.
3. `src/tools/retrieval.py`: `retrieve_cases` over the BM25 KB index; returns empty if the index is absent (M6 builds it).
4. `src/tools/registry.py`: dispatch `call(name, args) -> ToolResult` through the ToolLog; imports `TOOL_SPECS`/`TOOL_NAMES` from `agents/tool_specs.py` (unchanged, keeps the M1 smoke working).
5. Tests (`tests/test_tools.py`, hermetic): per-tool values on synthetic tracks, `ref_id` determinism, size bound + `truncated`, ToolLog dedup and full-vs-truncated. Extend `tests/test_leakage.py`: no `S\d{4}`/label/split string in any serialised `ToolResult.output`.
6. Decision D-032 (track resolution; deterministic same-hour baseline; retrieve_cases degrades to empty). Caps and native-vs-text tool-calling are M7, not M5.

Next step: implement, then `make test`/`make lint` green and report.

## 2026-11-02: M6 knowledge base — case cards + BM25 index (plan)

Cards + BM25 only (dense/RRF, reference passages, triage, agents all deferred). Cards are generated from the 10 KB-split scenarios using the M5 tools (`kinematics`, `identity`, `window_summary`) — computed numbers only, no memory, no test/dev stats.

1. `src/kb/cards.py`: select the 10 KB scenarios deterministically (sorted by label, scenario_id) -> C001..C010. For each, load its track from `tracks.parquet` and compute stats with the M5 tools. Write `data/kb/cards/C0NN.md` as YAML frontmatter (id, label, title, signature, differentiators, outcome, synthetic:true, source_split:kb) + a prose body. A shared `describe_stats()` turns the computed numbers into the card prose and (label-free) the recall query, so retrieval keys on measured signal. `outcome` is computed-derived (track span / max step / max gap), not the injection param — documented.
2. `src/kb/build_index.py` (Makefile `kb`): parse the cards, write `data/kb/index.json` in the M5 retriever schema (`card_id,label,title,text`), build a `CaseRetriever.from_kb`, run recall@4 on dev, write `results/kb/recall_at4.json` + `report.md`. Deterministic and rerunnable.
3. recall@4: for each dev scenario, query = `describe_stats` of its own computed stats (label-free); retrieve top 4; a hit counts if a card with the scenario's true label is in the top k. True label used only after retrieval. Report recall@1/2/4, per-label, counts, caveat "Expected high — only 10 cards."
4. Tests (`tests/test_kb.py`, hermetic, synthetic loader): 2 cards/label, required fields, synthetic/source_split, no `S\d{4}` in cards, frontmatter round-trip, index schema, recall math on a synthetic index, `CaseRetriever.from_kb`, deterministic selection. Extend `tests/test_leakage.py` to run `check_no_test_ids_in_kb` over generated `data/kb/`.
5. D-033 logged. Reference passages = none in M6 (said so). Known limit: the three tools do not expose identity *presence*, so ghost_aircraft looks "quiet" to retrieval — recall reported honestly per label.

Next step: implement, `make kb`, full suite + lint green, report (no commit until authorised).

### M6 results

Built `src/kb/cards.py` + `build_index.py`; generated `data/kb/cards/C001..C010.md` (2 per label, from the 10 KB scenarios' computed stats via the M5 tools), `data/kb/index.json`, and `results/kb/{recall_at4.json,report.md}`. 18 new KB/leakage tests; full suite 95 pass, ruff clean.

Retrieval signal: cards and the (label-free) recall query share conditional `signal_tokens` computed from the stats (residualhigh, positionjump, duplicatepositions, coveragegap, missingsamples, identitychange, residualrising, consistentkinematics, regularsampling). Found and fixed an M5 `CaseRetriever` defect: BM25 IDF goes <= 0 for tokens common across a 10-card corpus, so the old `score>0` cut returned nothing (or inverted rankings) for quiet, common-token queries. Fixed minimally: BM25 stays primary; when it has no positive signal, fall back to shared-token overlap (a match never lowers a card's rank). No interface change; M5 tool tests still pass.

Recall on dev (n=15, label-free queries, true label compared only after retrieval):
- recall@1 0.33, recall@2 0.53, **recall@4 0.73**.
- per-label recall@4: position_spoofing 1.0, ghost_aircraft 1.0, replay_duplicate 1.0, sensor_fault 0.33, benign_anomaly 0.33.

Honest caveats (in `results/kb/report.md`): only 10 cards, so high recall is expected and proves neither generalisation nor detection quality. The three tools expose no identity *presence* and smear subtle residual, so quiet classes (ghost/benign) and multi-modal sensor_fault separate weakly; quiet-class ranking leans on near-identical fingerprints and is close to chance. Reference passages and dense/RRF deferred (D-033).

Next step: M7 (LLM wrapper, triage, subagent loop, verifier, adjudicator, orchestrator).

## 2026-11-02: M7 agents — wrapper, triage, subagent, verifier, adjudicator, orchestrator (plan)

Build the agent pipeline on top of the M5 tools (`ToolRegistry`) and M6 retrieval. Local Llama only (D-028). Configs A and D from `config/ablations.yaml`; thresholds and caps from `config/agents.yaml`; models from `config/models.yaml`. No scenario id / label / split in any prompt, tool output or alert (leakage test extended).

1. `src/agents/llm.py`: add `LLMResult` + `class LLMClient` with `async complete(stage, messages, *, tools, response_schema, max_tokens, timeout_s)` (ARCHITECTURE §6). Resolves the stage's model from `models.yaml`; native Ollama tool-calling (measured working), `response_format=json_object` + schema-in-prompt validated with Pydantic, one retry on parse failure with the error fed back; logs one JSONL line per call (stage, model, tokens, latency_s, tool_calls_count, tool_call_valid, parse_ok, cost_usd=0, alert_id, config); hosted spend-cap check (local = $0, never trips). Sync core wrapped via `asyncio.to_thread`; keep the M1 `--smoke` path.
2. `src/agents/prompts/*.v1.md` + `cheatsheet.py`: versioned prompt files (preamble, triage, subagent, subagent_config_a, adjudicator) from PROMPT_SPECS; placeholders filled by `str.replace` (JSON braces stay literal). Cheat sheet = label-free definitions/supports/refutes.
3. `src/agents/triage.py`: one model call, no tools, parse `Triage`; keep prior >= 0.15, >= 3 and <= 5 (top-3 if fewer pass). Failure -> rule-based priors from the alert's top features, fallback recorded.
4. `src/agents/subagent.py`: native tool-call loop through `ToolRegistry`; <= N tool calls (4 for D, 8 for config A); force a final structured `HypothesisReport`; parse fail -> retry once -> inconclusive; any exception -> inconclusive with a note. `run_single_agent` (config A) returns the top report + alternatives.
5. `src/agents/verifier.py`: pure Python (no model). Per `Evidence`: ref in ToolLog (else `missing_ref`); if stat+value, stat is a key (nested) in the full logged output (else `unknown_stat`) and the value matches within max(5% rel, 0.5 abs) (else `value_mismatch`); stat/value missing -> `verified_partial` (counted apart). Returns the report with `verified` set + per-report counts. Adjudicator sees only verified items.
6. `src/agents/adjudicator.py`: one model call from verified evidence only; `ranked` replaced in code by the verified reports; `evidence_table` built in code; confidence cap 0.9 unless >= 2 independent verified items back the verdict (enforced in code). Failure -> inconclusive `IncidentReport` with the verified evidence and reason.
7. `src/agents/orchestrator.py`: `asyncio` + semaphore (concurrency 1). Config D: triage -> sequential subagents -> verifier -> adjudicator. Config A: single agent -> verifier -> `IncidentReport` directly (no adjudicator call). Per-stage timing + tokens in `meta`; one trace to `runs/<inv_id>/trace.json` (stage names per ARCHITECTURE §8). CLI `run-case` over `data/scenarios/alerts.json`.
8. Tests (`tests/test_agents.py`, hermetic, `FakeLLM`, synthetic provider/retriever): verifier's 7 cases; triage keep-rule + fallback; subagent budget + inconclusive-on-failure; confidence-cap; orchestrator A and D end-to-end produce a valid `IncidentReport` + trace with per-stage timing; leakage — captured prompts carry no label/scenario id/split. Extend `tests/test_leakage.py` if needed.
9. Real smoke after tests: `make run-case` on one real alert for configs A and D with Ollama, per-stage timing recorded. If Ollama is down or too slow on the laptop, report honestly; the hermetic path stays the verified deliverable.

Next step: implement; full suite + ruff green; one real run per config if the laptop allows; log results; D-034. No commit until authorised.

### M7 results

Built the full agent pipeline (D-034): LLM wrapper (`agents/llm.py` `LLMClient.complete`), versioned prompts + label-free cheat sheet, triage (+ rule-based fallback), the bounded subagent tool-loop, the pure-Python verifier (EVALUATION_PROTOCOL §5), the adjudicator (verified-only, 0.9 confidence cap), and the asyncio orchestrator with configs A and D and a `make run-case` CLI. 21 new hermetic agent tests (FakeLLM, synthetic provider); full suite **117 pass**, ruff clean.

Two real bugs surfaced by the first live run and fixed:
- **ToolLog falsy.** An empty `ToolLog` has len 0, so `ToolRegistry`'s `self.log = log or ToolLog(...)` silently replaced the orchestrator's log with a fresh one — traces serialised an empty toollog and `n_tool_calls=0` though tools ran. Fixed to `log if log is not None`. A D-e2e test now guards it.
- **ref_id not visible to the model.** Tool results shown to the model omitted the `ref_id`, so it could not cite real evidence (it hallucinated a card id). The subagent loop now surfaces `{"ref_id", "result"}` per tool result.

Real smoke on one alert (`alert_0a372e…`), `llama3.1:8b`, CPU, **heavy memory pressure (~1 GB free)** — n=1, not an evaluation; numbers in `results/agents/m7_smoke.json`:
- **Config A: completed, 222.6 s (~3.7 min)**, 12 model calls, 7 tool calls. Verdict `position_spoofing`, confidence 0.80. Verified evidence **0**, excluded **2**: the 8B agent spent all 7 tool calls on `retrieve_cases` and cited numbers from card *prose* under wrong stat keys (`median residual` vs the real `residual_kt_median`); the verifier correctly rejected both (`unknown_stat`). The pipeline is behaving as designed — the weakness is 8B tool choice/citation, which is dev-prompt tuning for M8, not a code defect.
- **Config D: did not finish** — it ran past **~38 min / 29 model calls** and was stopped. Over the AGENTS §7 15-min ceiling, so the §7 cut is applied (**D-035**: top-3 hypotheses, 3 tool calls). The dominant cost is 8B prompt-evaluation under memory pressure (API_NOTES: ~1.8 tok/s loaded vs ~8.3 with apps closed). A clean per-investigation D timing and the A-vs-D comparison belong to the **M8** resumable eval, run with other apps closed (AGENTS §4).

Deviations: config D's clean completion/timing is deferred to M8 (hardware-bound, not a pipeline gap). Honest limitation: with 8B under this memory pressure, D is impractical to run inline; M8 must close apps and use `--resume`.

Next step: one completed config-D run with the D-035 caps (apps closed) to confirm the end-to-end D path, then M8 evaluation. No commit until authorised.

### M7 results — config D completed (update)

After fixing a subagent loop non-termination bug, config D now completes on the laptop. Root cause: the tool-call budget counted only *successful* calls, so a subagent whose 8B calls kept raising (valid shape, missing required args) never hit the cap and looped 20+ turns (~200 s each) — the earlier "runaway". Fixed to cap on **attempts**; guarded by `test_subagent_terminates_when_every_tool_call_errors`. Full suite **118 pass**, ruff clean.

Clean run (apps closed, `llama3.1:8b` ~7 tok/s; numbers in `results/agents/m7_smoke.json`), one alert, n=1:
- **Config D: completed in 533.5 s (~8.9 min)** — under the AGENTS §7 15-min ceiling. 13 model calls, 1 unique tool call (subagents hit the same window → ToolLog deduped, confirming the falsy-log fix). Triage ran for real (not fallback) and kept the top-3 (benign_anomaly, position_spoofing, sensor_fault). Verdict **position_spoofing @ 0.85**; **3 verified evidence items, 2 excluded** — with `ref_id` now visible the model cited real refs. Per-stage: triage 29 s, subagents 89/237/131 s, verification ~0 s, adjudication 47 s.
- Config A (earlier, under memory pressure): 222.6 s, verdict position_spoofing, 0 verified / 2 excluded. The two times are not directly comparable (A under load, D apps-closed); the clean A-vs-D comparison is M8.

M7 done-criteria met: configs A and D each produce a verified `IncidentReport` for one alert with per-stage timing. Next: M8 evaluation (resumable, apps closed).

## 2026-11-02: M8 evaluation harness (plan)

Reality that shapes M8: the M4 detector alerted on only **10 of 25 test scenarios, all `ghost_aircraft` (5) and `replay_duplicate` (5)**; the other 15 (position_spoofing, sensor_fault, benign_anomaly) were **missed** — the pipeline never sees them. So the end-to-end A-vs-D comparison runs on 10 alerts over 2 of 5 classes, and the 15 missed detections are a headline result, not a footnote (EVALUATION_PROTOCOL §9). Every table says "n=10 evaluated of 25 test; 15 missed by the detector."

1. `src/eval/run_eval.py` (`make eval`): resumable. Args `--config A|D|both`, `--split test`, `--resume`, `--limit N`, `--run-id`. Ground truth = alert_map.json (alert→scenario) + splits.json (scenario→label); the label is used only for scoring, never passed to the pipeline (leakage test still holds). For each test scenario with an alert, run `orchestrator.investigate` (one shared provider/retriever); write `results/<run_id>/cases/<config>__<alert_id>.json` (label, verdict, correct, top2, confidence, verified/excluded counts, support rate, per-stage seconds, tool/llm counts) and the full trace under `traces/`. Skip cases already written (resume). Write `config.json` once (configs, git commit, models + `ollama show` digests, seeds, options) and `missed.json` (the 15). A case is the unit of resumption.
2. `src/eval/metrics.py`: pure functions for EVALUATION_PROTOCOL §4 — top-1/top-2 accuracy, per-class precision/recall/F1 with counts, 5×5 confusion matrix, evidence support rate + unsupported-claim rate, inconclusive rate, tool-call validity + structured parse rate (from llm_calls), latency p50/max, detector recall/FP (from results/detector + missed), calibration bands; plus 95% bootstrap CIs (§6, 1000 resamples, fixed seed) for top-1 and support rate.
3. `src/eval/figures.py`: matplotlib PNGs — accuracy by config (with n), confusion matrix (config D), latency per case (A and D), calibration counts (D). To `results/<run_id>/figures/`.
4. `src/eval/summarize.py` (`make summarize`): read `results/<run_id>/cases/*.json` + llm_calls only (nothing hand-typed) → `summary.csv` (one row per case), `summary.md` (tables with n and the missed-detection caveat), figures, and the spot-check CSV template (§8): sample 10 evidence items per config (fixed seed) with claim + tool-output snippet for a human to fill. Default `--run-id` = latest under `results/`.
5. Tests (`tests/test_eval.py`, hermetic): metrics math on synthetic case records (known confusion/accuracy/support/calibration/bootstrap determinism); run_eval end-to-end with an injected FakeLLM factory + synthetic provider (writes cases/config/missed, resumes without re-running); summarize builds csv/md/template from synthetic cases.
6. Cheap real validation: `make eval --config A --limit 1` then `--resume` (proves a real case writes + resumes), then `make summarize` on it. Do NOT run the full 20 investigations inline.
7. Full run is the overnight resumable job (10 alerts × A and D ≈ 2–2.5 h on the laptop, apps closed): set it up, let the user launch it, then summarize. Numbers trace to `results/<run_id>/`.

Next step: implement 1–5, hermetic green + lint, cheap real validation, then hand off the full run. No commit until authorised.

### M8 results (harness built + validated; full run pending)

Built `src/eval/{run_eval,metrics,figures,summarize}.py` (D-036). 13 new hermetic eval tests (metrics math on synthetic records; runner + summariser driven by an injected FakeLLM + synthetic provider, incl. a resume check). Full suite **124 pass**, ruff clean.

Validated the real CLI on one config-A case (`make eval --config A --limit 1 --run-id smoke_eval --resume`): the case ran (293 s), a second `--resume` skipped it (`ran=0`), and `make summarize` wrote `summary.csv`, `summary.md`, `metrics.json`, `figures/` and `spotcheck_template.csv`; `missed.json` recorded the 15 detector misses. The throwaway `smoke_eval/` run was deleted (not a final result; results/ is committed only for the final run).

Headline coverage fact (also in the summary): the detector alerted on **10/25 test scenarios, all ghost_aircraft + replay_duplicate** — the A-vs-D comparison is over 10 alerts / 2 classes, with 15 missed detections reported up front. Per-investigation cost (M7): config A ~3–5 min, config D ~9 min, so the full run (10 × A and D) is ~2–2.5 h — the resumable overnight job, not run inline.

Next step: launch the full run (`make eval` / `python -m eval.run_eval --config both --run-id test_final --resume`, apps closed) overnight, then `make summarize`; fill the spot-check; write the M9 app. No commit of a partial run.
