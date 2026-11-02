# Decision log

Format: ID, date, status, context, decision, consequences. Never delete an entry. Supersede by adding a new entry that names the old one.

## D-001 (2026-10-27, accepted): Custom asyncio orchestration
- Context: parallelism and timing are central to the design and must be measurable.
- Decision: plain asyncio, no agent framework.
- Consequences: more code. Full control over timing. Sequential by default on the laptop.

## D-002 (2026-10-27, superseded by D-016): Responses API first
- Superseded because the chosen inference path is Ollama's OpenAI-compatible endpoint (Chat Completions style). The Responses API was for the closed Meta Model API path, which is no longer primary.

## D-003 (2026-10-27, accepted): DuckDB over Parquet with fixed tools
- Decision: no server database; the model never writes SQL.
- Consequences: safe, fast windowed queries. Tools must be well designed.

## D-004 (2026-10-27, accepted, amended): Hybrid retrieval, BM25 first
- Context: the knowledge base is small (10 case cards plus optional passages).
- Decision: BM25 by default. Add local embeddings with reciprocal rank fusion only if M6 is on schedule.
- Consequences: no extra model download needed for the minimum version.

## D-005 (2026-10-27, superseded by D-012): Six hypothesis classes and a 300-scenario benchmark
- Superseded. See D-012.

## D-006 (2026-10-27, accepted): Verifier is pure Python
- Decision: evidence must cite ref_ids and match logged values. Unverified evidence is excluded from adjudication.
- Consequences: an honest support metric. Claim wording is checked only by manual spot-check.

## D-007 (2026-10-27, amended by D-017): Reasoning-effort policy
- Superseded in part. Local models do not expose a reasoning-effort parameter in the same way. Effort is expressed through prompt length and tool-call limits instead. Effect is not measured.

## D-008 (2026-10-27, PROPOSED, awaiting human approval): Streamlit as UI
- Context: the app must be a working, interactive case view, built in about a week.
- Decision (proposed): Streamlit for the app. No React, no FastAPI.
- Consequences: faster build. Limited styling. Acceptable for an analysis-first app.
- Status: approve or reject in writing.

## D-009 (2026-10-27, accepted): Fresh injectors only
- Context: the hackathon requires new work; the organizers' licence is broad and perpetual.
- Decision: write all injectors fresh during the event. Do not reuse earlier research code or notebooks.
- Consequences: more time for injectors, a clear provenance story for judging.

## D-010 (2026-10-29, accepted): Local-first inference on the laptop
- Context: the laptop is the only machine; hosted credits are unconfirmed; the Modal balance is $1.
- Decision: all main inference runs locally through Ollama. Hosted calls are off by default and used only for a few demonstration cases if budget allows.
- Consequences: CPU-bound speed (measured in API_NOTES.md). Sequential investigations. Smaller test set.

## D-011 (2026-10-29, accepted, pending G1): Primary model set by gate
- Context: Llama is not on the guide's list of named Meta models. Organizers' answer is pending.
- Decision: if G1 is yes, primary is `llama3.1:8b`. If no or unanswered by Day 2, primary is Muse Glimmer 30B, 2-bit local.
- Consequences: model choice lives in `config/models.yaml`. The README states the basis.

## D-012 (2026-10-29, accepted): Five hypothesis labels, 10 scenarios each
- Supersedes D-005.
- Decision: five labels: `position_spoofing`, `ghost_aircraft`, `replay_duplicate`, `sensor_fault`, `benign_anomaly`. Ten scenarios per label, total 50. Per label: 2 case cards, 3 dev, 5 test. Test total 25.
- `kinematic_spoofing` merged into `position_spoofing` as the `velocity_offset` mode.
- Consequences: one fewer subagent and injector. Smaller test set, so intervals are wide; reported as such.

## D-013 (2026-10-29, accepted): Subagent tool-call cap of 4
- Decision: subagents in config D are capped at 4 tool calls. Config A is capped at 8.
- Consequences: faster investigations on CPU. Evidence may be thinner; the verifier and inconclusive path cover this.

## D-014 (2026-10-29, accepted): Five tools
- Decision: `get_track_window`, `compute_kinematics`, `compare_to_baseline`, `check_identity`, `retrieve_cases`. Cut `render_plot`, `get_neighbors`, `check_coverage` for v1.
- Consequences: smaller tool surface. Plots for the report are made by Matplotlib in the report step, not by the model.

