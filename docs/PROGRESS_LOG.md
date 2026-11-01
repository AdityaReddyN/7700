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
