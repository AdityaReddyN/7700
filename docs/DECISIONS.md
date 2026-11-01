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

## D-029 (2026-11-01, accepted): Raw data is one day of hourly tar archives
- Context: the human added the raw OpenSky data. It is **one day**, 2019-12-09, with 24 hourly files `data/raw/.2019-12-09/HH/states_2019-12-09-HH.csv.tar` (~3.2 GB), not the four days or the 2017-06-05 date the earlier docs assumed, and the files are `.csv.tar` archives, not plain CSV. The folder name is hidden (leading dot).
- Decision: M2 conversion untars each hourly file before reading, and re-measures the schema/null rates on this data (the 2017 figures in DATA_SPEC are from a different file and are not assumed to hold). Because only one day is available, the day-based split (D-024) falls back to the **hour-based** split (disjoint hours per split); confirm in M2. The day lists in `config/scenarios.yaml` stay null.
- Consequences: replay offsets up to 6 h (D-026) fit within the 24-hour day. The data report (M2) states the actual date, coverage and counts. Raw data stays uncommitted (gitignored).
- Renumbered from an earlier D-023 in this session to avoid a collision with the gates entry above (log rule: ids are unique and entries are not deleted).
- Context: the laptop had no `make` and no `pytest`/`ruff`; the stack otherwise matched the pinned versions.
- Decision: use a project-local `.venv` (created at the human's request); `make setup` creates/uses it. Use the pre-installed GNU Make 3.82 (`C:\MinGW\bin\mingw32-make.exe`), copied to `make.exe` on PATH so the documented `make` commands work. Dependencies pinned to the versions verified installed on the laptop.
- Consequences: `make setup`/`make test` run on Windows. Makefile uses `OS`-based branching for the venv interpreter path. Full README (with results) still deferred to M10; a WIP README stub was added so the repo is not README-less.
