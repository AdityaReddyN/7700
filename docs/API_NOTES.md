# API and model notes

Status values: MEASURED (run on the laptop and recorded), VERIFIED (checked against official docs with a date), UNVERIFIED (must be tested in M1 before use). Replace UNVERIFIED with a dated status after testing.

## 1. Measured on the Lenovo Yoga (16 GB RAM, Intel Iris Xe, CPU inference)

| Item | Result | Status |
|---|---|---|
| Memory at idle with normal apps | About 12.9 GB of 15.7 GB used (82%) with browser open | MEASURED |
| GPU | Intel Iris Xe, shared memory only (about 7.9 GB shared, 0 dedicated). Not used for inference | MEASURED |
| Ollama, `llama3.1:8b`, plain prompt | Generation 8.29 tokens/s (93 tokens). Prompt evaluation 37.23 tokens/s (21 tokens, 5 cached). Total 11.7 s for a 3-sentence answer | MEASURED |
| Memory for `llama3.1:8b` | About 4.9 GB model file; needs roughly 5 GB free plus context | MEASURED (fit) / to re-check with `ollama ps` under load |
| `llama3.2:3b` | Not yet measured | UNVERIFIED |
| Muse Glimmer 30B, 2-bit | Not yet measured. Expected memory about 12 to 14 GB; very tight | UNVERIFIED |

Consequence: prompt evaluation speed is the bottleneck. A 3,000-token subagent context would take about 80 seconds before generation.

## 2. Ollama (local)

| Item | Reported or known | Status |
|---|---|---|
| Install | Windows installer from ollama.com | MEASURED (installed) |
| Pull model | `ollama pull llama3.1:8b`; `ollama pull llama3.2:3b` | MEASURED (8B) / UNVERIFIED (3B) |
| Run and check | `ollama run <model> --verbose "<prompt>"` prints eval and prompt rates | MEASURED |
| Check processor split | `ollama ps` shows `100% CPU` or a CPU/GPU split | UNVERIFIED on this machine; expected 100% CPU |
| OpenAI-compatible endpoint | `http://localhost:11434/v1` | UNVERIFIED in this project; test in M1 |
| Native tool calling | Model-dependent. Test with the five tool definitions | UNVERIFIED |
| Structured output | JSON format option and schema support: test | UNVERIFIED |
| Deterministic settings | `temperature: 0`, fixed `seed` in options | UNVERIFIED |
| Model digest | `ollama show <model>` | UNVERIFIED |

## 3. Muse models (for reference; eligibility per guide)

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

## 6. Quirks log
Add dated entries here as behaviour differs from the documentation.