## D-015 (2026-10-29, accepted): No FastAPI, no SSE, no React
- Decision: the Streamlit app reads trace files and can call the orchestrator directly for a live run.
- Consequences: removes the API and event-streaming layer. Live progress shown by placeholders.

## D-016 (2026-10-29, accepted): Ollama as the local inference backend
- Decision: Ollama with its OpenAI-compatible endpoint. Hosted backends use the same client shape.
- Consequences: simple install. Tool-calling and structured-output behaviour must be verified in M1.

## D-017 (2026-10-29, accepted): Sequential investigations by default
- Context: measured prompt evaluation about 37 tokens/s on the laptop; parallel subagents would share the same CPU and memory.
- Decision: concurrency 1. The asyncio semaphore stays so the design can be raised if measured.
- Consequences: no speedup claim unless measured. Time per investigation reported honestly.

## D-018 (2026-10-29, accepted): Config A versus D as the main comparison
- Decision: the evaluation compares config A (single agent) and config D (full pipeline). Ablations beyond these are out of scope.
- Consequences: a clearer, smaller story that fits the time budget.

## D-019 (2026-10-29, accepted): Test set of 25 scenarios, one run
- Decision: 25 test scenarios, one run per config. Report bootstrap intervals and sample sizes. Do not claim improvements the intervals do not support.
- Consequences: a small but honest evaluation. Reduced to 15 if the time budget forces it, and reported as such.

