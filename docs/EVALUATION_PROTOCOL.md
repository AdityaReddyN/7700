# Evaluation protocol

## 1. What is being evaluated
Whether the full pipeline (config D) gives more accurate, better-supported explanations than a single agent with the same tools (config A), on a small, labelled test set, on a 16 GB CPU laptop.

The evaluation is deliberately small. Say so in every table: "n = 25 test scenarios, one run."

## 2. Splits and usage

| Split | Scenarios | Use |
|---|---|---|
| KB | 10 (2 per label) | Case cards only. Never evaluated |
| Dev | 15 (3 per label) | Iterate prompts, thresholds, tools |
| Test | 25 (5 per label) | Final numbers only |

Rules:
- Iterate on dev only.
- Run each config on test once for the final numbers. Re-runs are allowed only after a bug fix, and must be logged in `EXPERIMENT_REGISTRY.md` with the reason.
- Test numbers are not used to choose prompts, thresholds or models.

## 3. Configurations

| Config | Description | Status |
|---|---|---|
| A | Single agent; all five tools; up to 8 tool calls; returns top hypothesis plus alternatives | Required |
| D | Full pipeline: triage, sequential subagents (up to 4 tool calls each), verifier, adjudicator | Required |
| D-hosted | Config D with a hosted Muse model for the adjudicator only, on test | Optional, only if budget allows |
| Glimmer-local | Config D with Muse Glimmer 2-bit, on a small subset | Optional, only if Glimmer runs usably |

Ablations beyond A and D are out of scope for v1.

## 4. Metrics

| Metric | Definition | Reported as |
|---|---|---|
| Top-1 accuracy | Final verdict equals the scenario label | Fraction, with n |
| Top-2 accuracy | Label is among the top two ranked hypotheses | Fraction, with n |
| Per-class precision, recall, F1 | Standard, computed on verdicts. Five classes with 5 test cases each: report counts, not just F1 | Table with counts |
| Confusion matrix | 5 by 5, counts | Figure and table |
| Evidence support rate | Verified evidence items / all evidence items cited | Fraction, with n items |
| Unsupported-claim rate | Evidence items failing verification / all items | Fraction |
| Inconclusive rate | Share of investigations with an `inconclusive` verdict | Fraction |
| Tool-call validity | Tool calls that parsed and ran / all tool calls | Fraction |
| Structured-output parse rate | Stage outputs that validated on first try / all stage outputs | Fraction |
| Latency | Wall-clock seconds per investigation, per stage | Median and range (p50 and max; p95 is not meaningful at n = 25) |
| Cost | Local: $0 money; report seconds. Hosted: dollars from the wrapper log | Per investigation |
| Detector | Recall and false-positive rate on dev and test scenarios | Fraction, with n |
| Calibration | Accuracy by confidence band (below 0.5, 0.5 to 0.7, above 0.7). Counts per band | Table; ECE only if every band has at least 5 cases |

Do not report a speedup between A and D as a headline number. If latencies are measured, report both medians and say they were measured on one laptop with CPU-only inference.

## 5. Verifier definition

For each evidence item (`Evidence`):
1. `ref_id` must exist in the investigation's ToolLog. If not: `verified = false`, reason `missing_ref`.
2. If `stat` and `value` are both given:
   - `stat` must appear as a key in the logged output of that `ref_id`, or as a key in a nested dictionary of it. If not: `verified = false`, reason `unknown_stat`.
   - The logged numeric value must match `value` within **5% relative** or **0.5 absolute**, whichever is larger. If not: `verified = false`, reason `value_mismatch`.
3. If `stat` or `value` is missing, `verified` depends only on rule 1 and is recorded as `verified_partial`. Count these separately; they are not counted as fully supported.
4. The claim text is **not** machine-checked. The manual spot-check (section 8) measures how often that matters.

Unit tests required: missing ref, unknown stat, value exactly at tolerance, value just outside tolerance, value zero, negative values, `null` value with a stat present.

Per-report support rate = verified items / total items in that report. The adjudicator receives only verified items.

## 6. Statistics

- With n = 25, confidence intervals are wide. Report 95% bootstrap intervals over cases (1,000 resamples) for top-1 accuracy and evidence support rate, and state n.
- Do not claim one config is better unless the intervals clearly separate or a paired comparison on the same cases supports it. Paired comparison (for example McNemar's test on per-case correct or incorrect) is preferred.
- Every table states its sample size.
- Do not report p-values as proof. Report them as one piece of evidence next to the counts.

## 7. Run outputs

```
results/<run_id>/
  config.json            config name, git commit, models with digests, seeds, options
  llm_calls.jsonl        one line per model call
  cases/<alert_id>.json  report, trace reference, verifier output, metrics, label
  summary.csv            one row per case: label, verdict, correct, support rate, seconds
  summary.md             tables for the README (generated)
  figures/*.png          accuracy by config, confusion matrix, latency per case, calibration
```

Required figures: accuracy by config (with n), confusion matrix for config D, latency per case for configs A and D, calibration counts for config D.

`make summarize` generates `summary.csv`, `summary.md` and figures from `results/` only. Nothing is typed by hand.

## 8. Manual spot-check (human fills)

Sample 10 evidence items per config (30 total if time allows), chosen at random with a fixed seed. For each, a human fills:

| alert_id | evidence claim | ref_id | does the cited output support the claim? (y/n) | verifier said verified? | notes |
|---|---|---|---|---|---|

Report the disagreement rate: cases where the human and the verifier differ, over total checked. Report it next to the support rate. If the disagreement rate is high, say that the support rate overstates quality.

The agent produces the sampled sheet (CSV) with the claim text and tool output snippet. The human fills the rest.

## 9. Error analysis (required in the README)
For each label with at least two errors:
- Count of errors.
- Most frequent confusion (predicted label).
- Two example alert ids (not scenario ids).
- Likely cause: tool gap, retrieval miss, prompt issue, ambiguous scenario, or model limit.
- Proposed fix or limitation statement.

Also report: detector missed detections (count), inconclusive investigations (count), and structured-output failures (count).

## 10. Targets (set before running test; edit only with a logged decision)
These are targets, not promises. Report what happens.
- Config D top-1 accuracy at or above config A. If not, say so and explain.
- Evidence support rate at least 0.90 on verified items. If not, the verifier or the prompts need work before the final run.
- Tool-call validity at least 0.90. If lower, the tool-calling mode needs changing (see ARCHITECTURE.md section 6).
- Every investigation under 15 minutes on the laptop. If not, report the actual median and cut scope as in AGENTS.md.

## 11. Integrity checklist (complete before writing any number down)
- [ ] Leakage test passes (`make test`).
- [ ] No prompt contains a scenario id, split name or test label.
- [ ] Test split used once per config, or re-runs are logged in EXPERIMENT_REGISTRY.md.
- [ ] Every reported number traces to a file in `results/`.
- [ ] Failures, inconclusive cases and weak classes are reported.
- [ ] Sample size appears next to every number.
- [ ] Model names and digests are recorded in `config.json`.
