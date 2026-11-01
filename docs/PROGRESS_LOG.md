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

Next step: human confirms the benign holdings (eye-check); then M4 (rule-based flagger + alerts).
