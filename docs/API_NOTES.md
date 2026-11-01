# API and model notes

Status values: MEASURED (run on the laptop and recorded), VERIFIED (checked against official docs with a date), UNVERIFIED (must be tested in M1 before use). Replace UNVERIFIED with a dated status after testing.

## 1. Measured on the Lenovo Yoga (16 GB RAM, Intel Iris Xe, CPU inference)

| Item | Result | Status |
|---|---|---|
| Memory at idle with normal apps | About 12.9 GB of 15.7 GB used (82%) with browser open | MEASURED |
| GPU | Intel Iris Xe, shared memory only (about 7.9 GB shared, 0 dedicated). Not used for inference | MEASURED |
| Ollama, `llama3.1:8b`, plain prompt | Generation 8.29 tokens/s (93 tokens). Prompt evaluation 37.23 tokens/s (21 tokens, 5 cached). Total 11.7 s for a 3-sentence answer | MEASURED |
| Memory for `llama3.1:8b` | About 4.9 GB model file; needs roughly 5 GB free plus context | MEASURED (fit) / to re-check with `ollama ps` under load |
| `llama3.2:3b` | Loads at 2.6 GB (`ollama ps`), 100% CPU. Plain gen ~4.4 tok/s **under memory pressure** (see below) | MEASURED (2026-11-01) |
| Muse Glimmer 30B, 2-bit | Not used (D-028); not measured | N/A |

**Memory pressure caveat (M1 smoke, 2026-11-01):** the smoke run executed with only 0.6–1.4 GB free of 16.9 GB (many apps open). Under that load, plain generation was ~1.8 tok/s for `llama3.1:8b` and ~4.4 tok/s for `llama3.2:3b` — far below the 8.3 tok/s measured earlier with apps closed. `ollama ps` showed `llama3.1:8b` at 5.6 GB and `llama3.2:3b` at 2.6 GB, both 100% CPU, context 4096. Close apps before any benchmark (AGENTS §4); re-measure speed then.

Consequence: prompt evaluation speed is the bottleneck. A 3,000-token subagent context would take about 80 seconds before generation.

## 2. Ollama (local)

| Item | Reported or known | Status |
|---|---|---|
| Install | Windows installer from ollama.com | MEASURED (installed) |
| Pull model | `ollama pull llama3.1:8b`; `ollama pull llama3.2:3b` | MEASURED (8B) / UNVERIFIED (3B) |
| Run and check | `ollama run <model> --verbose "<prompt>"` prints eval and prompt rates | MEASURED |
| Check processor split | `ollama ps` shows `100% CPU` for both models (no GPU split) | MEASURED (2026-11-01): 100% CPU |
| OpenAI-compatible endpoint | `http://localhost:11434/v1`, called via the `openai` SDK | VERIFIED (2026-11-01): chat completions, tools and `response_format` all work |
| Native tool calling | Works via `tools` + `tool_choice:auto`. 3B 20/20 valid; 8B 11/20 (9 fails were integer timestamps emitted as **strings**) | MEASURED (2026-11-01) |
| Structured output | `response_format={"type":"json_object"}` + schema described in the prompt, validated with Pydantic. 8B 20/20, 3B 19/20 first-try | MEASURED (2026-11-01) |
| Deterministic settings | `temperature: 0`, `seed: 42` accepted by the SDK/endpoint | MEASURED (2026-11-01, used in smoke) |
| Model digest | captured via `ollama show` into `results/smoke/<date>.json` | MEASURED (2026-11-01) |

## 3. Muse models (for reference only; not used)

**D-028: inference is local only. No Muse models and no hosted/third-party calls are used.** The table below is kept for reference and in case the decision is revisited.

| Model | Where it runs | Notes | Status |
|---|---|---|---|
| Muse Glimmer 30B | Local (Hugging Face weights, GGUF builds, Ollama listing), or partner hosts (Fireworks, Together, OpenRouter) | 30B dense. Apache 2.0. Meta describes it as tuned for tool use and long tasks. Meta's benchmark numbers are Meta's claims | VERIFIED from Meta's model page (date of check: 29 Oct 2026) |
| Muse Spark Open | Partner hosts (Baseten, Modal, Fireworks, Together, OpenRouter, others). Baseten model id for the event: `meta-models/muse-spark-open-1026` | 816B total, 42B active. Too large to run locally | VERIFIED from Meta's model page and the participant guide |
| Muse Spark 1.1, 1.2, 1.3, Muse Wonder | Meta Model API (closed) | Excluded: not open weights | Not used |

Modal's $1 balance is enough for a handful of hosted calls at most. Do not deploy a GPU endpoint on it. Check per-token prices on the host's pricing page before any call; record the price and date in `config/pricing.yaml`.

## 4. Llama models
- Eligibility: **ACCEPTED** for the event (gate G1). The organizers' written answer is saved in `docs/permissions/G1-llama.md`; reference it in the README. Llama results may be reported in the submission.
- Licence: Meta's Llama licence and acceptable-use policy. Read them before downloading. Mention the licence in the README.
- Sizes quoted here are approximate; confirm on the model's page before downloading.

## 5. Smoke-test checklist (M1)

Write `make smoke` to run these and write `results/smoke/<date>.json`:
1. Plain completion, timed, with `temperature: 0`.
2. Tool calling: the five tool definitions, 20 dev prompts. Count valid calls (parsed, correct tool name, correct argument types).
3. Structured output: a `HypothesisReport` schema, 20 dev prompts. Count parses on first try.
4. OpenAI-compatible endpoint: one call through the SDK pointed at `http://localhost:11434/v1`.
5. Prompt evaluation speed on a 2,000-word prompt.
6. Free RAM during the run (Task Manager or `psutil`), and `ollama ps` output.
7. Glimmer 2-bit, if downloaded: one completion and its tokens per second. Record memory headroom.

Record all results in this file under the relevant row, with the date.

### M1 smoke results — 2026-11-01 (`results/smoke/2026-11-01.json`)

Harness: `make smoke` (`src/agents/llm.py`), 20 neutral dev prompts, `temperature 0`, `seed 42`, endpoint `http://localhost:11434/v1`.

| Model | Plain gen | Tool-call valid | Structured parse | `ollama ps` | Free RAM min |
|---|---|---|---|---|---|
| `llama3.1:8b` | 1.82 tok/s* | 11/20 | 20/20 | 5.6 GB, 100% CPU | 1.4 GB |
| `llama3.2:3b` | 4.36 tok/s* | 20/20 | 19/20 | 2.6 GB, 100% CPU | 0.64 GB |

*Under heavy memory pressure (0.6–1.4 GB free); not the clean-run speed. Re-measure with apps closed.

Takeaways: the endpoint, native tool calling, and JSON structured output all work. `llama3.1:8b` (primary) parses structured output perfectly but often sends integer timestamps as strings in tool args; `llama3.2:3b` calls tools cleanly but missed one structured parse (bad `hypothesis` enum). The M5 tool registry should coerce numeric-string args. Glimmer not tested (D-028).

## 6. Quirks log
Add dated entries here as behaviour differs from the documentation.

- **2026-11-01 — `llama3.1:8b` string timestamps in tool args.** 9/20 tool calls put `t_start`/`t_end` as JSON strings, not integers. Plan: coerce numeric strings to int in the tool registry (M5), and/or state "integer seconds" in the arg descriptions.
- **2026-11-01 — speed scales with free RAM.** With ~0.6–1.4 GB free, generation ran ~1.8 (8B) / ~4.4 (3B) tok/s vs 8.3 tok/s earlier with apps closed. Benchmarks must close other apps first.
