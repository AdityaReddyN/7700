# Streamlit app specification

Goal: the analysis and the explanation are the centre of the app. Each alert is presented as a case the judge walks through in order. The app must work from saved traces, so the demo never depends on the model being fast.

Reference layout: the HTML mockup approved in conversation (one case on a single page, with a track replay, hypothesis cards, a verifier table, and a labelled verdict). Match its sections and wording where practical.

## 1. Navigation
Sidebar with three entries, rendered with `st.sidebar` and `st.radio`:
1. **Investigate** (default): the case story.
2. **Report**: the full report for the selected alert, including evidence table and plot.
3. **Benchmark**: reads `results/`.

Sidebar also shows: the selected alert (dropdown of alerts from `data/alerts/alerts.parquet` or `alerts.json`), the mode (Replay or Live), the model name and config from the trace, and a visible "Rule-based flagger" label.

Use `st.session_state` for the selected alert, the scrubber position and the current step. Nothing resets when the user moves the scrubber.

## 2. Investigate view (the case story)

Top to bottom:

1. **Header.** Alert id, icao24, score, and one line: "Why it was flagged: <summary from the alert>".
2. **Step indicator.** Five steps: Detected, Hypotheses, Debate, Verified, Verdict. Highlight the step the user is viewing. Use a segmented control or `st.radio` horizontally. Each step shows its content below; do not hide content from the page layout during streaming.
3. **Track replay (Detected step).** A Plotly chart of the track: position path on the left, reported speed and implied speed on the right, with a `st.slider` for time point. The residual readout updates from the **real track data** (computed from the saved track, not a formula). Mark the time the anomaly starts.
4. **Hypotheses (Hypotheses step).** Triage output as cards, sorted by prior. Show the top card outlined. Each card: hypothesis name, prior, one-line reason. Hovering or clicking shows its "supports" and "refutes" signs from the cheat sheet, placed beside the observed values where they match.
5. **Debate (Debate step).** For each subagent: a tabbed or expandable panel with "For" evidence and "Against" evidence, the verdict, confidence, and the inference labelled as reasoning. Use `st.expander` per hypothesis. Each evidence line shows its `ref_id`.
6. **Verification (Verified step).** Table of every evidence item: claim, ref_id, status (Verified / Excluded), and the reason for any exclusion (missing ref, unknown stat, value mismatch). Excluded items are shown, not hidden. Count of verified and excluded at the top.
7. **Verdict (Verdict step).** Verdict, confidence, the verified evidence summary, the labelled inference, "What would change my mind", and the recommended action.

Use `st.status` or `st.empty` placeholders in Live mode so stages appear as they complete.

## 3. Report view
- The full `IncidentReport` for the selected alert.
- Evidence table (verified only) with ref ids.
- Ranked list of all hypotheses with verdicts.
- Metadata: config, model name and digest, per-stage seconds, number of tool calls, excluded evidence count.
- Plot: generated from the saved track with Matplotlib, saved as PNG under `results/<run_id>/figures/` or `runs/<id>/`.
- Download button for the report as JSON (`st.download_button`).

## 4. Benchmark view
- Reads only `results/<run_id>/summary.csv`, `summary.md` and figures. Never computes metrics itself.
- Shows, for each config: n, top-1 accuracy with bootstrap interval, evidence support rate, inconclusive rate, median seconds per investigation.
- Confusion matrix for config D.
- Latency per case for A and D.
- A visible note: "n = 25 test scenarios, one run, CPU-only inference on one laptop."
- A visible note on the detector: recall and false-positive rate, with n.
- If `results/` is empty, show a message saying no evaluation has been run, not placeholder numbers.

## 5. Replay and live modes

**Replay (default):** loads `runs/<investigation_id>/trace.json` or the case file from `results/<run_id>/cases/`. Label it "Replay of a saved run" at the top of the Investigate view, with the run date and model.

**Live:** a button "Run live investigation (short case)". Calls the orchestrator directly. Shows stage progress. Only available when the model backend responds (the app checks with a quick ping on demand). Live runs are saved to `runs/`. Label the result "Live run".

Never present a replayed trace as a live run. Never present a live run as a full evaluation.

## 6. Interactions that carry analysis (keep to these)
- Time scrubber on the track, driving the residual readout.
- Click on a hypothesis card to show its signs and observed values.
- Click on a verified evidence row to show the logged tool output (the full output from the ToolLog, shown as formatted JSON in an expander).
- Optional, only if time allows: toggle an evidence item off and recompute the confidence with the same rule as the adjudicator's cap. Label the recomputed value as "recomputed from evidence, not a new model run".

Do not add a free-text chatbot. It falls into the anti-project list.

## 7. Streamlit implementation notes
- Use `st.set_page_config(layout="wide")`.
- Use `st.fragment` (where available in the installed Streamlit version) for the scrubber and the evidence panel, so only that part reruns. If the installed version lacks it, keep the page small.
- Use Plotly for the track chart; hover and zoom are expected.
- Use `st.dataframe` for tables; set column config for the status column.
- Keep the page fast: load traces once with `st.cache_data`.
- No external network calls from the app. No external fonts or images.
- Keep the UI readable: sentence case, no emoji, no all-caps labels.

## 8. What the app must not do
- Compute metrics on the fly.
- Show placeholder or invented numbers.
- Expose scenario ids or labels for the alert being investigated. Ground-truth labels are shown only in the Benchmark view and only from `results/`, and only where the evaluation has been run.
- Require the internet.
