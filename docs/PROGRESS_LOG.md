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
