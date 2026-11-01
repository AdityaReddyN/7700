# Architecture

## 1. Components

```
OpenSky CSVs --> Parquet store --> Scenario builder (injectors, benign finder)
                                        |
                              Alert generator (rule-based flagger)
                                        |
                           Orchestrator (one alert at a time)
                                        |
   Triage (no tools) --> ranked hypotheses (prior >= 0.15, 3 to 5 kept)
                                        |
   Subagent per hypothesis (sequential by default; tools; <= 4 calls)
                                        |
   Verifier (pure Python) --> verified evidence only
                                        |
   Adjudicator --> IncidentReport --> saved trace in runs/ or results/
                                        |
                        Streamlit app (reads traces; live run on demand)
```

| Component | Responsibility | Must not |
|---|---|---|
| Parquet store | Clean, partitioned data | Be modified after conversion |
| Scenario builder | Make labelled scenarios | Leak labels into the alert path |
| Flagger | Produce alerts with a score and top features | See labels or scenario ids |
| Triage | Rank five hypotheses by prior from the alert summary | Use tools; claim to have checked data |
| Subagent | Test one hypothesis; return `HypothesisReport` | See other subagents' output |
| Tools | Read-only, bounded, return `ref_id` | Write, execute code, touch the network |
| Verifier | Check refs and values against the ToolLog | Call a model |
| Adjudicator | Write `IncidentReport` from verified evidence | Cite anything not in a report |
| Orchestrator | Run stages, time them, handle failures | Continue silently after a stage fails |
| LLM wrapper | All model calls, logging, retries, budget cap | Be bypassed |
| App | Present traces and explain reasoning | Compute metrics (reads `results/` only) |

## 2. Pipeline for one alert

1. Flagger emits an alert object (no label, no scenario id).
2. Orchestrator creates an investigation id and a `ToolLog`.
3. **Triage** (one model call, no tools) returns ranked hypotheses with priors and reasons. Keep hypotheses with prior at least 0.15; keep at least 3 and at most 5. If fewer than 3 pass the threshold, keep the top 3.
4. **Subagents** run one at a time in config D. Each loop: model call, then execute any tool calls, append bounded results, repeat. At most 4 tool calls. Finish with a structured `HypothesisReport`. A parse failure is retried once, then recorded as `inconclusive`.
5. **Verifier** checks each evidence item (rules in EVALUATION_PROTOCOL.md). Verified items are kept; unverified items are marked and excluded from the adjudicator's input.
6. **Adjudicator** (one model call) receives the alert summary, the verified evidence, and each hypothesis's verdict and confidence. Writes the `IncidentReport`. It may cite only evidence present in the reports.
7. Orchestrator saves one JSON trace containing: alert, triage, each subagent's messages and tool calls, verifier output, adjudicator output, per-stage timing, token counts, and the config used.

**Config A (single agent):** one model call that receives all five tools and the alert. It may call tools up to 8 times, then returns one `HypothesisReport` for its best hypothesis and a list of alternatives with brief reasons. No separate verifier stage beyond the same checks, so that evidence support can be compared.

Both configs use the same tools, prompts' data sections, and verifier. This keeps the comparison about the pipeline design, not about the data.

## 3. Tools

All five tools are read-only and deterministic. Each returns a `ToolResult`:

```python
class ToolResult(BaseModel):
    ref_id: str
    tool: str
    args: dict
    output: dict          # bounded; see size rule
    truncated: bool
    ts: float
```

Size rule: the serialised `output` must stay under about 400 tokens (roughly 1,600 characters). Truncate lists to the top N items and record `truncated: true`.

### 3.1 `get_track_window(icao24, t_start, t_end)`
Downsampled summary of one aircraft's track in the window.
Output: `n_points`, `t_first`, `t_last`, `lat_first`, `lon_first`, `lat_last`, `lon_last`, `max_gap_s`, `missing_fraction`, `altitude_first_m`, `altitude_last_m`.
`ref_id`: `win:<alert_id>:<t_start>-<t_end>`.