## D-020 (2026-10-29, PROPOSED, awaiting human decision): Problem statement
- Options: Push the Frontier (recommended: sensor and system integrity fits "understand and control a physical system") or Build for Your World (if the pitch is from the user's own airspace or sensor-monitoring experience).
- Status: human to choose and record.

## D-021 (2026-10-29, accepted): Avoid anti-project framing
- Decision: the project leads with hypothesis testing, verification and the evaluation. Retrieval is one component, not the headline. Avoid military, political or safety-advice framing.
- Consequences: judging alignment with the guide's anti-project list.

## D-022 (2026-10-29, accepted): Data use limited by gates
- Decision: raw OpenSky data is never committed. Published data is limited to statistics and a small sample, and only after G2 is resolved.
- Consequences: reproducibility depends on the reader obtaining OpenSky data themselves. The README says how.

## D-023 (2026-11-01, accepted): Gates G1 and G2 resolved, G3 partial
- Supersedes the pending status of D-011.
- Context: the organizers answered the eligibility question and OpenSky answered the permission request; more hourly data arrived.
- Decision: G1 is accepted — Llama models are eligible, so `llama3.1:8b` is the primary model (settles D-011); `llama3.2:3b` is the triage/fallback. G2 is received — OpenSky permission reply saved; follow any conditions it states. G3 is partial — four days of hourly files are present but only one is inspected; confirm file dates and day groups in M2.
- Consequences: replies saved in `docs/permissions/` and referenced in the README and submission. Muse Glimmer is demoted to the optional comparison (D-025). The day-based split (D-024) and extended replay offsets (D-026) follow from the new data.

## D-024 (2026-11-01, PROPOSED, in effect as default): Day-based scenario split
- Context: with several days of data, splitting by day group keeps shared receiver conditions, traffic patterns and replay source windows from a test day out of the dev/kb material.
- Decision: split scenarios by day group (a dev/kb group and a test group) rather than at random within a day. If only one day is usable, fall back to disjoint-hour splits and record it. Day lists in `config/scenarios.yaml` are filled after the M2 data check. Human to confirm the day groups (section 10).
- Consequences: stronger leakage guarantee; the leakage test also checks the day-group boundary. Reflected in SCENARIO_SPEC.md section 6 and DATA_SPEC.md section 2.

## D-025 (2026-11-01, PROPOSED, off by default): Optional Muse Glimmer comparison
- Context: the Meta-tooling judging criterion favours using a named Meta model; Llama is primary but Glimmer is a named open-weight Meta model.
- Decision: keep an optional, off-by-default Muse Glimmer 30B (2-bit, local) comparison run, enabled via the `comparison` block in `config/models.yaml`, to demonstrate Meta tooling on a few cases. Not part of the main pipeline. Human to decide whether to run it (section 10).
- Consequences: no effect on the default pipeline. If run, report it honestly as a small comparison with its own timing and memory headroom.

## D-026 (2026-11-01, accepted): Replay offsets extended to six hours
- Context: more than one hour of data is now available (G3 partial), so longer replay offsets are realistic.
- Decision: `replay_duplicate` `window_copy` offset range is now 10 minutes to 6 hours (`config/scenarios.yaml`: `window_copy_offset_min: [10, 360]`). The source window must stay within the same day group as the scenario (D-024).
- Consequences: more realistic replay scenarios. The leakage test checks that replay source windows do not cross the split boundary.

## D-028 (2026-11-01, accepted): Local inference only — no third-party hosts
- Supersedes the hosted allowance in D-010 and declines D-025.
- Context: the human confirmed there will be no third-party hosted inference. The primary model is the local Llama model.
- Decision: all inference runs locally through Ollama. No hosted/third-party calls at all (Baseten, Modal, Fireworks, Together, OpenRouter, Meta Model API). The `hosted` block in `config/models.yaml` stays disabled; the optional Muse Glimmer comparison (D-025) is declined, so Glimmer is not run or tested. Meta-tooling eligibility is met by Llama, which the organizers accepted (G1). `llama3.1:8b` is primary and `llama3.2:3b` is the triage/fallback; both are local Llama models.
- Consequences: G5 (credits) no longer blocks anything. No spend risk. The M1 Glimmer test is dropped. The README's Meta-tooling section cites Llama only. If the human later wants a Glimmer comparison, re-open D-025.

## D-030 (2026-11-02, accepted): Isolation Forest is the primary detector; rules are the fallback
- Owner decision (human). Reverses the earlier stance (rule-based primary, IsolationForest optional) in AGENTS §5/§7 and the "in scope if time" IsolationForest item.
- Decision: the detector is an **IsolationForest** (scikit-learn), fit on real normal traffic, scoring each track window. The **rule-based flagger is kept as the fallback/baseline** — selectable via `config/detector.yaml` (`method: isolation_forest | rules`) and used automatically if the IsolationForest fit is unavailable. Both emit the same `Alert` object (no label, no scenario_id). Determinism via fixed `random_state`; the model is refit each run from the seeded baseline sample (no pickle committed).
- Consequences: `config/detector.yaml` added (new config file). The threshold is tuned on dev only, test scored once. `top_features` is populated from the most extreme baseline z-scores (IsolationForest gives no direct attribution). All docs updated to match.

## D-031 (2026-11-02, accepted): Detector operating point is a false-positive budget, not forced recall
- Context: the first M4 run tuned the threshold to hit 80% dev recall. That reached 0.85 test recall but flagged **61% of real traffic** — unusable as an alert stream. Subtle `position_spoofing` (hard drift / near-unity velocity scale) and some `sensor_fault` windows are genuinely indistinguishable from normal flight, so forcing recall pushes the threshold into the normal-traffic bulk.
- Decision: the threshold is set by a **false-positive budget on normal dev-hour traffic** — flag the top `target_alert_rate` (default 0.05) fraction of the baseline score distribution (`config/detector.yaml` `threshold.target_alert_rate`). Recall is reported at that operating point, not targeted. `threshold.value` still overrides; the old recall-targeting policy is kept in code (`_tune_threshold`) but is not the default. The detector stays deliberately simple; catching subtle injections is the job of the agents and tools downstream.
- Consequences: a believable alert rate (~5% on dev-hour traffic) with honestly lower, class-dependent recall (strong on `ghost_aircraft`/`replay_duplicate`, weak on subtle `position_spoofing`). The independent test-hour alert rate is reported as the false-positive proxy. Still "tuned on dev only" (the budget uses dev-hour normal traffic); test scored once. Numbers in `results/detector/`.

## D-029 (2026-11-01, accepted): Raw data is one day of hourly tar archives
- Context: the human added the raw OpenSky data. It is **one day**, 2019-12-09, with 24 hourly files `data/raw/.2019-12-09/HH/states_2019-12-09-HH.csv.tar` (~3.2 GB), not the four days or the 2017-06-05 date the earlier docs assumed, and the files are `.csv.tar` archives, not plain CSV. The folder name is hidden (leading dot).
- Decision: M2 conversion untars each hourly file before reading, and re-measures the schema/null rates on this data (the 2017 figures in DATA_SPEC are from a different file and are not assumed to hold). Because only one day is available, the day-based split (D-024) falls back to the **hour-based** split (disjoint hours per split); confirm in M2. The day lists in `config/scenarios.yaml` stay null.
- Consequences: replay offsets up to 6 h (D-026) fit within the 24-hour day. The data report (M2) states the actual date, coverage and counts. Raw data stays uncommitted (gitignored).
- Renumbered from an earlier D-023 in this session to avoid a collision with the gates entry above (log rule: ids are unique and entries are not deleted).
- Context: the laptop had no `make` and no `pytest`/`ruff`; the stack otherwise matched the pinned versions.
- Decision: use a project-local `.venv` (created at the human's request); `make setup` creates/uses it. Use the pre-installed GNU Make 3.82 (`C:\MinGW\bin\mingw32-make.exe`), copied to `make.exe` on PATH so the documented `make` commands work. Dependencies pinned to the versions verified installed on the laptop.
- Consequences: `make setup`/`make test` run on Windows. Makefile uses `OS`-based branching for the venv interpreter path. Full README (with results) still deferred to M10; a WIP README stub was added so the repo is not README-less.

## D-032 (2026-11-02, accepted): Tool data resolution and the deterministic baseline
- Context: M5 tools must read the alert's track without leaking that it is a scenario, and `compare_to_baseline` must be deterministic and read-only (non-negotiables #2, #5).
- Decision: a `TrackProvider` resolves the alert's own track by `icao24` + `[t_start, t_end]` from the scenario view (`data/scenarios/tracks.parquet`) when matching rows exist there, otherwise from the real Parquet store. Resolution never uses `scenario_id` or `alert_map.json`, and no tool output contains a label, scenario id or split (a leakage test enforces this). `compare_to_baseline` computes the baseline as a full same-hour aggregate over real traffic (DuckDB `quantile_cont` for median/p95), excluding any scenario-source aircraft — a full aggregate, so it is deterministic with no sampling seed; cached per `(hour, feature, context)`. `retrieve_cases` ships in M5 reading an optional BM25 index and returning an empty list when the index is absent; the real index is built in M6.
- Consequences: tools are self-contained and testable in M5 without the KB. The scenario view is the single source for an alert's (possibly injected) track, so ghost and replay alerts resolve correctly. Baselines come from real traffic only. Tool-call caps and native-vs-text tool-calling remain M7 concerns.

## D-033 (2026-11-02, accepted): M6 knowledge base — case cards + BM25 only
- Context: M6 builds the KB that `retrieve_cases` searches. The owner's brief scopes it to cards + BM25.
- Decision: case cards are `data/kb/cards/C001..C010.md` with YAML frontmatter (id, label, title, signature, differentiators, outcome, `synthetic: true`, `source_split: kb`) plus a prose body. Numbers are computed from the 10 KB-split scenarios only, via the M5 tools (`kinematics`, `identity`, `window_summary`); no dev/test stats and no memory. `data/kb/index.json` is built in the M5 retriever schema (`card_id, label, title, text`). Retrieval is **BM25 only** for v1. Dense embeddings + reciprocal rank fusion are deferred (`sentence-transformers` is not a dependency and dense retrieval is an unneeded resource cost on the 16 GB CPU laptop; D-004 allows BM25 alone). **Reference passages are deferred** (they need external sourcing and sign-off on terms per SCENARIO_SPEC §8.2); M6 ships zero and says so. recall@4 on dev uses a **label-free** query built from the dev scenario's computed stats; the true label is compared only after retrieval.
- Consequences: `make kb` regenerates cards, index and `results/kb/` deterministically. `outcome` is computed-derived (track span / largest step / max gap), not the ground-truth injection magnitude the SCENARIO_SPEC example shows — a documented limitation. The three tools do not expose identity *presence*, so `ghost_aircraft` reads as a "quiet" track to retrieval; recall is reported honestly per label. Evaluating against only 10 cards makes recall@4 optimistic and says nothing about generalisation or detection quality (stated in the report).
- Consequence (M6 build): fixed an M5 `CaseRetriever.search` defect where BM25 IDF <= 0 for tokens common across the 10-card corpus made the `score>0` cut return nothing (or rank cards by NOT containing the query terms). BM25 stays primary; it falls back to shared-token overlap only when BM25 has no positive signal. No interface change; M5 tests unchanged.

## D-034 (2026-11-02, accepted): M7 agent pipeline — wrapper, stages, configs A/D
- Context: M7 builds the investigation pipeline on the M5 tools and M6 retrieval. Local Llama only (D-028), CPU laptop (AGENTS §4). ARCHITECTURE §2/§6/§10 and PROMPT_SPECS set the shape; this entry records the implementation choices.
- Decision:
  - **LLM wrapper** (`src/agents/llm.py`, `LLMClient.complete`) is `async` (sync core via `asyncio.to_thread`), resolves the stage's model from `config/models.yaml` (triage→`llama3.2:3b`, subagent/adjudicator→`llama3.1:8b`), uses **native Ollama tool-calling** (measured working, API_NOTES §2) and `response_format=json_object` + schema-in-prompt validated with Pydantic, retries once on a parse failure with the validation error fed back (then the caller records `inconclusive`), retries connection errors with backoff, and logs one JSONL line per call. Money cost is $0 (local); the hosted spend-cap path exists but never trips. The M1 `--smoke` path is unchanged.
  - **Prompts** are versioned files `src/agents/prompts/*.v1.md` filled by exact-token replacement (JSON braces stay literal); a label-free `CHEATSHEET` holds the public hypothesis definitions/supports/refutes.
  - **Triage** keeps prior ≥ 0.15, 3–5 hypotheses (top-3 if too few pass); a parse failure falls back to deterministic rule-based priors from the alert's top features, recorded.
  - **Subagent** runs a native tool-call loop through `ToolRegistry`, caps tool calls (4 for D, 8 for config A), then forces a structured `HypothesisReport`; the executed tool count is authoritative and the hypothesis under test is pinned. Any loop/parse failure → `inconclusive`, investigation continues.
  - **Verifier** is pure Python per EVALUATION_PROTOCOL §5: `missing_ref`/`unknown_stat`/`value_mismatch`, and `verified_partial` when stat/value are absent (ref-grounded only, counted apart). Full + partial reach the adjudicator; the rest are excluded and counted.
  - **Adjudicator** writes the `IncidentReport` from verified evidence only; `ranked` is replaced in code by the verified reports and `evidence_table` is built in code; confidence is capped at 0.9 unless ≥ 2 independent verified items back the verdict.
  - **Orchestrator** is `asyncio` with a semaphore (concurrency 1 default; sequential on this CPU). Config D = triage → sequential subagents → verifier → adjudicator; config A = single agent → verifier → `IncidentReport` with the agent's own verdict (same verification and confidence cap, no adjudicator model call) so A and D compare. Per-stage timing + token counts go in `meta`; one trace per run to `runs/<inv_id>/trace.json` with the ARCHITECTURE §8 stage names. CLI `make run-case` (`--config A|D`, `--alert-id`).
- Consequences: configs A and D each produce a verified `IncidentReport` for one alert with per-stage timing. 21 new hermetic agent tests (FakeLLM, synthetic provider) cover the verifier's required cases, the triage keep-rule + fallback, the subagent budget and inconclusive paths, the confidence cap, and both configs end-to-end; a leakage test confirms no scenario id/split reaches any prompt. Real end-to-end timing on the laptop is recorded in PROGRESS_LOG and `results/` (M8 adds the full eval, model digests in `config.json`, and the A-vs-D comparison). If a real investigation exceeds 15 min, cut per AGENTS §7 (fewer tool calls / top-3 hypotheses) with a logged decision.

## D-035 (2026-11-02, accepted): Config D scope cut — 3 hypotheses, 3 tool calls (AGENTS §7 time budget)
- Context: the first real config-D investigation on the laptop (one alert, `llama3.1:8b`, CPU, under heavy memory pressure — ~1 GB free, see API_NOTES §1) ran past **38 minutes / 29 model calls without finishing** and was stopped. AGENTS §7 time budget: if a measured investigation exceeds 15 minutes, cut subagent tool calls to 3 and reduce to the top-3 hypotheses, and record it here.
- Decision: in `config/agents.yaml`, `triage_max_hypotheses` 5 → 3 and `subagent_tool_call_limit` 4 → 3. `triage_min_hypotheses` stays 3, so config D now runs exactly the top-3 triage hypotheses with at most 3 tool calls each. Config A is unchanged (its one real run was 222.6 s, under the ceiling).
- Consequences: config D does fewer, shorter 8B turns per alert. The dominant cost is 8B prompt-evaluation on a memory-pressured CPU (API_NOTES: ~1.8 tok/s under load vs ~8.3 with apps closed), so the clean per-investigation timing — and the M8 A-vs-D evaluation — must be measured with other apps closed and should run as the resumable overnight eval, not inline. The cut is a config value only; no code or test change. Revisit if a clean run shows ample headroom.