### 3.2 `compute_kinematics(icao24, t_start, t_end)`
Compares positions with reported fields.
Output: `implied_speed_kt_median`, `reported_speed_kt_median`, `residual_kt_median`, `residual_kt_max`, `residual_slope_kt_per_min`, `largest_jump_km`, `largest_jump_t`, `vertrate_vs_altitude_mismatch_ms_median`, `n_points_used`.
`ref_id`: `calc:<alert_id>:kin:<hash8>`, where the hash is of the arguments.

### 3.3 `compare_to_baseline(feature, context)`
Compares a named feature with a baseline from **real normal traffic** in the same hour, excluding windows that overlap any scenario or alert.
`feature` in {`residual_kt_median`, `largest_jump_km`, `max_gap_s`, `vertrate_vs_altitude_mismatch_ms_median`}. `context` is a short label such as `all` or `same_altitude_band`.
Output: `feature`, `value`, `baseline_median`, `baseline_p95`, `z`, `n_baseline`.
`ref_id`: `calc:<alert_id>:base:<hash8>`.

### 3.4 `check_identity(icao24, t_start, t_end)`
Identity and consistency checks.
Output: `callsign_changes`, `squawk_changes`, `duplicate_position_pairs` (same time, distance over 10 km), `n_points`.
`ref_id`: `calc:<alert_id>:id:<hash8>`.

### 3.5 `retrieve_cases(query, hypothesis, k=4)`
Top-k case cards, or reference passages if present. Only the KB index is searched.
Output: list of up to 4 items, each with `card_id`, `label`, `title`, and a 1-sentence snippet.
`ref_id`: `case:<card_id>`.

Cut tools (not built in v1): `render_plot`, `get_neighbors`, `check_coverage`. If time allows after M8, add `get_neighbors` as a sixth tool. Record in DECISIONS.md first.

## 4. ToolLog
- Per investigation, a dictionary from `ref_id` to `ToolResult`, saved in the trace.
- Each entry records the full output (not truncated) so the verifier can check values. The model sees only the truncated output.
- Identical calls return the same `ref_id` (hash of tool name and arguments).

## 5. Schemas (`src/common/schemas.py`)

```python
from typing import Literal
from pydantic import BaseModel, Field

Label = Literal["position_spoofing", "ghost_aircraft", "replay_duplicate",
                "sensor_fault", "benign_anomaly"]

class Alert(BaseModel):
    alert_id: str
    icao24: str
    t_start: int
    t_end: int
    score: float
    top_features: list[dict]     # {"name": str, "z": float}
    summary: str                 # human-readable; no label, no scenario id

class Triage(BaseModel):
    hypotheses: list["TriageItem"]

class TriageItem(BaseModel):
    hypothesis: Label
    prior: float = Field(ge=0, le=1)
    reason: str

class Evidence(BaseModel):
    claim: str
    source: Literal["data_window", "calc", "retrieved_case", "reference"]
    ref_id: str
    stat: str | None = None
    value: float | None = None
    verified: bool | None = None  # set by verifier only

class HypothesisReport(BaseModel):
    hypothesis: Label
    verdict: Literal["supported", "refuted", "inconclusive"]
    confidence: float = Field(ge=0, le=1)
    evidence: list[Evidence]
    inference: str               # labelled as reasoning, not evidence
    would_disprove: list[str]
    next_checks: list[str]
    tool_calls_used: int

class IncidentReport(BaseModel):
    alert_id: str
    verdict: Label | Literal["inconclusive"]
    confidence: float = Field(ge=0, le=1)
    ranked: list[HypothesisReport]
    evidence_table: list[Evidence]   # verified only
    excluded_evidence_count: int
    inference: str
    would_change_my_mind: list[str]
    recommended_action: str
    meta: dict                       # config, models, per-stage seconds, tokens
```

Confidence rule: the adjudicator must not report confidence above 0.9 unless at least two independent verified evidence items support the verdict. Enforce this in code, not only in the prompt.

## 6. LLM wrapper (`src/agents/llm.py`)

One async function, used by every stage:

```python
async def complete(stage: str, messages: list[dict], *,
                   tools: list[dict] | None = None,
                   response_schema: type[BaseModel] | None = None,
                   max_tokens: int = 800,
                   timeout_s: float = 300) -> LLMResult
```

Behaviour:
- Backend from `config/models.yaml`: `ollama` (default, `http://localhost:11434/v1`) or `openai_compatible` (hosted, base URL and key from `.env`).
- Native tool calling if the backend and model support it. If not, fall back to a text protocol: the model emits one JSON action per turn, parsed and validated with Pydantic. Record which mode was used.
- Structured output: request JSON conforming to the schema where the backend supports it; always validate with Pydantic. One retry on parse failure, with the validation error fed back. Then mark `inconclusive`.
- Timeouts per call. Retries with backoff on connection errors only. Do not retry on validation errors more than once.
- Logs one JSON line per call to `runs/<run_id>/llm_calls.jsonl` (or `results/<run_id>/` for evaluation runs): timestamp, stage, backend, model, input tokens, output tokens, latency_s, tool_calls_count, tool_call_valid (bool), parse_ok (bool), cost_usd (0 for local), alert_id, config.
- Spend cap: for hosted backends, read `MAX_SPEND_USD` and the cumulative cost in the run folder; refuse new hosted calls above the cap and raise a clear error. Local backends never hit this cap.
- Replay cache: optional, keyed by a hash of the request, for development and tests only. Off for evaluation runs.

Prompt caching: no vendor-specific caching is assumed. Ollama reuses the prompt prefix automatically when it is identical across calls. Keep system text first and alert-specific text last.

## 7. Configuration files

`config/models.yaml`
```yaml
primary:
  backend: ollama
  base_url: http://localhost:11434/v1
  model: llama3.1:8b          # set by gate G1; alternative: muse-glimmer (local GGUF path)
triage:
  model: llama3.2:3b          # optional; same as primary if unset
adjudicator:
  model: null                 # null = primary
hosted:
  enabled: false
  backend: openai_compatible
  base_url: null              # set per provider the human has an account with
  model: null
```

`config/agents.yaml`
```yaml
triage_min_prior: 0.15
triage_min_hypotheses: 3
triage_max_hypotheses: 5
subagent_tool_call_limit: 4
config_a_tool_call_limit: 8
max_concurrency: 1            # local hardware; raise only if measured to help
call_timeout_s: 300
max_tokens: {triage: 300, subagent: 700, adjudicator: 900}
```

`config/scenarios.yaml`: seeds, injector parameter ranges (copied from SCENARIO_SPEC.md), split sizes, difficulty mix.
`config/ablations.yaml`: definitions of config A and config D (which stages run, which tool set, which verifier mode).
`config/pricing.yaml`: hosted prices only, with a `checked_on` date and source URL. Local backends are $0.

## 8. Events and traces (no SSE)
The app does not stream events. Each investigation writes one trace file, `runs/<investigation_id>/trace.json`, containing the stages in order with timings. The app reads these files. For a live run, the app calls the orchestrator directly and shows the stages when they complete, using `st.status` or `st.empty` placeholders.

Trace stage names: `alert`, `triage`, `subagent:<hypothesis>`, `verification`, `adjudication`, `report`.

## 9. Determinism
- Seeds for scenario generation, splits, detector fitting and any sampling.
- Ollama: set `temperature: 0` and a fixed `seed` in options for evaluation runs. Record both in `config.json`.
- Record model digest (from `ollama show`) in each run's config.
- Variance is measured, not assumed away: a small repeat (for example 10 cases run twice) is reported if time allows.

## 10. Concurrency and failure handling
- Default concurrency 1. The semaphore is still implemented, so the design is honest about parallelism and can be raised if measured.
- A failed subagent yields an `inconclusive` report with an error note. The investigation continues.
- A failed triage stage falls back to the three hypotheses with the highest rule-based prior from the alert's top features. Record the fallback.
- A failed adjudicator yields an `inconclusive` `IncidentReport` with the verified evidence listed and the reason. Never fabricate a verdict.
- The spend cap aborts new hosted calls cleanly and marks the run as truncated.
